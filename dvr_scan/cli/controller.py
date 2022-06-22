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

import os
import os.path
import sys
import logging

from scenedetect import VideoOpenFailure

import dvr_scan
from dvr_scan.cli import get_cli_parser
from dvr_scan.cli.config import ConfigRegistry, ConfigLoadFailure
from dvr_scan.scanner import DetectorType, ScanContext
from dvr_scan.platform import init_logger

logger = logging.getLogger('dvr_scan')


def validate_cli_args(args):
    """ Validates command line options, returning a boolean indicating if the validation succeeded,
    and a set of validated options. """
    for file in args.input:
        if not os.path.exists(file):
            logger.error("Error: Input file does not exist:\n  %s", file)
            return False, None
    if hasattr(args, 'output') and not '.' in args.output:
        args.output += '.avi'
    if args.kernel_size < 0:
        args.kernel_size = None
    try:
        args.bg_subtractor = DetectorType[args.bg_subtractor.upper()]
    except KeyError:
        logger.error('Error: Unknown background subtraction type: %s', args.bg_subtractor)
        return False, None
    return True, args


def run_dvr_scan():
    """Entry point for running DVR-Scan.

    Handles high-level interfacing of video IO and motion event detection.

    Returns:
        0 on successful termination, non-zero otherwise.
    """
    args = None
    config_load_failure = False
    init_log = []

    try:
        user_config = ConfigRegistry()
        verbosity = getattr(logging, user_config.get_value('program', 'verbosity').upper())
        init_logger(
            log_level=verbosity,
            show_stdout=not user_config.get_value('program', 'quiet_mode'),
        )
        args = get_cli_parser(user_config).parse_args()

        verbosity = args.verbosity if hasattr(args, 'verbosity') else user_config.get_value(
            'program', 'verbosity')
        verbosity = getattr(logging, verbosity.upper())
        quiet_mode = (True if hasattr(args, 'quiet_mode') else user_config.get_value(
            'program', 'quiet_mode'))
        if not hasattr(args, 'config') or verbosity == logging.DEBUG:
            init_log += user_config.get_init_log()
        if hasattr(args, 'config'):
            user_config = ConfigRegistry(args.config)
            init_log += user_config.get_init_log()

        # If verbosity is debug, override -q/--quiet if it was not specified.
        if verbosity == logging.DEBUG and not hasattr(args, 'quiet_mode'):
            quiet_mode = False
        # Re-initialize logger with correct verbosity/quiet_mode setting.
        init_logger(
            log_level=verbosity,
            show_stdout=not quiet_mode,
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
            return 1

    if user_config.config_dict:
        logger.debug("Current configuration:\n%s", str(user_config.config_dict))
    logger.debug('Parsing program options.')
    # Validate arguments and then continue.
    validated, args = validate_cli_args(args)
    if not validated:
        return 1

    try:
        if not args.bg_subtractor.value.is_available():
            logger.error(
                'Method %s is not available. To enable it, install a version of'
                ' the OpenCV package `cv2` that includes it.', args.bg_subtractor.name)
            sys.exit(1)

        sctx = ScanContext(
            input_videos=args.input,
            frame_skip=args.frame_skip,
            show_progress=not quiet_mode,
        )

        # Set context properties based on CLI arguments.

        sctx.set_output(
            scan_only=args.scan_only_mode,
            comp_file=args.output if hasattr(args, 'output') else None,
            codec=args.fourcc_str,
        )

        sctx.set_overlays(
            draw_timecode=args.draw_timecode,
            bounding_box_smoothing=args.bounding_box,
        )

        sctx.set_detection_params(
            threshold=args.threshold,
            kernel_size=args.kernel_size,
            downscale_factor=args.downscale_factor,
            roi=args.roi,
        )

        sctx.set_event_params(
            min_event_len=args.min_event_len,
            time_pre_event=args.time_pre_event,
            time_post_event=args.time_post_event,
        )

        sctx.set_video_time(
            start_time=args.start_time,
            end_time=args.end_time,
            duration=args.duration,
        )

        sctx.scan_motion(detector_type=args.bg_subtractor)

    except VideoOpenFailure as ex:
        # Error information is logged in ScanContext when this exception is raised.
        logger.error('Failed to load input: %s', ex)
        return 1

    except ValueError as ex:
        logger.error(ex)
        return 1

    return 0
