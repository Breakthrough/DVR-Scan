# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Copyright (C) 2014-2022 Brandon Castellano <http://www.bcastell.com>.
# PySceneDetect is licensed under the BSD 2-Clause License; see the
# included LICENSE file, or visit one of the above pages for details.
#
""" ``dvr_scan.cli.controller`` Module

This module manages the DVR-Scan program control flow, starting with `run_dvr_scan()`.
"""

import argparse
import glob
import logging
from typing import Any, Optional

from scenedetect import FrameTimecode, VideoOpenFailure

import dvr_scan
from dvr_scan.cli import get_cli_parser
from dvr_scan.cli.config import ConfigRegistry, ConfigLoadFailure, ROIValue
from dvr_scan.overlays import TextOverlay, BoundingBoxOverlay
from dvr_scan.scanner import DetectorType, OutputMode, ScanContext
from dvr_scan.platform import init_logger

logger = logging.getLogger('dvr_scan')

EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1


class ProgramSettings:
    """Contains the active command-line and config file settings."""

    def __init__(self, args: argparse.Namespace, config: ConfigRegistry):
        self._args = args
        self._config = config

    def get_arg(self, arg: str) -> Optional[Any]:
        """Get setting specified via command line argument, if any."""
        arg_name = arg.replace('-', '_')
        return getattr(self._args, arg_name) if hasattr(self._args, arg_name) else None

    def get(self, option: str, arg: Optional[str] = None) -> Any:
        """Get setting based on following resolution order:
            1. Argument specified via command line.
            2. Option set in the active config file (either explicit with -c/--config, or
               the dvr-scan.cfg file in the user's settings folder).
            3. Default value specified in the config map (`dvr_scan.cli.config.CONFIG_MAP`).
        """
        arg_val = self.get_arg(option if arg is None else arg)
        if arg_val is not None:
            return arg_val
        return self._config.get_value(option)


def _preprocess_args(args):
    """Perform some preprocessing and validation of command line arguments, returning a
    boolean indicating if the validation succeeded, and the set of validated arguments."""
    # -i/--input
    # Each entry in args.input is a list of paths or globs we need to expand and combine.
    input_files = []
    for files in args.input:
        for file in files:
            expanded = glob.glob(file)
            if not expanded:
                logger.error("Error: Input file does not exist:\n  %s", file)
                return False, None
            input_files += expanded
    args.input = input_files
    # -o/--output
    if hasattr(args, 'output') and not '.' in args.output:
        args.output += '.avi'
    # -k/--kernel-size
    if hasattr(args, 'kernel_size') and args.kernel_size < 0:
        args.kernel_size = None
    # -roi/--region-of-interest
    if hasattr(args, 'region_of_interest') and args.region_of_interest:
        original_roi = args.region_of_interest
        try:
            args.region_of_interest = ROIValue(value=' '.join(original_roi), allow_point=True).value
        except ValueError:
            logger.error(
                'Error: Invalid value for ROI: %s. ROI must be specified as a rectangle of'
                ' the form `x,y,w,h` or the max window size `w,h` (commas/spaces are ignored).'
                ' For example: -roi 200,250 50,100', ' '.join(original_roi))
            return False, None
    return True, args


def _init_dvr_scan() -> Optional[ProgramSettings]:
    """Parse command line options and load config file settings."""
    args = None
    config_load_failure = False
    init_log = []

    try:
        # Try to load the user config file and parse the CLI arguments.
        user_config = ConfigRegistry()
        verbosity = getattr(logging, user_config.get_value('verbosity').upper())
        init_logger(
            log_level=verbosity,
            show_stdout=not user_config.get_value('quiet-mode'),
        )
        args = get_cli_parser(user_config).parse_args()

        # Always include all log information in debug mode, otherwise if a config file path
        # was given, suppress the init log since we'll re-init the config registry below.
        debug_mode = hasattr(args, 'verbosity') and args.verbosity.upper() == 'DEBUG'
        if not hasattr(args, 'config') or debug_mode:
            init_log += user_config.get_init_log()

        # Re-initialize the config registry if the user specified a config file.
        if hasattr(args, 'config'):
            user_config = ConfigRegistry(args.config)
            init_log += user_config.get_init_log()

        # Get final verbosity setting and convert string to the constant in the `logging` module.
        verbosity_setting: str = (
            args.verbosity if hasattr(args, 'verbosity') else user_config.get_value('verbosity'))
        verbosity: int = getattr(logging, verbosity_setting.upper())
        # If verbosity is DEBUG, override the quiet mode option unless -q/--quiet was set.
        if not hasattr(args, 'quiet-mode'):
            args.quiet_mode = (False if verbosity == logging.DEBUG else
                               user_config.get_value('quiet-mode'))

        # Re-initialize logger with final quiet mode/verbosity settings.
        init_logger(
            log_level=verbosity,
            show_stdout=not args.quiet_mode,
            log_file=args.logfile if hasattr(args, 'logfile') else None,
        )

    except ConfigLoadFailure as ex:
        config_load_failure = True
        init_log += ex.init_log
        if ex.reason is not None:
            init_log += [(logging.ERROR, 'Error: %s' % str(ex.reason).replace('\t', '  '))]
    finally:
        if args is not None or (args is None and config_load_failure):
            # As CLI parsing errors are printed first, we only print the version if the
            # args were parsed correctly, or if we fail to load the config file.
            logger.info('DVR-Scan %s', dvr_scan.__version__)
        for (log_level, log_str) in init_log:
            logger.log(log_level, log_str)
        if config_load_failure:
            logger.critical("Failed to load configuration file.")
            # There is nowhere else to propagatge the exception to, and we've already
            # logged the error information above.
            #pylint: disable=lost-exception
            return None

    if user_config.config_dict:
        logger.debug("Current configuration:\n%s", str(user_config.config_dict))
    logger.debug('Parsing program options.')
    # Validate arguments and then continue.
    validated, args = _preprocess_args(args)
    if not validated:
        return None

    return ProgramSettings(args=args, config=user_config)


def run_dvr_scan():
    """Entry point for running DVR-Scan.

    Handles high-level interfacing of video IO and motion event detection.

    Returns:
        0 on successful termination, non-zero otherwise.
    """
    # Parse command-line options and config file settings.
    settings = _init_dvr_scan()
    if settings is None:
        return EXIT_ERROR

    # Validate that the specified motion detector is available on this system.
    try:
        detector_type = settings.get('bg-subtractor')
        bg_subtractor = DetectorType[detector_type.upper()]
    except KeyError:
        logger.error('Error: Unknown background subtraction type: %s', detector_type)
        return EXIT_ERROR
    if not bg_subtractor.value.is_available():
        logger.error(
            'Method %s is not available. To enable it, install a version of'
            ' the OpenCV package `cv2` that includes it.', bg_subtractor.name)
        return EXIT_ERROR

    # TODO(v1.5): If the specified output mode is not available on the system, display
    # a more graceful error message.

    try:
        # Create ScanContext using the
        sctx = ScanContext(
            input_videos=settings.get_arg('input'),
            frame_skip=settings.get('frame-skip'),
            show_progress=not settings.get('quiet-mode'),
        )

        # Set context properties based on CLI arguments.

        sctx.set_output(
            comp_file=settings.get_arg('output'),
            mask_file=settings.get_arg('mask_output'),
            output_mode=(OutputMode.SCAN_ONLY
                         if settings.get_arg('scan_only') else settings.get('output-mode')),
            opencv_fourcc=settings.get('opencv-codec'),
            ffmpeg_output_args=settings.get('ffmpeg-output-args'),
            output_dir=settings.get('output-dir'),
        )

        timecode_overlay = None
        if settings.get_arg('draw-timecode') or settings.get('timecode'):
            timecode_overlay = TextOverlay(
                font_scale=settings.get('timecode-font-scale'),
                margin=settings.get('timecode-margin'),
                thickness=settings.get('timecode-font-thickness'),
                color=settings.get('timecode-font-color'),
                bg_color=settings.get('timecode-bg-color'),
            )

        bounding_box = None
        # bounding_box_arg will be None if -bb was not set, False if -bb was set without any args,
        # otherwise it represents the desired smooth time.
        bounding_box_arg = settings.get_arg('bounding-box')
        if bounding_box_arg is not None or settings.get('bounding-box'):
            if bounding_box_arg is not None and bounding_box_arg is not False:
                smoothing_time = FrameTimecode(bounding_box_arg, sctx.framerate)
            else:
                smoothing_time = FrameTimecode(
                    settings.get('bounding-box-smooth-time'), sctx.framerate)
            bounding_box = BoundingBoxOverlay(
                min_size_ratio=settings.get('bounding-box-min-size'),
                thickness_ratio=settings.get('bounding-box-thickness'),
                color=settings.get('bounding-box-color'),
                smoothing=smoothing_time.frame_num,
            )

        sctx.set_overlays(
            timecode_overlay=timecode_overlay,
            bounding_box=bounding_box,
        )

        sctx.set_detection_params(
            threshold=settings.get('threshold'),
            kernel_size=settings.get('kernel-size'),
            downscale_factor=settings.get('downscale-factor'),
            roi=settings.get('region-of-interest'),
        )

        sctx.set_event_params(
            min_event_len=settings.get('min-event-length'),
            time_pre_event=settings.get('time-before-event'),
            time_post_event=settings.get('time-post-event'),
        )

        sctx.set_video_time(
            start_time=settings.get_arg('start-time'),
            end_time=settings.get_arg('end-time'),
            duration=settings.get_arg('duration'),
        )

        # Run motion detection.
        sctx.scan_motion(detector_type=bg_subtractor)

    except VideoOpenFailure as ex:
        # Error information is logged in ScanContext when this exception is raised.
        logger.error('Failed to load input: %s', ex)
        return EXIT_ERROR

    except ValueError as ex:
        logger.error(ex)
        return EXIT_ERROR

    except KeyboardInterrupt as ex:
        logger.debug("KeyboardInterrupt received, quitting.")
        return EXIT_ERROR

    return EXIT_SUCCESS
