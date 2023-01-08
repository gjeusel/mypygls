import argparse


def main() -> None:
    from mypygls import __version__, server

    parser = argparse.ArgumentParser(prog="mypygls")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.parse_args()

    server.LSP_SERVER.start_io()


if __name__ == "__main__":
    main()
