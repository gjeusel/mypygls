"""Implementation of the LSP server for Mypy."""
from __future__ import annotations

import enum
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from lsprotocol.types import (
    INITIALIZE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    Diagnostic,
    DiagnosticSeverity,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    InitializeParams,
    Position,
    Range,
)
from mypy import api as mypy_api
from mypy.version import __version__ as __mypy_version__
from pygls import server, uris
from pygls.workspace import Document

from mypygls import __version__
from mypygls.timer import timer

logger = logging.getLogger("mypygls")


class DMypyStatus(enum.Enum):
    ok = 0
    warning = 1
    error = 2


class DMypyCmd(str, enum.Enum):
    # fmt: off
    start = "start"      # Start daemon
    check = "check"      # Check some files (requires daemon)
    recheck = "recheck"  # Re-check the previous list of files, with optional modifications (requires daemon)
    restart = "restart"  # Restart daemon (stop or kill followed by start)
    status = "status"    # Show daemon status
    stop = "stop"        # Stop daemon (asks it politely to go away)
    kill = "kill"        # Kill daemon (kills the process)
    run = "run"          # Check some files, [re]starting daemon if necessary
    suggest = "suggest"  # Suggest a signature or show call sites for a specific function
    inspect = "inspect"  # Locate and statically inspect expression(s)
    hang = "hang"        # Hang for 100 seconds
    daemon = "daemon"    # Run daemon in foreground
    # fmt: on


@dataclass
class UserSettings:
    log_level: str = "debug"  # "notset"
    log_file: str | None = (Path.home() / ".cache/nvim/mypygls.log").as_posix()

    args: list[str] = field(default_factory=list)
    # interpreter: str


@dataclass
class Settings(UserSettings):
    workspace: str = field(default_factory=lambda: uris.from_fs_path(os.getcwd()))
    workspaceFS: str = field(default_factory=lambda: os.getcwd())

    @property
    def workspace_name(self) -> str:
        return Path(self.workspaceFS).stem


@dataclass
class State:
    state_folder: ClassVar[Path] = Path(tempfile.mkdtemp(prefix="mypygls"))

    settings: Settings

    registered_files: list[str] = field(default_factory=list)
    daemon_started: bool = False

    @classmethod
    def from_init_params(cls, params: InitializeParams) -> State:
        # Extract `settings` from the initialization options.
        user_settings = (params.initialization_options or {}).get(  # type: ignore
            "settings",
        )

        if isinstance(user_settings, dict):
            # In Sublime Text, Neovim, and probably others, we're passed a single
            # `settings`, which we'll treat as defaults for any future files.
            settings = Settings(**user_settings)
        elif isinstance(user_settings, list):
            # In VS Code, we're passed a list of `settings`, one for each workspace folder.
            # Let's ignore this for now and consider arbitrarily the first one.
            user_settings = user_settings[0]
            if "workspace" in user_settings:
                kwargs = {
                    "workspace": user_settings["workspace"],
                    "workspace_path": uris.to_fs_path(user_settings["workspace"]),
                }
            settings = Settings(**(user_settings | kwargs))
        else:
            settings = Settings()

        return cls(settings=settings)

    def _to_state_filepath(self, filename: str) -> str:
        status_file = self.state_folder / f"{self.settings.workspace_name}-{filename}"
        return status_file.absolute().as_posix()

    @property
    def status_file(self) -> str:
        return self._to_state_filepath("status.json")

    @property
    def stats_file(self) -> str:
        return self._to_state_filepath("perf.json")

    def update_registered_files(self) -> None:
        # Initialize an empty list to store the absolute paths
        pyfiles = []

        # Walk through the directory tree and get the list of Python files
        for root, _, files in os.walk(self.settings.workspaceFS):
            for f in files:
                if f.endswith(".py"):
                    abs_path = os.path.abspath(os.path.join(root, f))
                    pyfiles.append(abs_path)

        self.registered_files = pyfiles


class ProgressTokens(str, enum.Enum):
    start_daemon = "start_daemon"
    linting = "linting"


STATE: State

MAX_WORKERS = 5
LSP_SERVER = server.LanguageServer(
    name="mypygls",
    version=__version__,
    max_workers=MAX_WORKERS,
)

TOOL_DISPLAY = "dmypy"

###
# Mypy utils
###

# coming from pylsp-mypy (to be checked agasint null-ls list of regexes to catch all cases)
LINE_PATTERN = re.compile(
    r"((?:^[a-z]:)?[^:]+):(?:(\d+):)?(?:(\d+):)? (?:note: )?(\w+): (.*)"
)


def format_dmypy_cmd(cmd: DMypyCmd, *, path: str | None = None) -> list[str]:
    dmypy_args = [
        "--status-file",
        STATE.status_file,
    ]

    cmd_args: list[str] = []
    mypy_args: list[str] = []

    if cmd == DMypyCmd.run:
        cmd_args = ["--perf-stats-file", STATE.stats_file]

        mypy_args = [
            "--show-column-numbers",
            # "--config-file",
            # f"{settings.workspaceFS}/pyproject.toml",
        ]

    if path:
        mypy_args.append(path)

    if mypy_args:
        mypy_cmd = [*dmypy_args, cmd.value, *cmd_args, "--", *mypy_args]
    else:
        mypy_cmd = [*dmypy_args, cmd.value, *cmd_args]

    logger.debug("dmypy " + " ".join(mypy_cmd))

    return mypy_cmd


def call_dmypy(cmd: DMypyCmd, *, path: str | None = None) -> tuple[str, str, int]:
    out, err, status = mypy_api.run_dmypy(format_dmypy_cmd(cmd=cmd, path=path))

    if status == DMypyStatus.error.value:
        logger.error(
            f"failed to run {cmd.value} for {STATE.settings.workspace_name}\n{err}"
        )

    return out, err, status


def daemon_status() -> DMypyStatus:
    _, _, status = call_dmypy(DMypyCmd.status)
    return DMypyStatus(status)


def start_daemon() -> None:
    # use the "run" command to ensure the daemon grab all pythons files
    # (which is not done via "start")
    with timer:
        out, err, status = call_dmypy(DMypyCmd.run, path=STATE.settings.workspaceFS)

    if status == DMypyStatus.error.value:
        logger.error(f"Failed to run daemon:\n{status=}\n{err=}\n{out=}")
        LSP_SERVER.show_message("failed to start.")
        return

    logger.info(f"started daemon for workspace '{STATE.settings.workspace_name}'")
    STATE.update_registered_files()
    STATE.daemon_started = True
    LSP_SERVER.show_message(f"daemon (re-)started ({timer}).")


def _parse_raw_diagnostic_line(line: str, document: Document) -> Diagnostic | None:
    result = LINE_PATTERN.match(line)
    if not result:
        return None

    filepath, raw_lineno, raw_offset, raw_severity, msg = result.groups()

    if not document.path.endswith(filepath):
        return None

    lineno = int(raw_lineno or 1) - 1  # 0-based line number
    offset = int(raw_offset or 1) - 1  # 0-based offset

    start_pos = Position(line=lineno, character=offset)

    word = document.word_at_position(start_pos)
    if word:
        end_pos = Position(line=lineno, character=offset + len(word))
    else:
        end_pos = Position(line=lineno, character=offset + 1)

    if raw_severity == "Hint":
        severity = DiagnosticSeverity.Hint
    elif raw_severity == "error":
        severity = DiagnosticSeverity.Error
    else:
        severity = DiagnosticSeverity.Warning

    return Diagnostic(
        source=TOOL_DISPLAY,
        range=Range(start=start_pos, end=end_pos),
        message=msg,
        severity=severity,
    )


def run_lint(document: Document, daemon: bool) -> list[Diagnostic]:
    if daemon:
        raw_diagnostics, messages, status = call_dmypy(DMypyCmd.recheck)
    else:
        logger.debug(f"running fallback mypy on {document.path}")
        raw_diagnostics, messages, status = mypy_api.run(
            ["--show-column-numbers", document.path]
        )

    diagnostics: list[Diagnostic] = []
    for line in raw_diagnostics.splitlines():
        diagnostic = _parse_raw_diagnostic_line(line, document)
        if diagnostic:
            diagnostics.append(diagnostic)

    logger.debug(f"found {len(diagnostics)} diagnostics for {document.path}")

    # Handle case where mypy failed for any reason to run, and reported an error.
    # We want to put the details at the first line like a diagnostic error / warning.
    if messages:
        diagnostics.append(
            Diagnostic(
                source=TOOL_DISPLAY,
                range=Range(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=0),
                ),
                message=messages,
                severity=DiagnosticSeverity.Error
                if status != 0
                else DiagnosticSeverity.Warning,
            )
        )

    return diagnostics


###
# Linting
###


@LSP_SERVER.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(params: DidOpenTextDocumentParams) -> None:
    """LSP handler for textDocument/didOpen request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)

    if not STATE.daemon_started:
        diagnostics = run_lint(document, daemon=False)
    else:
        if document.path not in STATE.registered_files:
            logger.debug(f"New buffer {document.path}. Waiting for it to be saved.")
            return

        diagnostics = run_lint(document, daemon=True)

    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.thread()
@LSP_SERVER.feature(TEXT_DOCUMENT_DID_SAVE)
def did_save_daemon(params: DidSaveTextDocumentParams) -> None:
    """LSP handler for textDocument/didSave request."""

    document = LSP_SERVER.workspace.get_document(params.text_document.uri)

    if not STATE.daemon_started:
        diagnostics = run_lint(document, daemon=False)
    else:
        if document.path not in STATE.registered_files:
            logger.info(f"New file {document.path}. Restarting the daemon.")
            mypy_api.run_dmypy(format_dmypy_cmd(DMypyCmd.stop))
            start_daemon()
            return

        diagnostics = run_lint(document, daemon=True)

    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: DidCloseTextDocumentParams) -> None:
    """LSP handler for textDocument/didClose request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    # Publishing empty diagnostics to clear the entries for this file.
    LSP_SERVER.publish_diagnostics(document.uri, [])


###
# Lifecycle
###


@LSP_SERVER.thread()
@LSP_SERVER.feature(INITIALIZE)
def initialize(params: InitializeParams) -> None:
    """LSP handler for initialize request."""

    LSP_SERVER.show_message_log(f"MYPYGLS: {params=}")

    global STATE
    STATE = State.from_init_params(params)

    # # Setup LSP trace level considered as logs.
    # if isinstance(LSP_SERVER.lsp, protocol.LanguageServerProtocol):
    #     log_levels = {settings.logLevel for settings in STATE.workspace_settings}
    #     if "debug" in log_levels:
    #         LSP_SERVER.lsp.trace = TraceValues.Verbose
    #     elif {None} == log_levels:
    #         LSP_SERVER.lsp.trace = TraceValues.Off
    #     else:
    #         LSP_SERVER.lsp.trace = TraceValues.Messages

    # Setup mypygls logs
    if STATE.settings.log_file:
        handler = logging.FileHandler(STATE.settings.log_file)
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)-8s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(STATE.settings.log_level.upper())

    logger.info(f"initialized mypygls '{__version__}' with mypy '{__mypy_version__}'")
    logger.debug(f"state folder at {STATE.state_folder}")

    # Start the mypy daemon
    start_daemon()
