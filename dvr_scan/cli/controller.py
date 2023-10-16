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
""" ``dvr_scan.cli.controller`` Module

This module manages the DVR-Scan program control flow, starting with `run_dvr_scan()`.
"""

import argparse
import glob
import logging
import sys
import time
import typing as ty

from scenedetect import FrameTimecode

import dvr_scan
from dvr_scan.cli import get_cli_parser
from dvr_scan.cli.config import ConfigRegistry, ConfigLoadFailure, RegionValueDeprecated
from dvr_scan.overlays import TextOverlay, BoundingBoxOverlay
from dvr_scan.scanner import DetectorType, OutputMode, MotionScanner
from dvr_scan.platform import init_logger

logger = logging.getLogger('dvr_scan')


class ProgramSettings:
    """Contains the active command-line and config file settings."""

    def __init__(self, args: argparse.Namespace, config: ConfigRegistry):
        self._args = args
        self._config = config

    @property
    def config(self) -> ConfigRegistry:
        return self._config

    def get_arg(self, arg: str) -> ty.Optional[ty.Any]:
        """Get setting specified via command line argument, if any."""
        arg_name = arg.replace('-', '_')
        return getattr(self._args, arg_name) if hasattr(self._args, arg_name) else None

    def get(self, option: str) -> ty.Union[str, int, float, bool]:
        """Get setting based on following resolution order:
            1. Argument specified via command line.
            2. Option set in the active config file (either explicit with -c/--config, or
               the dvr-scan.cfg file in the user's settings folder).
            3. Default value specified in the config map (`dvr_scan.cli.config.CONFIG_MAP`).
        """
        arg_val = self.get_arg(option)
        if arg_val is not None:
            return arg_val
        return self.config.get_value(option)


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
    # -roi/--region-of-interest
    if hasattr(args, 'region_of_interest') and args.region_of_interest:
        original_roi = args.region_of_interest
        try:
            args.region_of_interest = RegionValueDeprecated(
                value=' '.join(original_roi), allow_size=True).value
        except ValueError:
            logger.error(
                'Error: Invalid value for ROI: %s. ROI must be specified as a rectangle of'
                ' the form `x,y,w,h` or the max window size `w,h` (commas/spaces are ignored).'
                ' For example: -roi 200,250 50,100', ' '.join(original_roi))
            return False, None
    return True, args


def _init_logging(args: ty.Optional[argparse.ArgumentParser], config: ty.Optional[ProgramSettings]):
    verbosity = logging.INFO
    if args is not None and hasattr(args, 'verbosity'):
        verbosity = getattr(logging, args.verbosity.upper())
    elif config is not None:
        verbosity = getattr(logging, config.get_value('verbosity').upper())

    quiet_mode = False
    if args is not None and hasattr(args, 'quiet_mode'):
        quiet_mode = args.quiet_mode
    elif config is not None:
        quiet_mode = config.get_value('quiet-mode')

    init_logger(
        log_level=verbosity,
        show_stdout=not quiet_mode,
        log_file=args.logfile if hasattr(args, 'logfile') else None,
    )


def parse_settings(args: ty.List[str] = None) -> ty.Optional[ProgramSettings]:
    """Parse command line options and load config file settings."""
    init_log = []
    config_load_error = None
    failed_to_load_config = False
    debug_mode = False
    config = ConfigRegistry()
    # Try to load config from user settings folder.
    try:
        user_config = ConfigRegistry()
        user_config.load()
        config = user_config
    except ConfigLoadFailure as ex:
        config_load_error = ex
    _init_logging(args, config)
    # Parse CLI args, override config if an override was specified on the command line.
    try:
        args = get_cli_parser(config).parse_args(args=args)
        debug_mode = args.debug
        _init_logging(args, config)
        init_log += [(logging.INFO, 'DVR-Scan %s' % dvr_scan.__version__)]
        if config_load_error and not hasattr(args, 'config'):
            raise config_load_error
        if debug_mode:
            init_log += config.consume_init_log()
        if hasattr(args, 'config'):
            config_setting = ConfigRegistry()
            config_setting.load(args.config)
            _init_logging(args, config_setting)
            config = config_setting
        init_log += config.consume_init_log()
    except ConfigLoadFailure as ex:
        init_log += ex.init_log
        if ex.reason is not None:
            init_log += [(logging.ERROR, 'Error: %s' % str(ex.reason).replace('\t', '  '))]
        failed_to_load_config = True
        config_load_error = ex
    finally:
        for (log_level, log_str) in init_log:
            logger.log(log_level, log_str)
        if failed_to_load_config:
            logger.critical('Failed to load config file.')
            logger.debug('Error loading config file:', exc_info=config_load_error)
            if debug_mode:
                raise config_load_error
            return None

    if config.config_dict:
        logger.debug("Loaded configuration:\n%s", str(config.config_dict))

    validated, args = _preprocess_args(args)
    if not validated:
        return None
    logger.debug("Program arguments:\n%s", str(args))
    settings = ProgramSettings(args=args, config=config)

    # Validate that the specified motion detector is available on this system.
    try:
        detector_type = settings.get('bg-subtractor')
        bg_subtractor = DetectorType[detector_type.upper()]
    except KeyError:
        logger.error('Error: Unknown background subtraction type: %s', detector_type)
        return None
    if not bg_subtractor.value.is_available():
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # This should only happen for MOG2_CUDA (currently).
            assert bg_subtractor == DetectorType.MOG2_CUDA
            logger.error(
                "Method %s is not available. To enable it, use a CUDA-enabled build of DVR-Scan.",
                bg_subtractor.name)
        else:
            logger.error(
                "Method %s is not available. To enable CNT, you can try `pip install "
                "opencv-contrib-python`. MOG2_CUDA requires building OpenCV with Python and CUDA "
                "support enabled.", bg_subtractor.name)
        return None

    return settings


# TODO: Along with the TODO ontop of MotionScanner, the actual conversion from the ProgramSetting
# to the option in MotionScanner should be done via properties, e.g. make a property in
# ProgramSettings called 'output_dir' that just returns settings.get('output_dir'). These can then
# be directly referenced from the MotionScanner.
def run_dvr_scan(settings: ProgramSettings) -> ty.List[ty.Tuple[FrameTimecode, FrameTimecode]]:
    """Run DVR-Scan scanning logic using validated `settings` from `parse_settings()`."""

    logger.info("Initializing scan context...")
    scanner = MotionScanner(
        input_videos=settings.get_arg('input'),
        frame_skip=settings.get('frame-skip'),
        show_progress=not settings.get('quiet-mode'),
        debug_mode=settings.get('debug'),
    )

    output_mode = (
        OutputMode.SCAN_ONLY if settings.get_arg('scan-only') else settings.get('output-mode'))
    scanner.set_output(
        comp_file=settings.get_arg('output'),
        mask_file=settings.get_arg('mask-output'),
        output_mode=output_mode,
        opencv_fourcc=settings.get('opencv-codec'),
        ffmpeg_input_args=settings.get('ffmpeg-input-args'),
        ffmpeg_output_args=settings.get('ffmpeg-output-args'),
        output_dir=settings.get('output-dir'),
    )

    timecode_overlay = None
    if settings.get('time-code'):
        timecode_overlay = TextOverlay(
            font_scale=settings.get('text-font-scale'),
            margin=settings.get('text-margin'),
            border=settings.get('text-border'),
            thickness=settings.get('text-font-thickness'),
            color=settings.get('text-font-color'),
            bg_color=settings.get('text-bg-color'),
            corner=TextOverlay.Corner.TopLeft,
        )

    metrics_overlay = None
    if settings.get('frame-metrics'):
        metrics_overlay = TextOverlay(
            font_scale=settings.get('text-font-scale'),
            margin=settings.get('text-margin'),
            border=settings.get('text-border'),
            thickness=settings.get('text-font-thickness'),
            color=settings.get('text-font-color'),
            bg_color=settings.get('text-bg-color'),
            corner=TextOverlay.Corner.TopRight,
        )

    bounding_box = None
    # bounding_box_arg will be None if -bb was not set, False if -bb was set without any args,
    # otherwise it represents the desired smooth time.
    bounding_box_arg = settings.get_arg('bounding-box')
    if bounding_box_arg is not None or settings.get('bounding-box'):
        if bounding_box_arg is not None and bounding_box_arg is not False:
            smoothing_time = FrameTimecode(bounding_box_arg, scanner.framerate)
        else:
            smoothing_time = FrameTimecode(
                settings.get('bounding-box-smooth-time'), scanner.framerate)
        bounding_box = BoundingBoxOverlay(
            min_size_ratio=settings.get('bounding-box-min-size'),
            thickness_ratio=settings.get('bounding-box-thickness'),
            color=settings.get('bounding-box-color'),
            smoothing=smoothing_time.frame_num,
        )

    scanner.set_overlays(
        timecode_overlay=timecode_overlay,
        metrics_overlay=metrics_overlay,
        bounding_box=bounding_box,
    )

    scanner.set_detection_params(
        detector_type=DetectorType[settings.get('bg-subtractor').upper()],
        threshold=settings.get('threshold'),
        max_threshold=settings.get('max-threshold'),
        kernel_size=settings.get('kernel-size'),
        downscale_factor=settings.get('downscale-factor'),
    )

    scanner.set_event_params(
        min_event_len=settings.get('min-event-length'),
        time_pre_event=settings.get('time-before-event'),
        time_post_event=settings.get('time-post-event'),
    )

    scanner.set_video_time(
        start_time=settings.get_arg('start-time'),
        end_time=settings.get_arg('end-time'),
        duration=settings.get_arg('duration'),
    )

    # If the user specified some regions on the command line, ignore the load-regions setting in the
    # config file.
    load_region = settings.get_arg('load-region')
    if load_region is None:
        load_region = settings.config.get_value('load-region', ignore_default=True)
        if not settings.get_arg('regions') is None:
            load_region = None

    scanner.set_regions(
        region_editor=settings.get_arg('region-editor'),
        regions=settings.get_arg('regions'),
        load_region=load_region,
        save_region=settings.get_arg('save-region'),
        roi_deprecated=settings.get('region-of-interest'),
    )

    # Scan video for motion with specified parameters.
    processing_start = time.time()
    result = scanner.scan()
    if result is None:
        logging.debug("Exiting early, scan() returned None.")
        return
    processing_time = time.time() - processing_start
    # Display results and performance.

    processing_rate = float(result.num_frames) / processing_time
    logger.info("Processed %d frames read in %3.1f secs (avg %3.1f FPS).", result.num_frames,
                processing_time, processing_rate)
    if not result.event_list:
        logger.info("No motion events detected in input.")
        return
    logger.info("Detected %d motion events in input.", len(result.event_list))
    if result.event_list:
        output_strs = [
            "-------------------------------------------------------------",
            "|   Event #    |  Start Time  |   Duration   |   End Time   |",
            "-------------------------------------------------------------"
        ]
        output_strs += [
            "|  Event %4d  |  %s  |  %s  |  %s  |" % (
                i + 1,
                event.start.get_timecode(precision=1),
                (event.end - event.start).get_timecode(precision=1),
                event.end.get_timecode(precision=1),
            ) for i, event in enumerate(result.event_list)
        ]
        output_strs += ["-------------------------------------------------------------"]
        logger.info("List of motion events:\n%s", '\n'.join(output_strs))
        timecode_list = []
        for event in result.event_list:
            timecode_list.append(event.start.get_timecode())
            timecode_list.append(event.end.get_timecode())
        logger.info("Comma-separated timecode values:")
        # Print values regardless of quiet mode or not.
        # TODO: This should not print in quiet mode, it should go through the logger.
        # TODO(#78): Fix this output format to be more usable, in the form:
        # start1-end1[,[+]start2-end2[,[+]start3-end3...]]
        print(','.join(timecode_list))

    if output_mode != OutputMode.SCAN_ONLY:
        logger.info("Motion events written to disk.")
