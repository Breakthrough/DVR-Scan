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

This file contains the implementation of the DVR-Scan command-line logic.
"""

import argparse
import os
import os.path
import logging
from typing import Any, Optional

from scenedetect import FrameTimecode, VideoOpenFailure

import dvr_scan
from dvr_scan.cli import get_cli_parser
from dvr_scan.cli.config import ConfigRegistry, ConfigLoadFailure, ROIValue
from dvr_scan.overlays import TextOverlay, BoundingBoxOverlay
from dvr_scan.scanner import DetectorType, ScanContext
from dvr_scan.platform import init_logger

logger = logging.getLogger('dvr_scan')

INIT_FAILURE_EXIT_CODE: int = 1


class ProgramContext:
    """Contains the context of DVR-Scan's user options."""

    def __init__(self, args: argparse.Namespace, config: ConfigRegistry):
        self._args = args
        self._config = config

    def get_arg(self, arg: str) -> Optional[Any]:
        """Get option specified via command line, if any."""
        arg_name = arg.replace('-', '_')
        return getattr(self._args, arg_name) if hasattr(self._args, arg_name) else None

    def get_option(self, section: str, option: str) -> Any:
        """Get user-specified option based on following resolution order:
            1. Get option if set on command line.
            2. Get option if set in the config file being used (either explicit with -c/--config,
               or the dvr-scan.cfg file in the user's settings folder).
            3. Get default value.
        """
        arg = self.get_arg(option)
        if arg is not None:
            return arg
        return self._config.get_value(section=section, option=option)


def _validate_cli_args(args):
    """ Validates command line options, returning a boolean indicating if the validation succeeded,
    and a set of validated options. """
    # -i/--input
    for file in args.input:
        if not os.path.exists(file):
            logger.error("Error: Input file does not exist:\n  %s", file)
            return False, None
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


def _init_dvr_scan() -> Optional[ProgramContext]:
    args = None
    config_load_failure = False
    init_log = []

    try:
        # Try to load the user config file and parse the CLI arguments.
        user_config = ConfigRegistry()
        verbosity = getattr(logging, user_config.get_value('program', 'verbosity').upper())
        init_logger(
            log_level=verbosity,
            show_stdout=not user_config.get_value('program', 'quiet-mode'),
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

        # Get final verbosity setting.
        verbosity = args.verbosity if hasattr(args, 'verbosity') else user_config.get_value(
            'program', 'verbosity')
        verbosity = getattr(logging, verbosity.upper())
        # If verbosity is DEBUG, override the quiet mode option unless -q/--quiet was set.
        if not hasattr(args, 'quiet-mode'):
            args.quiet_mode = False if verbosity == logging.DEBUG else user_config.get_value(
                'program', 'quiet-mode')

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
    validated, args = _validate_cli_args(args)
    if not validated:
        return None

    return ProgramContext(args=args, config=user_config)


def run_dvr_scan():
    """Entry point for running DVR-Scan.

    Handles high-level interfacing of video IO and motion event detection.

    Returns:
        0 on successful termination, non-zero otherwise.
    """
    context = _init_dvr_scan()
    if context is None:
        return INIT_FAILURE_EXIT_CODE

    try:
        detector_type = context.get_option('detection', 'bg-subtractor')
        bg_subtractor = DetectorType[detector_type.upper()]
    except KeyError:
        logger.error('Error: Unknown background subtraction type: %s', detector_type)
        return INIT_FAILURE_EXIT_CODE
    if not bg_subtractor.value.is_available():
        logger.error(
            'Method %s is not available. To enable it, install a version of'
            ' the OpenCV package `cv2` that includes it.', bg_subtractor.name)
        return INIT_FAILURE_EXIT_CODE

    try:
        sctx = ScanContext(
            input_videos=context.get_arg('input'),
            frame_skip=context.get_option('detection', 'frame-skip'),
            show_progress=not context.get_option('program', 'quiet-mode'),
        )

        # Set context properties based on CLI arguments.

        sctx.set_output(
            scan_only=context.get_arg('scan_only'),
            comp_file=context.get_arg('output'),
            codec=context.get_option('program', 'opencv-codec'),
        )

        timecode_overlay = None
        if context.get_arg('draw-timecode') or context.get_option('overlays', 'timecode'):
            timecode_overlay = TextOverlay(
                font_scale=context.get_option('overlays', 'timecode-font-scale'),
                margin=context.get_option('overlays', 'timecode-margin'),
                thickness=context.get_option('overlays', 'timecode-font-thickness'),
                color=context.get_option('overlays', 'timecode-font-color'),
                bg_color=context.get_option('overlays', 'timecode-bg-color'),
            )

        bounding_box = None
        # None if -bb was not set, False if -bb was provided without any args, otherwise smooth time.
        bounding_box_arg = context.get_arg('bounding-box')
        if bounding_box_arg is not None or context.get_option('overlays', 'bounding-box'):
            if bounding_box_arg is not None and bounding_box_arg is not False:
                smoothing_time = FrameTimecode(context.get_arg('bounding-box'), sctx.framerate)
            else:
                smoothing_time = FrameTimecode(
                    context.get_option('overlays', 'bounding-box-smooth-time'), sctx.framerate)
            bounding_box = BoundingBoxOverlay(
                min_size_ratio=context.get_option('overlays', 'bounding-box-min-size'),
                thickness_ratio=context.get_option('overlays', 'bounding-box-thickness'),
                color=context.get_option('overlays', 'bounding-box-color'),
                smoothing=smoothing_time.frame_num,
            )

        sctx.set_overlays(
            timecode_overlay=timecode_overlay,
            bounding_box=bounding_box,
        )

        sctx.set_detection_params(
            threshold=context.get_option('detection', 'threshold'),
            kernel_size=context.get_option('detection', 'kernel-size'),
            downscale_factor=context.get_option('detection', 'downscale-factor'),
            roi=context.get_option('detection', 'region-of-interest'),
        )

        sctx.set_event_params(
            min_event_len=context.get_option('detection', 'min-event-length'),
            time_pre_event=context.get_option('detection', 'time-before-event'),
            time_post_event=context.get_option('detection', 'time-post-event'),
        )

        sctx.set_video_time(
            start_time=context.get_arg('start-time'),
            end_time=context.get_arg('end-time'),
            duration=context.get_arg('duration'),
        )

        sctx.scan_motion(detector_type=bg_subtractor)

    except VideoOpenFailure as ex:
        # Error information is logged in ScanContext when this exception is raised.
        logger.error('Failed to load input: %s', ex)
        return 1

    except ValueError as ex:
        logger.error(ex)
        return 1

    return 0
