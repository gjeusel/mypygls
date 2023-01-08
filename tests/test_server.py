import pytest

from mypygls.server import (
    LINE_PATTERN,
    # PATTERN_FULL_DIAG,
    # PATTERN_DIAG_WITHOUT_CODE,
    # PATTERN_NO_ROW_NO_COL,
)


class TestDiagnosticParsing:
    def test_full_diag(self):
        raw = 'test.py:1:1: error: Library stubs not installed for "requests" (or incompatible with Python 3.9)  [import]'
        expected = {
            "filename": "test.py",
            "row": "1",
            "col": "1",
            "severity": "error",
            "message": 'Library stubs not installed for "requests" (or incompatible with Python 3.9)',
            "code": "import",
        }

        assert PATTERN_FULL_DIAG.match(raw).groupdict() == expected  # type: ignore[union-attr]

    def test_diag_without_code(self):
        raw = 'test.py:2:1: note: Hint: "python3 -m pip install types-requests"'
        expected = {
            "filename": "test.py",
            "row": "2",
            "col": "1",
            "severity": "hint",
            "message": "python3 -m pip install types-requests",
        }

        assert PATTERN_DIAG_WITHOUT_CODE.match(raw).groupdict() == expected  # type: ignore[union-attr]

    def test_diag_no_row_no_col(self):
        raw = 'Unused "type: ignore" comment'
        expected = {"message": 'Unused "type: ignore" comment'}

        assert PATTERN_NO_ROW_NO_COL.match(raw).groupdict() == expected  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "raw, expected",
    (
        # should handle full diagnostic:
        (
            'test.py:1:1: error: Library stubs not installed for "requests" (or incompatible with Python 3.9)  [import]',
            {
                "filename": "test.py",
                "row": "1",
                "col": "1",
                "severity": "error",
                "message": 'Library stubs not installed for "requests" (or incompatible with Python 3.9)',
                "code": "import",
            },
        ),
        # should diagnostic without code:
        (
            'test.py:2:1: note: Hint: "python3 -m pip install types-requests"',
            {
                "filename": "test.py",
                "row": "2",
                "col": "1",
                "severity": "hint",
                "message": "python3 -m pip install types-requests",
            },
        ),
        # should handle diagnostic with no column or error code:
        (
            'Unused "type: ignore" comment',
            {
                "message": 'Unused "type: ignore" comment',
            },
        ),
    ),
)
def test_diagnostic_parse_regex(raw, expected):
    match = LINE_PATTERN.match(raw)

    if match is None:
        assert expected is None

    assert match.groups() == list(expected.values())


# def test_
