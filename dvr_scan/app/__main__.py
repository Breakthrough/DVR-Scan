#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2014 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#

import argparse
import logging
import sys
import typing as ty

from dvr_scan import get_license_info
from dvr_scan.app.application import Application
from dvr_scan.config import CHOICE_MAP
from dvr_scan.platform import init_logger
from dvr_scan.shared import (
    VERSION_STRING,
    LicenseAction,
    VersionAction,
    string_type_check,
)

EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1


def get_cli_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        argument_default=argparse.SUPPRESS,
    )
    if hasattr(parser, "_optionals"):
        parser._optionals.title = "arguments"

    parser.add_argument(
        "-V",
        "--version",
        action=VersionAction,
        version=VERSION_STRING,
    )

    parser.add_argument(
        "-v",
        "--verbosity",
        metavar="type",
        type=string_type_check(CHOICE_MAP["verbosity"], False, "type"),
        help=(
            "Amount of verbosity to use for log output. Must be one of: %s."
            % (", ".join(CHOICE_MAP["verbosity"]),)
        ),
    )

    parser.add_argument(
        "--logfile",
        metavar="file",
        type=str,
        help=(
            "Path to log file for writing application output. If FILE already exists, the program"
            " output will be appended to the existing contents."
        ),
    )

    parser.add_argument(
        "-L",
        "--license",
        action=LicenseAction,
        version=get_license_info(),
    )

    return parser


def _init_logging(args: ty.Optional[argparse.ArgumentParser]):
    verbosity = logging.INFO
    if args is not None and hasattr(args, "verbosity"):
        verbosity = getattr(logging, args.verbosity.upper())

    quiet_mode = False
    if args is not None and hasattr(args, "quiet_mode"):
        quiet_mode = args.quiet_mode

    init_logger(
        log_level=verbosity,
        show_stdout=not quiet_mode,
        log_file=args.logfile if hasattr(args, "logfile") else None,
    )


def main():
    args = get_cli_parser().parse_args()
    _init_logging(args)
    app = Application()
    app.run()
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
