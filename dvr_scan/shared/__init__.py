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

"""Business logic shared between the DVR-Scan CLI and the DVR-Scan GUI."""

import argparse
import logging
import typing as ty
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_path
from scenedetect import FrameTimecode

from dvr_scan.overlays import BoundingBoxOverlay, TextOverlay
from dvr_scan.platform import LOG_FORMAT_ROLLING_LOGS, attach_log_handler
from dvr_scan.platform import init_logger as _init_logger
from dvr_scan.scanner import DetectorType, MotionScanner, OutputMode
from dvr_scan.shared.settings import ScanSettings

logger = logging.getLogger("dvr_scan")


def init_logging(
    args: ty.Optional[argparse.ArgumentParser],
    config: ty.Optional[ScanSettings],
):
    verbosity = logging.INFO
    if args is not None and hasattr(args, "verbosity"):
        verbosity = getattr(logging, args.verbosity.upper())
    elif config is not None:
        verbosity = getattr(logging, config.get("verbosity").upper())

    quiet_mode = False
    if args is not None and hasattr(args, "quiet_mode"):
        quiet_mode = args.quiet_mode
    elif config is not None:
        quiet_mode = config.get("quiet-mode")

    _init_logger(
        log_level=verbosity,
        show_stdout=not quiet_mode,
        log_file=args.logfile if hasattr(args, "logfile") else None,
    )


def logfile_path(logfile_name: str):
    """Initialize rolling debug logger."""
    folder = user_log_path("DVR-Scan", False)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / Path(logfile_name)


def setup_logger(logfile_path: str, max_size_bytes: int, max_files: int):
    """Initialize rolling debug logger."""
    folder = user_log_path("DVR-Scan", False)
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        logfile_path,
        maxBytes=max_size_bytes,
        backupCount=max_files,
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT_ROLLING_LOGS))
    # *WARNING*: This log message must come before we attach the handler otherwise it will get
    # written to the log file each time.
    logger.debug(
        f"writing logs to {logfile_path} (max_size_bytes: {max_size_bytes}, max_files: {max_files})"
    )
    attach_log_handler(handler)


def init_scanner(
    settings: ScanSettings,
) -> MotionScanner:
    logger.debug("initializing motion scan")
    scanner = MotionScanner(
        input_videos=settings.get_arg("input"),
        input_mode=settings.get("input-mode"),
        frame_skip=settings.get("frame-skip"),
        show_progress=not settings.get("quiet-mode"),
        debug_mode=settings.get("debug"),
    )

    scanner.set_output(
        comp_file=settings.get_arg("output"),
        mask_file=settings.get_arg("mask-output"),
        output_mode=OutputMode.SCAN_ONLY
        if settings.get_arg("scan-only")
        else settings.get("output-mode"),
        opencv_fourcc=settings.get("opencv-codec"),
        ffmpeg_input_args=settings.get("ffmpeg-input-args"),
        ffmpeg_output_args=settings.get("ffmpeg-output-args"),
        output_dir=settings.get("output-dir"),
    )

    timecode_overlay = None
    if settings.get("time-code"):
        timecode_overlay = TextOverlay(
            font_scale=settings.get("text-font-scale"),
            margin=settings.get("text-margin"),
            border=settings.get("text-border"),
            thickness=settings.get("text-font-thickness"),
            color=settings.get("text-font-color"),
            bg_color=settings.get("text-bg-color"),
            corner=TextOverlay.Corner.TopLeft,
        )

    metrics_overlay = None
    if settings.get("frame-metrics"):
        metrics_overlay = TextOverlay(
            font_scale=settings.get("text-font-scale"),
            margin=settings.get("text-margin"),
            border=settings.get("text-border"),
            thickness=settings.get("text-font-thickness"),
            color=settings.get("text-font-color"),
            bg_color=settings.get("text-bg-color"),
            corner=TextOverlay.Corner.TopRight,
        )

    bounding_box = None
    # bounding_box_arg will be None if -bb was not set, False if -bb was set without any args,
    # otherwise it represents the desired smooth time.
    bounding_box_arg = settings.get_arg("bounding-box")
    if bounding_box_arg is not None or settings.get("bounding-box"):
        if bounding_box_arg is not None and bounding_box_arg is not False:
            smoothing_time = FrameTimecode(bounding_box_arg, scanner.framerate)
        else:
            smoothing_time = FrameTimecode(
                settings.get("bounding-box-smooth-time"), scanner.framerate
            )
        bounding_box = BoundingBoxOverlay(
            min_size_ratio=settings.get("bounding-box-min-size"),
            thickness_ratio=settings.get("bounding-box-thickness"),
            color=settings.get("bounding-box-color"),
            smoothing=smoothing_time.frame_num,
        )

    scanner.set_overlays(
        timecode_overlay=timecode_overlay,
        metrics_overlay=metrics_overlay,
        bounding_box=bounding_box,
    )

    scanner.set_detection_params(
        detector_type=DetectorType[settings.get("bg-subtractor").upper()],
        threshold=settings.get("threshold"),
        max_threshold=settings.get("max-threshold"),
        variance_threshold=settings.get("variance-threshold"),
        kernel_size=settings.get("kernel-size"),
        downscale_factor=settings.get("downscale-factor"),
        learning_rate=settings.get("learning-rate"),
    )

    scanner.set_event_params(
        min_event_len=settings.get("min-event-length"),
        time_pre_event=settings.get("time-before-event"),
        time_post_event=settings.get("time-post-event"),
        use_pts=settings.get("use-pts"),
    )

    scanner.set_thumbnail_params(
        thumbnails=settings.get("thumbnails"),
    )

    scanner.set_video_time(
        start_time=settings.get_arg("start-time"),
        end_time=settings.get_arg("end-time"),
        duration=settings.get_arg("duration"),
    )

    scanner.set_regions(
        region_editor=settings.get("region-editor"),
        regions=settings.get_arg("regions"),
        load_region=settings.get("load-region"),
        save_region=settings.get_arg("save-region"),
        roi_deprecated=settings.get("region-of-interest"),
    )

    return scanner
