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
import glob
import logging
import os
import random
import string
import typing as ty
from contextlib import contextmanager
from datetime import datetime
from logging import FileHandler
from pathlib import Path

import tqdm
from platformdirs import user_log_path
from scenedetect import FrameTimecode

# TODO: This is a hack and will break eventually, but this is the only way to handle this
# right now unfortunately. logging_redirect_tqdm from the tqdm contrib module doesn't respect
# verbosity unfortunately. This is being tracked by https://github.com/tqdm/tqdm/issues/1272.
from tqdm.contrib.logging import (
    _get_first_found_console_logging_handler,
    _is_console_logging_handler,
    _TqdmLoggingHandler,
)

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


def logfile_path(name_prefix: str) -> Path:
    """Get path to log file, creating the folder if it does not exist."""
    folder = user_log_path("DVR-Scan", False)
    folder.mkdir(parents=True, exist_ok=True)
    # Generate a random suffix so multiple instances of dvr-scan don't try to write to the same
    # log file.
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return folder / Path(f"{name_prefix}-{datetime.now():%Y%m%d-%H%M%S}-{random_suffix}.log")


def prune_log_files(log_folder: Path, max_files: int, name_prefix: str):
    """Prune log files, keeping the latest `max_files` number of logs."""
    # Prune oldest log files if we have too many.
    if max_files > 0:
        # We find all DVR-Scan log files by globbing, then remove the oldest ones.
        log_file_pattern = str(log_folder / f"{name_prefix}-*.log")
        log_files = list(glob.glob(log_file_pattern))
        if len(log_files) > max_files:
            log_files.sort(key=os.path.getmtime)
            for i in range(len(log_files) - max_files):
                logger.debug("Removing old log file: %s", log_files[i])
                try:
                    os.remove(log_files[i])
                except PermissionError:
                    logger.warning(
                        "Failed to remove old log file: %s. It might be in use by another DVR-Scan process.",
                        log_files[i],
                    )


def setup_logger(logfile_path: Path, max_files: int, name_prefix: str):
    """Initialize rolling debug logger."""
    prune_log_files(logfile_path.parent, max_files, name_prefix)
    handler = FileHandler(str(logfile_path))
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT_ROLLING_LOGS))
    # *WARNING*: This log message must come before we attach the handler otherwise it will get
    # written to the log file each time.
    logger.debug(f"writing logs to {logfile_path} (max_files: {max_files})")
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

    # NOTE: The CLI overloads the type of the bounding-box setting by allowing an optional smooth
    # time. When set, this means the flag is no longer boolean, and represents desired smoothing.
    bounding_box_option_is_smoothing = not isinstance(settings.get("bounding-box"), bool)
    bounding_box_enabled = bool(settings.get("bounding-box")) or bounding_box_option_is_smoothing
    if bounding_box_enabled:
        smoothing_time = (
            settings.get("bounding-box")
            if bounding_box_option_is_smoothing
            else settings.get("bounding-box-smooth-time")
        )
        smoothing = FrameTimecode(smoothing_time, scanner.framerate).frame_num
        bounding_box = BoundingBoxOverlay(
            min_size_ratio=settings.get("bounding-box-min-size"),
            thickness_ratio=settings.get("bounding-box-thickness"),
            color=settings.get("bounding-box-color"),
            smoothing=smoothing,
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
        max_area=settings.get("max-area"),
        max_width=settings.get("max-width"),
        max_height=settings.get("max-height"),
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


@contextmanager
def logging_redirect_tqdm(
    loggers: ty.Optional[ty.List[logging.Logger]], instance: ty.Type = tqdm.tqdm
):
    """
    Context manager redirecting console logging to `tqdm.write()`, leaving
    other logging handlers (e.g. log files) unaffected.

    Parameters
    ----------
    loggers  : list, optional
      Which handlers to redirect (default: [logging.root]).
    tqdm_class  : optional

    Example
    -------
    ```python
    import logging
    from tqdm import trange
    from tqdm.contrib.logging import logging_redirect_tqdm

    LOG = logging.getLogger(__name__)

    if __name__ == "__main__":
        logging.basicConfig(level=logging.INFO)
        with logging_redirect_tqdm():
            for i in trange(9):
                if i == 4:
                    LOG.info("console logging redirected to `tqdm.write()`")
        # logging restored
    ```
    """
    if loggers is None:
        loggers = [logging.root]
    original_handlers_list = [logger.handlers for logger in loggers]
    try:
        for logger in loggers:
            tqdm_handler = _TqdmLoggingHandler(instance)
            orig_handler = _get_first_found_console_logging_handler(logger.handlers)
            if orig_handler is not None:
                tqdm_handler.setFormatter(orig_handler.formatter)
                tqdm_handler.stream = orig_handler.stream
                # The following is missing from the original logging_redirect_tqdm.
                # This is being tracked by https://github.com/tqdm/tqdm/issues/1272.
                tqdm_handler.setLevel(orig_handler.level)
            logger.handlers = [
                handler for handler in logger.handlers if not _is_console_logging_handler(handler)
            ] + [tqdm_handler]
        yield
    finally:
        for logger, original_handlers in zip(loggers, original_handlers_list):
            logger.handlers = original_handlers
