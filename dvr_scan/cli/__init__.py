# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2014-2023 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
""" ``dvr_scan.cli`` Module

This module provides the command-line business logic for the `dvr-scan` command. The entry point
starts the program by calling :py:func:`dvr_scan.cli.controller.run_dvr_scan`.

Control logic can be found in :py:mod:`dvr_scan.cli.controller` and configuration file parsing
is defined in :py:mod:`dvr_scan.cli.config`. This main module file defines :py:func:`get_cli_parser`
which provides an argparse-based CLI used by the DVR-Scan application.
"""

import argparse
from typing import List, Optional

import dvr_scan
from dvr_scan.cli.config import ConfigRegistry, CHOICE_MAP, USER_CONFIG_FILE_PATH
from dvr_scan.region import RegionValidator

# Version string shown for the -v/--version CLI argument.
VERSION_STRING = f"""------------------------------------------------
DVR-Scan {dvr_scan.__version__}
------------------------------------------------
Copyright (C) 2016-2023 Brandon Castellano
< https://www.dvr-scan.com >
"""

# In the CLI, -so/--scan-only is a different flag than -m/--output-mode, whereas in the
# config file they are the same option. Therefore, we remove the scan only choice
# from the -m/--output-mode selection in the CLI.
SCAN_ONLY_MODE = 'scan_only'
assert SCAN_ONLY_MODE in CHOICE_MAP['output-mode']
VALID_OUTPUT_MODES = [mode for mode in CHOICE_MAP['output-mode'] if mode != SCAN_ONLY_MODE]


def timecode_type_check(metavar: Optional[str] = None):
    """ Creates an argparse type for a user-inputted timecode.

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
    metavar = 'value' if metavar is None else metavar

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
        elif value.endswith('s'):
            secs = value[:-1]
            if secs.replace('.', '').isdigit():
                secs = float(secs)
                if secs >= 0.0:
                    valid = True
                    value = secs
        # Timecode in HH:MM:SS[.nnn] format.
        elif ':' in value:
            tc_val = value.split(':')
            if (len(tc_val) == 3 and tc_val[0].isdigit() and tc_val[1].isdigit()
                    and tc_val[2].replace('.', '').isdigit()):
                hrs, mins = int(tc_val[0]), int(tc_val[1])
                secs = float(tc_val[2]) if '.' in tc_val[2] else int(tc_val[2])
                if (hrs >= 0 and mins >= 0 and secs >= 0 and mins < 60 and secs < 60):
                    valid = True
        if not valid:
            raise argparse.ArgumentTypeError(
                f'invalid timecode: {value}\n'
                'Timecode must be specified as number of frames (12345), seconds (number followed '
                'by s, e.g. 123s or 123.45s), or timecode (HH:MM:SS[.nnn].')
        return value

    return _type_checker


def int_type_check(min_val: int, max_val: Optional[int] = None, metavar: Optional[str] = None):
    """ Creates an argparse type for a range-limited integer.

    The passed argument is declared valid if it is a valid integer which
    is greater than or equal to min_val, and if max_val is specified,
    less than or equal to max_val.

    Returns:
        A function which can be passed as an argument type, when calling
        add_argument on an ArgumentParser object

    Raises:
        ArgumentTypeError: Passed argument must be integer within proper range.
    """
    metavar = 'value' if metavar is None else metavar

    def _type_checker(value):
        value = int(value)
        valid = True
        msg = ''
        if max_val is None:
            if value < min_val:
                valid = False
            msg = 'invalid choice: %d (%s must be at least %d)' % (value, metavar, min_val)
        else:
            if value < min_val or value > max_val:
                valid = False
            msg = 'invalid choice: %d (%s must be between %d and %d)' % (value, metavar, min_val,
                                                                         max_val)
        if not valid:
            raise argparse.ArgumentTypeError(msg)
        return value

    return _type_checker


def _kernel_size_type_check(metavar: Optional[str] = None):
    metavar = 'value' if metavar is None else metavar

    def _type_checker(value):
        value = int(value)
        if not value in (-1, 0) and (value < 3 or value % 2 == 0):
            raise argparse.ArgumentTypeError(
                'invalid choice: %d (%s must be an odd number starting from 3, 0 to disable, or '
                '-1 for auto)' % (value, metavar))
        return value

    return _type_checker


def float_type_check(min_val: float,
                     max_val: Optional[float] = None,
                     metavar: Optional[str] = None,
                     default_str: Optional[str] = None):
    """ Creates an argparse type for a range-limited float.

    The passed argument is declared valid if it is a valid float which is
    greater thanmin_val, and if max_val is specified, less than max_val.

    Returns:
        A function which can be passed as an argument type, when calling
        add_argument on an ArgumentParser object

    Raises:
        ArgumentTypeError: Passed argument must be float within proper range.
    """
    metavar = 'value' if metavar is None else metavar

    def _type_checker(value):
        if default_str and isinstance(value, str) and default_str == value:
            return None
        value = float(value)
        valid = True
        msg = ''
        if max_val is None:
            if value < min_val:
                valid = False
            msg = 'invalid choice: %3.1f (%s must be greater than %3.1f)' % (value, metavar,
                                                                             min_val)
        else:
            if value < min_val or value > max_val:
                valid = False
            msg = 'invalid choice: %3.1f (%s must be between %3.1f and %3.1f)' % (value, metavar,
                                                                                  min_val, max_val)
        if not valid:
            raise argparse.ArgumentTypeError(msg)
        return value

    return _type_checker


def string_type_check(valid_strings: List[str],
                      case_sensitive: bool = True,
                      metavar: Optional[str] = None):
    """ Creates an argparse type for a list of strings.

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
    metavar = 'value' if metavar is None else metavar
    valid_strings = [x.strip() for x in valid_strings]
    if not case_sensitive:
        valid_strings = [x.lower() for x in valid_strings]

    def _type_checker(value):
        value = str(value)
        valid = True
        if not case_sensitive:
            value = value.lower()
        if not value in valid_strings:
            valid = False
            case_msg = ' (case sensitive)' if case_sensitive else ''
            msg = 'invalid choice: %s (valid settings for %s%s are: %s)' % (
                value, metavar, case_msg, valid_strings.__str__()[1:-1])
        if not valid:
            raise argparse.ArgumentTypeError(msg)
        return value

    return _type_checker


class LicenseAction(argparse.Action):
    """argparse Action for displaying DVR-Scan license & copyright info."""

    # pylint: disable=redefined-builtin, too-many-arguments
    def __init__(self,
                 option_strings,
                 version=None,
                 dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help="show copyright information"):
        super(LicenseAction, self).__init__(
            option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)
        self.version = version

    def __call__(self, parser, namespace, values, option_string=None):
        version = self.version
        if version is None:
            version = parser.version
        parser.exit(message=version)


class VersionAction(argparse.Action):
    """argparse Action for displaying DVR-Scan version."""

    # pylint: disable=redefined-builtin, too-many-arguments
    def __init__(self,
                 option_strings,
                 version=None,
                 dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help="show version number"):
        super(VersionAction, self).__init__(
            option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)
        self.version = version

    def __call__(self, parser, namespace, values, option_string=None):
        version = self.version
        if version is None:
            version = parser.version
        parser.exit(message=version)


class RegionAction(argparse.Action):

    DEFAULT_ERROR_MESSAGE = "Region must be 3 or more points of the form X0 Y0 X1 Y1 X2 Y2 ..."

    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None):
        assert nargs == '*'
        assert const is None
        super(RegionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)

    def __call__(self, parser, namespace, values: List[str], option_string=None):

        try:
            region = RegionValidator(" ".join(values))
        except ValueError as ex:
            message = " ".join(str(arg) for arg in ex.args)
            raise (argparse.ArgumentError(
                self, message if message else RegionAction.DEFAULT_ERROR_MESSAGE)) from ex

        # Append this ROI to any existing ones, if any.
        # TODO(v1.7): Audit uses of the 'regions' constant for -a/--add-region, replace with a named
        # constant where possible.
        items = getattr(namespace, 'regions', [])
        items += [region.value]
        setattr(namespace, 'regions', items)


# TODO: To help with debugging, add a `debug` option to the config file as well that, if set in the
# user config file, initializes the parser with exit_on_error=False.
def get_cli_parser(user_config: ConfigRegistry):
    """Creates the DVR-Scan argparse command-line interface.

    Arguments:
        user_config: User configuration file registry.

    Returns:
        ArgumentParser object, which parse_args() can be called with.
    """

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        argument_default=argparse.SUPPRESS,
    )

    if hasattr(parser, '_optionals'):
        # pylint: disable=protected-access
        parser._optionals.title = 'arguments'

    parser.add_argument(
        '-V',
        '--version',
        action=VersionAction,
        version=VERSION_STRING,
    )

    parser.add_argument(
        '-L',
        '--license',
        action=LicenseAction,
        version=dvr_scan.get_license_info(),
    )

    parser.add_argument(
        '-i',
        '--input',
        metavar='video_file',
        required=True,
        type=str,
        nargs='+',
        action='append',
        help=('[REQUIRED] Path to input video. May specify multiple inputs with the same'
              ' resolution and framerate, or by specifying a wildcard/glob. Output'
              ' filenames are generated using the first video name only.'),
    )

    parser.add_argument(
        '-d',
        '--output-dir',
        metavar='path',
        type=str,
        help=('If specified, write output files in the given directory. If path does not'
              ' exist, it  will be created. If unset, output files are written to the'
              ' current working directory.'),
    )

    parser.add_argument(
        '-o',
        '--output',
        metavar='video.avi',
        type=str,
        help=('If specified, all motion events will be written to a single file'
              ' in order (if not specified, separate files are created for each event).'
              ' Filename MUST end with .avi. Only supported in output mode OPENCV.'),
    )

    parser.add_argument(
        '-m',
        '--output-mode',
        metavar='mode',
        type=string_type_check(VALID_OUTPUT_MODES, False, 'mode'),
        help=('Set mode for generating output files. Certain features may not work with '
              ' all output modes. Must be one of: %s.%s' %
              (', '.join(VALID_OUTPUT_MODES), user_config.get_help_string('output-mode'))),
    )

    parser.add_argument(
        '-so',
        '--scan-only',
        action='store_true',
        default=False,
        help=('Only perform motion detection (does not write any files to disk).'
              ' If set, -m/--output-mode is ignored.'),
    )

    parser.add_argument(
        '-c',
        '--config',
        metavar='settings.cfg',
        type=str,
        help=('Path to config file. If not set, tries to load one from %s' %
              (USER_CONFIG_FILE_PATH)),
    )

    parser.add_argument(
        "-r",
        "--region-editor",
        dest='region_editor',
        action='store_true',
        help=("Show region editor window. Motion detection will be limited to the enclosed area "
              "during processing. Only single regions can be edited, but supports preview of "
              "multiple regions if defined.%s" % user_config.get_help_string("region-editor")),
    )

    parser.add_argument(
        "-a",
        "--add-region",
        metavar="X0 Y0 X1 Y1 X2 Y2",
        dest='regions',
        nargs='*',
        action=RegionAction,
        help=(
            "Limit motion detection to a region of the frame. The region is defined as a sequence "
            "of 3 or more points forming a closed shape inside the video. Coordinate 0 0 is top "
            "left of the frame, and WIDTH-1 HEIGHT-1 is bottom right. Can be specified multiple "
            "times to add more regions."))
    parser.add_argument(
        "-R",
        "--load-region",
        metavar="FILE.txt",
        type=str,
        help=("Load region data from file. Each line must be a list of points in the format "
              "specified by -a/--add-region. Each line is treated as a separate polygon."),
    )

    parser.add_argument(
        "-s",
        "--save-region",
        metavar="FILE.txt",
        type=str,
        help=("Save detection regions to FILE.txt before processing. If FILE.txt exists it will be "
              "overwritten. Allows loading same regions using -R/--load-region."))

    parser.add_argument(
        '-b',
        '--bg-subtractor',
        metavar='type',
        type=string_type_check(['MOG2', 'CNT', 'MOG2_CUDA'], False, 'type'),
        help=('The type of background subtractor to use, must be one of: '
              ' MOG2 (default), CNT (parallel), MOG2_CUDA (Nvidia GPU).%s') %
        user_config.get_help_string('bg-subtractor'),
    )

    parser.add_argument(
        '-t',
        '--threshold',
        metavar='value',
        type=float_type_check(0.0, None, 'value'),
        help=('Threshold representing amount of motion in a frame required to trigger'
              ' motion events. Lower values are more sensitive to motion. If too high,'
              ' some movement in the scene may not be detected, while too low of a'
              ' threshold can result in false detections.%s' %
              (user_config.get_help_string('threshold'))),
    )

    parser.add_argument(
        '-k',
        '--kernel-size',
        metavar='size',
        type=_kernel_size_type_check(metavar='size'),
        help=('Size in pixels of the noise reduction kernel. Must be odd number greater than 1, '
              '0 to disable, or -1 to auto-set based on video resolution (default). If the kernel '
              'size is set too large, some movement in the scene may not be detected.%s' %
              (user_config.get_help_string('kernel-size'))),
    )

    parser.add_argument(
        '-l',
        '--min-event-length',
        metavar='time',
        type=timecode_type_check('time'),
        help=('Length of time that must contain motion before triggering a new event. Can be'
              ' specified as frames (123), seconds (12.3s), or timecode (00:00:01).%s' %
              user_config.get_help_string('min-event-length')),
    )

    parser.add_argument(
        '-tb',
        '--time-before-event',
        metavar='time',
        type=timecode_type_check('time'),
        help=('Maximum amount of time to include before each event. Can be specified as'
              ' frames (123), seconds (12.3s), or timecode (00:00:01).%s' %
              user_config.get_help_string('time-before-event')),
    )

    parser.add_argument(
        '-tp',
        '--time-post-event',
        metavar='time',
        type=timecode_type_check('time'),
        help=('Maximum amount of time to include after each event. The event will end once no'
              ' motion has been detected for this period of time. Can be specified as frames (123),'
              ' seconds (12.3s), or timecode (00:00:01).%s' %
              user_config.get_help_string('time-post-event')),
    )

    parser.add_argument(
        '-st',
        '--start-time',
        metavar='time',
        type=timecode_type_check('time'),
        help=('Time to seek to in video before performing detection. Can be'
              ' given in number of frames (12345), seconds (number followed'
              ' by s, e.g. 123s or 123.45s), or timecode (HH:MM:SS[.nnn]).'),
    )

    parser.add_argument(
        '-dt',
        '--duration',
        metavar='time',
        type=timecode_type_check('time'),
        help=('Duration stop processing the input after (see -st for valid timecode formats).'
              ' Overrides -et.'),
    )

    parser.add_argument(
        '-et',
        '--end-time',
        metavar='time',
        type=timecode_type_check('time'),
        help=('Timecode to stop processing the input (see -st for valid timecode formats).'),
    )

    # TODO(v2.0): Remove -roi (replaced by -r/--region-editor and -a/--add-region).
    parser.add_argument(
        '-roi',
        '--region-of-interest',
        dest='region_of_interest',
        metavar='x0 y0 w h',
        nargs='*',
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        '-bb',
        '--bounding-box',
        metavar='smooth_time',
        type=timecode_type_check('smooth_time'),
        nargs='?',
        const=False,
        help=('If set, draws a bounding box around the area where motion was detected. The amount'
              ' of temporal smoothing can be specified in either frames (12345) or seconds (number'
              ' followed by s, e.g. 123s or 123.45s). If omitted, defaults to 0.1s. If set to 0,'
              ' smoothing is disabled.%s' %
              (user_config.get_help_string('bounding-box', show_default=False))),
    )

    parser.add_argument(
        '-tc',
        '--time-code',
        action='store_true',
        help=('Draw time code in top left corner of each frame.%s' %
              user_config.get_help_string('time-code', show_default=False)),
    )

    parser.add_argument(
        '-fm',
        '--frame-metrics',
        action='store_true',
        help=('Draw frame metrics in top right corner of each frame.%s' %
              user_config.get_help_string('frame-metrics', show_default=False)),
    )

    parser.add_argument(
        '-mo',
        '--mask-output',
        metavar='motion_mask.avi',
        type=str,
        help=('Write a video containing the motion mask of each frame. Useful when tuning '
              'detection parameters.'),
    )

    parser.add_argument(
        '-df',
        '--downscale-factor',
        metavar='factor',
        type=int_type_check(0, None, 'factor'),
        help=('Integer factor to downscale (shrink) video before processing, to'
              ' improve performance. For example, if input video resolution'
              ' is 1024 x 400, and factor=2, each frame is reduced to'
              ' 1024/2 x 400/2=512 x 200 before processing.%s' %
              (user_config.get_help_string('downscale-factor'))),
    )

    parser.add_argument(
        '-fs',
        '--frame-skip',
        metavar='num_frames',
        type=int_type_check(0, None, 'num_frames'),
        help=('Number of frames to skip after processing a given frame.'
              ' Improves performance, at expense of frame and time accuracy,'
              ' and may increase probability of missing motion events.'
              ' If set, -l, -tb, and -tp will all be scaled relative to the source'
              ' framerate. Values above 1 or 2 are not recommended.%s' %
              (user_config.get_help_string('frame-skip'))),
    )
    parser.add_argument(
        '-q',
        '--quiet',
        dest='quiet_mode',
        action='store_true',
        help=('Suppress all output except for final comma-separated list of motion events.'
              ' Useful for computing or piping output directly into other programs/scripts.%s' %
              user_config.get_help_string('quiet-mode')),
    )

    # Options that only take long-form.

    parser.add_argument(
        '--logfile',
        metavar='file',
        type=str,
        help=('Path to log file for writing application output. If FILE already exists, the program'
              ' output will be appended to the existing contents.'),
    )

    parser.add_argument(
        '-v',
        '--verbosity',
        metavar='type',
        type=string_type_check(CHOICE_MAP['verbosity'], False, 'type'),
        help=('Amount of verbosity to use for log output. Must be one of: %s.%s' %
              (', '.join(CHOICE_MAP['verbosity']), user_config.get_help_string('verbosity'))),
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help=argparse.SUPPRESS,
        default=False,
    )

    # TODO: Support both input and output concatenation in ffmpeg mode. For concatenating events,
    # we can still encode files for each event, and then join them with ffmpeg's codec copying
    # mode as a final pass. Can also add a config param to keep the events.

    # TODO: Add a mode that can dump frame scores (-s/--stats), and another mode
    # that can dump the resulting frames after processing (-d/--dump-motion OUT.avi).
    # Might also be helpful to overlay the frame score when using -d. Multiply the motion
    # mask against the input image.

    return parser
