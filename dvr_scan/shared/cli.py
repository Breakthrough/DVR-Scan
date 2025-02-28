#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2024 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#

import argparse
import typing as ty

import dvr_scan
from dvr_scan.platform import get_system_version_info

# Version string shown for the -v/--version CLI argument.
VERSION_STRING = f"""DVR-Scan {dvr_scan.__version__}
------------------------------------------------
Copyright (C) 2024 Brandon Castellano
< https://www.dvr-scan.com >
"""


class VersionAction(argparse.Action):
    """argparse Action for displaying DVR-Scan version."""

    def __init__(
        self,
        option_strings,
        version=None,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="show version number",
    ):
        super(VersionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )
        self.version = version

    def __call__(self, parser, namespace, values, option_string=None):
        version = f"{self.version}\n{get_system_version_info(separator_width=48)}\n"
        parser.exit(message=version)


class LicenseAction(argparse.Action):
    """argparse Action for displaying DVR-Scan license & copyright info."""

    def __init__(
        self,
        option_strings,
        version=None,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="show copyright information",
    ):
        super(LicenseAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )
        self.version = version

    def __call__(self, parser, namespace, values, option_string=None):
        version = self.version
        if version is None:
            version = parser.version
        parser.exit(message=version)


def timecode_type_check(metavar: ty.Optional[str] = None):
    """Creates an argparse type for a user-inputted timecode.

    The passed argument is declared valid if it meets one of three valid forms:
      1) Standard timecode; in form HH:MM:SS or HH:MM:SS.nnn
      2) Number of seconds; type # of seconds, followed by s (e.g. 54s, 0.001s)
      3) Exact number of frames; type # of frames (e.g. 54, 1000)
     valid integer which
    is greater than or equal to min_val, and if max_val is specified,
    less than or equal to max_val.

    Returns:
        A function which can be passed as an argument type, when calling
        add_argument on an ArgumentParser object

    Raises:
        ArgumentTypeError: Passed argument must be integer within proper range.
    """
    metavar = "value" if metavar is None else metavar

    def _type_checker(value):
        valid = False
        value = str(value).lower().strip()
        # Integer number of frames.
        if value.isdigit():
            # All characters in string are digits, just parse as integer.
            frames = int(value)
            if frames >= 0:
                valid = True
                value = frames
        # Integer or real/floating-point number of seconds.
        elif value.endswith("s"):
            secs = value[:-1]
            if secs.replace(".", "").isdigit():
                secs = float(secs)
                if secs >= 0.0:
                    valid = True
                    value = secs
        # Timecode in HH:MM:SS[.nnn] format.
        elif ":" in value:
            tc_val = value.split(":")
            if (
                len(tc_val) == 3
                and tc_val[0].isdigit()
                and tc_val[1].isdigit()
                and tc_val[2].replace(".", "").isdigit()
            ):
                hrs, mins = int(tc_val[0]), int(tc_val[1])
                secs = float(tc_val[2]) if "." in tc_val[2] else int(tc_val[2])
                if hrs >= 0 and mins >= 0 and secs >= 0 and mins < 60 and secs < 60:
                    valid = True
        if not valid:
            raise argparse.ArgumentTypeError(
                f"invalid timecode: {value}\n"
                "Timecode must be specified as number of frames (12345), seconds (number followed "
                "by s, e.g. 123s or 123.45s), or timecode (HH:MM:SS[.nnn]."
            )
        return value

    return _type_checker


def int_type_check(
    min_val: int, max_val: ty.Optional[int] = None, metavar: ty.Optional[str] = None
):
    """Creates an argparse type for a range-limited integer.

    The passed argument is declared valid if it is a valid integer which
    is greater than or equal to min_val, and if max_val is specified,
    less than or equal to max_val.

    Returns:
        A function which can be passed as an argument type, when calling
        add_argument on an ArgumentParser object

    Raises:
        ArgumentTypeError: Passed argument must be integer within proper range.
    """
    metavar = "value" if metavar is None else metavar

    def _type_checker(value):
        value = int(value)
        valid = True
        msg = ""
        if max_val is None:
            if value < min_val:
                valid = False
            msg = "invalid choice: %d (%s must be at least %d)" % (
                value,
                metavar,
                min_val,
            )
        else:
            if value < min_val or value > max_val:
                valid = False
            msg = "invalid choice: %d (%s must be between %d and %d)" % (
                value,
                metavar,
                min_val,
                max_val,
            )
        if not valid:
            raise argparse.ArgumentTypeError(msg)
        return value

    return _type_checker


def kernel_size_type_check(metavar: ty.Optional[str] = None):
    metavar = "value" if metavar is None else metavar

    def _type_checker(value):
        value = int(value)
        if value not in (-1, 0) and (value < 3 or value % 2 == 0):
            raise argparse.ArgumentTypeError(
                "invalid choice: %d (%s must be an odd number starting from 3, 0 to disable, or "
                "-1 for auto)" % (value, metavar)
            )
        return value

    return _type_checker


def float_type_check(
    min_val: float,
    max_val: ty.Optional[float] = None,
    metavar: ty.Optional[str] = None,
    default_str: ty.Optional[str] = None,
):
    """Creates an argparse type for a range-limited float.

    The passed argument is declared valid if it is a valid float which is
    greater thanmin_val, and if max_val is specified, less than max_val.

    Returns:
        A function which can be passed as an argument type, when calling
        add_argument on an ArgumentParser object

    Raises:
        ArgumentTypeError: Passed argument must be float within proper range.
    """
    metavar = "value" if metavar is None else metavar

    def _type_checker(value):
        if default_str and isinstance(value, str) and default_str == value:
            return None
        value = float(value)
        valid = True
        msg = ""
        if max_val is None:
            if value < min_val:
                valid = False
            msg = "invalid choice: %3.1f (%s must be greater than %3.1f)" % (
                value,
                metavar,
                min_val,
            )
        else:
            if value < min_val or value > max_val:
                valid = False
            msg = "invalid choice: %3.1f (%s must be between %3.1f and %3.1f)" % (
                value,
                metavar,
                min_val,
                max_val,
            )
        if not valid:
            raise argparse.ArgumentTypeError(msg)
        return value

    return _type_checker


def string_type_check(
    valid_strings: ty.List[str], case_sensitive: bool = True, metavar: ty.Optional[str] = None
):
    """Creates an argparse type for a list of strings.

    The passed argument is declared valid if it is a valid string which exists
    in the passed list valid_strings.  If case_sensitive is False, all input
    strings and strings in valid_strings are processed as lowercase.  Leading
    and trailing whitespace is ignored in all strings.

    Returns:
        A function which can be passed as an argument type, when calling
        add_argument on an ArgumentParser object

    Raises:
        ArgumentTypeError: Passed argument must be string within valid list.
    """
    metavar = "value" if metavar is None else metavar
    valid_strings = [x.strip() for x in valid_strings]
    if not case_sensitive:
        valid_strings = [x.lower() for x in valid_strings]

    def _type_checker(value):
        value = str(value)
        valid = True
        if not case_sensitive:
            value = value.lower()
        if value not in valid_strings:
            valid = False
            case_msg = " (case sensitive)" if case_sensitive else ""
            msg = "invalid choice: %s (valid settings for %s%s are: %s)" % (
                value,
                metavar,
                case_msg,
                valid_strings.__str__()[1:-1],
            )
        if not valid:
            raise argparse.ArgumentTypeError(msg)
        return value

    return _type_checker
