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
"""``dvr_scan.platform`` Module

Provides logging and platform/operating system compatibility.
"""

import importlib
import logging
import os
import platform
import subprocess
import sys
from typing import AnyStr, Optional

try:
    import screeninfo
except ImportError:
    screeninfo = None

from scenedetect.platform import get_and_create_path, get_ffmpeg_version

try:
    import tkinter
except ImportError:
    tkinter = None

try:
    import cv2
    import cv2.cuda

    HAS_MOG2_CUDA = bool(hasattr(cv2.cuda, "createBackgroundSubtractorMOG2"))
except:  # noqa: E722
    # We make sure importing OpenCV succeeds elsewhere so it's okay to suppress any exceptions here.
    HAS_MOG2_CUDA = False


HAS_TKINTER = tkinter is not None

IS_FROZEN = bool(not (getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")))


def get_min_screen_bounds():
    """Attempts to get the minimum screen resolution of all monitors using the `screeninfo` package.
    Returns the minimum of all monitor's heights and widths with 10% padding, or None if the package
    is unavailable."""
    # TODO: See if we can replace this with Tkinter (`winfo_screenwidth` / `winfo_screenheight`).
    if screeninfo is not None:
        try:
            monitors = screeninfo.get_monitors()
            return (
                int(0.9 * min(m.height for m in monitors)),
                int(0.9 * min(m.width for m in monitors)),
            )
        except screeninfo.common.ScreenInfoError as ex:
            logging.getLogger("dvr_scan").warning("Unable to get screen resolution: %s", ex)
    return None


def is_ffmpeg_available(ffmpeg_path: AnyStr = "ffmpeg"):
    """Is ffmpeg Available: Gracefully checks if ffmpeg command is available.

    Returns:
        True if `ffmpeg` can be invoked, False otherwise.
    """
    ret_val = None
    try:
        ret_val = subprocess.call([ffmpeg_path, "-v", "quiet"])
    except OSError:
        return False
    if ret_val is not None and ret_val != 1:
        return False
    return True


def _init_logger_impl(
    logger: logging.Logger,
    log_level: int,
    format_str: str,
    show_stdout: bool,
    log_file: Optional[str],
):
    logger.handlers = []
    logger.setLevel(log_level)
    # Add stdout handler if required.
    if show_stdout:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(fmt=format_str))
        logger.addHandler(handler)
    # Add file handler if required.
    if log_file:
        log_file = get_and_create_path(log_file)
        handler = logging.FileHandler(log_file)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(fmt=format_str))
        logger.addHandler(handler)


def init_logger(
    log_level: int = logging.INFO,
    show_stdout: bool = False,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Initializes logging for DVR-Scan. The logger instance used is named 'dvr_scan'.
    By default the logger has no handlers to suppress output. All existing log handlers
    are replaced every time this function is invoked.

    Arguments:
        log_level: Verbosity of log messages. Should be one of [logging.INFO, logging.DEBUG,
            logging.WARNING, logging.ERROR, logging.CRITICAL].
        show_stdout: If True, add handler to show log messages on stdout (default: False).
        log_file: If set, add handler to dump log messages to given file path.
    """
    # Format of log messages depends on verbosity.
    format_str = "[DVR-Scan] %(message)s"
    if log_level == logging.DEBUG:
        format_str = "%(levelname)s: %(module)s.%(funcName)s(): %(message)s"
    _init_logger_impl(logging.getLogger("dvr_scan"), log_level, format_str, show_stdout, log_file)
    # The `scenedetect` package also has useful log messages when opening and decoding videos.
    # We still want to make sure we can tell the messages apart, so we add a short prefix [::].
    format_str = "[DVR-Scan] :: %(message)s"
    if log_level == logging.DEBUG:
        format_str = "%(levelname)s: [scenedetect] %(module)s.%(funcName)s(): %(message)s"
    _init_logger_impl(
        logging.getLogger("pyscenedetect"), log_level, format_str, show_stdout, log_file
    )
    return logging.getLogger("dvr_scan")


def get_filename(path: AnyStr, include_extension: bool) -> AnyStr:
    """Get filename of the given path, optionally excluding extension."""
    filename = os.path.basename(path)
    if not include_extension:
        dot_position = filename.rfind(".")
        if dot_position > 0:
            filename = filename[:dot_position]
    return filename


def get_system_version_info(separator_width: int = 40) -> str:
    """Get the system's operating system, Python, packages, and external tool versions.
    Useful for debugging or filing bug reports.

    Used for the `scenedetect version -a` command.
    """
    output_template = "{:<8} {}"
    line_separator = "-" * separator_width
    not_found_str = "Not Installed"
    out_lines = []

    # System (Python, OS)
    out_lines += ["System Info", line_separator]
    out_lines += [
        output_template.format(name, version)
        for name, version in (
            ("OS:", "%s" % platform.platform()),
            ("Python:", "%s %s" % (platform.python_implementation(), platform.python_version())),
            ("Arch:", " + ".join(platform.architecture())),
        )
    ]
    output_template = "{:<16} {}"

    # Third-Party Packages
    out_lines += ["", "Packages", line_separator]
    third_party_packages = (
        "cv2",
        "dvr_scan",
        "numpy",
        "platformdirs",
        "PIL",
        "scenedetect",
        "screeninfo",
        "tqdm",
    )
    for module_name in third_party_packages:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "__version__"):
                out_lines.append(output_template.format(module_name, module.__version__))
            else:
                out_lines.append(output_template.format(module_name, not_found_str))
        except ModuleNotFoundError:
            out_lines.append(output_template.format(module_name, not_found_str))

    # External Tools
    out_lines += ["", "Features", line_separator]

    ffmpeg_version = get_ffmpeg_version()
    feature_version_info = [("ffmpeg", ffmpeg_version)] if ffmpeg_version else []
    feature_version_info += [("tkinter", "Installed")] if HAS_TKINTER else []
    feature_version_info += [("cv2.cuda", "Installed")] if HAS_MOG2_CUDA else []

    for feature_name, feature_version in feature_version_info:
        out_lines.append(
            output_template.format(
                feature_name, feature_version if feature_version else not_found_str
            )
        )

    return "\n".join(out_lines)
