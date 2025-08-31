#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""``dvr_scan.controller`` Module

This module manages the DVR-Scan program control flow, starting with `run_dvr_scan()`.
"""

import logging
import time
import typing as ty
from pathlib import Path

from scenedetect import FrameTimecode

import dvr_scan
from dvr_scan.cli import get_cli_parser
from dvr_scan.config import ConfigLoadFailure, ConfigRegistry, RegionValueDeprecated
from dvr_scan.scanner import DetectorType, OutputMode
from dvr_scan.shared import ScanSettings, init_logging, init_scanner, logfile_path, setup_logger

logger = logging.getLogger("dvr_scan")

LOGFILE_PATH = logfile_path(name_prefix="dvr-scan")


def _preprocess_args(args):
    """Perform some preprocessing and validation of command line arguments, returning a
    boolean indicating if the validation succeeded, and the set of validated arguments."""
    # -i/--input
    # Each entry in args.input is a list of paths or globs we need to expand and combine.
    input_files = []
    for files in args.input:
        for file in files:
            path = Path(file)
            expanded = list(Path.cwd().glob(file)) if not path.is_absolute() else [path]
            if not expanded:
                logger.error("Error: Input file does not exist:\n  %s", file)
                return False, None
            input_files += expanded
    args.input = input_files
    # -o/--output
    if hasattr(args, "output") and "." not in args.output:
        args.output += ".avi"
    # -roi/--region-of-interest
    if hasattr(args, "region_of_interest") and args.region_of_interest:
        original_roi = args.region_of_interest
        try:
            args.region_of_interest = RegionValueDeprecated(
                value=" ".join(original_roi), allow_size=True
            ).value
        except ValueError:
            logger.error(
                "Error: Invalid value for ROI: %s. ROI must be specified as a rectangle of"
                " the form `x,y,w,h` or the max window size `w,h` (commas/spaces are ignored)."
                " For example: -roi 200,250 50,100",
                " ".join(original_roi),
            )
            return False, None
    return True, args


def parse_settings() -> ty.Optional[ScanSettings]:
    """Parse command line options and load config file settings."""
    # We defer printing the debug log until we know where to put it.
    init_log = []
    failed_to_load_config = True
    debug_mode = False
    config = ConfigRegistry()
    config_load_error = None
    # Try to load config from user settings folder.
    try:
        user_config = ConfigRegistry()
        user_config.load()
        config = user_config
        init_logging(args=None, config=config)
    except ConfigLoadFailure as ex:
        config_load_error = ex
    # Parse CLI args, override config if an override was specified on the command line.
    try:
        args = get_cli_parser(config).parse_args()
        if args.ignore_user_config:
            config_load_error = None
            config = ConfigRegistry()
        debug_mode = args.debug
        init_logging(args=args, config=config)
        init_log += [(logging.INFO, "DVR-Scan %s" % dvr_scan.__version__)]
        if config_load_error and not hasattr(args, "config"):
            raise config_load_error
        if debug_mode:
            init_log += config.consume_init_log()
        if hasattr(args, "config"):
            config_setting = ConfigRegistry()
            config_setting.load(Path(args.config))
            init_logging(args, config_setting)
            config = config_setting
        init_log += config.consume_init_log()
        if config.get("save-log"):
            setup_logger(
                logfile_path=LOGFILE_PATH,
                max_log_files=config.get("max-log-files"),
                name_prefix="dvr-scan",
            )
        failed_to_load_config = False
    except ConfigLoadFailure as ex:
        failed_to_load_config = True
        config_load_error = ex
        init_log += ex.init_log
        if ex.reason is not None:
            init_log += [(logging.ERROR, "Error: %s" % str(ex.reason).replace("\t", "  "))]
    finally:
        for log_level, log_str in init_log:
            logger.log(log_level, log_str)

    if failed_to_load_config:
        logger.critical("Failed to load config file.")
        logger.debug("Error loading config file:", exc_info=config_load_error)
        if debug_mode:
            raise config_load_error
        # Intentionally suppress the exception in release mode since we've already logged the
        # failure reason to the user above. We can now exit with an error code.
        return None

    if config.config_dict:
        logger.debug("Loaded configuration:\n%s", str(config.config_dict))

    validated, args = _preprocess_args(args)
    if not validated:
        return None
    logger.debug("Program arguments:\n%s", str(args))
    settings = ScanSettings(args=args, config=config)

    # Validate that the specified motion detector is available on this system.
    try:
        detector_type = settings.get("bg-subtractor")
        bg_subtractor = DetectorType[detector_type.upper()]
    except KeyError:
        logger.error("Error: Unknown background subtraction type: %s", detector_type)
        return None
    if not bg_subtractor.value.is_available():
        if bg_subtractor == DetectorType.MOG2_CUDA:
            logger.error("MOG2_CUDA requires a CUDA-enabled build of the `opencv-python` package!")
        else:
            logger.error(
                f"Method {bg_subtractor.name} is not available, you may need to run: "
                "`pip install opencv-contrib-python`"
            )
        return None

    return settings


def run_dvr_scan(
    settings: ScanSettings,
) -> ty.List[ty.Tuple[FrameTimecode, FrameTimecode]]:
    """Run DVR-Scan scanning logic using validated `settings` from `parse_settings()`."""

    scanner = init_scanner(settings)

    # Scan video for motion with specified parameters.
    processing_start = time.time()
    result = scanner.scan()
    if result is None:
        logger.debug("Exiting early, scan() returned None.")
        return
    processing_time = time.time() - processing_start

    # Display results and performance.
    processing_rate = float(result.num_frames) / processing_time
    logger.info(
        "Processed %d frames read in %3.1f secs (avg %3.1f FPS).",
        result.num_frames,
        processing_time,
        processing_rate,
    )
    if not result.event_list:
        logger.info("No motion events detected in input.")
        return
    logger.info("Detected %d motion events in input.", len(result.event_list))
    if result.event_list:
        output_strs = [
            "-------------------------------------------------------------",
            "|   Event #    |  Start Time  |   Duration   |   End Time   |",
            "-------------------------------------------------------------",
        ]
        output_strs += [
            "|  Event %4d  |  %s  |  %s  |  %s  |"
            % (
                i + 1,
                event.start.get_timecode(precision=1),
                (event.end - event.start).get_timecode(precision=1),
                event.end.get_timecode(precision=1),
            )
            for i, event in enumerate(result.event_list)
        ]
        output_strs += ["-------------------------------------------------------------"]
        logger.info("List of motion events:\n%s", "\n".join(output_strs))
        timecode_list = []
        for event in result.event_list:
            timecode_list.append(event.start.get_timecode())
            timecode_list.append(event.end.get_timecode())
        logger.info("Comma-separated timecode values:")
        # Print values regardless of quiet mode or not.
        # TODO(#78): Fix this output format to be more usable, in the form:
        # start1-end1[,[+]start2-end2[,[+]start3-end3...]]
        print(",".join(timecode_list))

    if scanner.output_mode != OutputMode.SCAN_ONLY:
        logger.info("Motion events written to disk.")
