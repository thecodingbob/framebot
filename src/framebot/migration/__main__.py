import argparse
from pathlib import Path

from .migrate import migrate


def main():
    parser = init_argparse()
    args = parser.parse_args()
    source = args.source
    target = args.target if args.target is not None else args.source
    migrate(source, target)


def init_argparse() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(
        prog="Framebot migration tool",
        usage=f"migrate -s source -t target...",
        description="Migrates the local file created from old framebot versions for use with the newer ones."
    )
    arg_parser.add_argument("-s", "--source", type=Path, metavar="Source directory",
                            help="Directory where the legacy framebot files are stored.", required=True)
    arg_parser.add_argument("-t", "--target", type=Path, metavar="Target directory",
                            help="Directory where the new framebot files are to be stored.", required=False)
    return arg_parser


if __name__ == "__main__":
    main()
