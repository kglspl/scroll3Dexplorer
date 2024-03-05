import argparse
import enum
import os


class Actions(str, enum.Enum):
    download = "download"
    download_apply = "download-apply"
    apply = "apply"


def parse_arguments():
    # we parse just --actions here so that we can set `required` argument correctly on other arguments when real parsing happens:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--actions", required=False, default=None, type=Actions)
    args_pre, _ = pre.parse_known_args()

    # parse arguments:
    argparser = argparse.ArgumentParser(usage="%(prog)s [OPTION]...", description="Scroll data downloader for Vesuvius Challenge. See https://scrollprize.org/data for details.")
    argparser.add_argument("--actions", help=f"which action(s) to perform: {', '.join([t.value for t in Actions])}", required=True, default="download-apply", type=Actions)
    argparser.add_argument(
        "--h5fs-scroll",
        help="full path to target scroll H5FS (.h5) file; file will be created if it doesn't exist yet, but directory must exist",
        required=args_pre.actions in [Actions.apply, Actions.download_apply],
    )
    argparser.add_argument(
        "--download-dir", help="full path to a target directory into which the downloaded files will be saved", required=args_pre.actions in [Actions.download, Actions.download_apply]
    )
    argparser.add_argument(
        "--auth",
        metavar="USERNAME:PASSWORD",
        help="credentials for downloading data from Vesuvius Challenge servers (see https://scrollprize.org/data for registration form)",
        required=args_pre.actions in [Actions.download, Actions.download_apply],
    )
    arguments = argparser.parse_args()
    return arguments


def main():
    arguments = parse_arguments()
    print(arguments)


if __name__ == "__main__":
    main()
