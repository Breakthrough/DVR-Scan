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
"""``dvr_scan.platform`` Module

Provides logging and platform/operating system compatibility.
"""

from contextlib import contextmanager
import logging
import os
import subprocess
import sys
from typing import AnyStr, Optional

try:
    import screeninfo
except ImportError:
    screeninfo = None

from scenedetect.platform import get_and_create_path

try:
    import tkinter
except ImportError:
    tkinter = None


# TODO(v1.7): Figure out how to make icon work on Linux. Might need a PNG version.
def get_icon_path() -> str:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        app_folder = os.path.abspath(os.path.dirname(sys.executable))
        icon_path = os.path.join(app_folder, "dvr-scan.ico")
        if os.path.exists(icon_path):
            return icon_path
    # TODO(v1.7): Figure out how to properly get icon path in the package. The folder will be
    # different in the final Windows build, may have to check if this is a frozen instance or not.
    # Also need to ensure the icon is included in the package metadata.
    # For Python distributions, may have to put dvr-scan.ico with the source files, and use
    # os.path.dirname(sys.modules[package].__file__) (or just __file__ here).
    for path in ("dvr-scan.ico", "dist/dvr-scan.ico"):
        if os.path.exists(path):
            return path
    return ""


HAS_TKINTER = not tkinter is None

IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes


def get_min_screen_bounds():
    """Attempts to get the minimum screen resolution of all monitors using the `screeninfo` package.
    Returns the minimum of all monitor's heights and widths with 10% padding, or None if the package
    is unavailable."""
    if not screeninfo is None:
        try:
            monitors = screeninfo.get_monitors()
            return (int(0.9 * min(m.height for m in monitors)),
                    int(0.9 * min(m.width for m in monitors)))
        except screeninfo.common.ScreenInfoError as ex:
            logging.getLogger('dvr_scan').warning("Unable to get screen resolution: %s", ex)
    return None


def is_ffmpeg_available(ffmpeg_path: AnyStr = 'ffmpeg'):
    """ Is ffmpeg Available: Gracefully checks if ffmpeg command is available.

    Returns:
        True if `ffmpeg` can be invoked, False otherwise.
    """
    ret_val = None
    try:
        ret_val = subprocess.call([ffmpeg_path, '-v', 'quiet'])
    except OSError:
        return False
    if ret_val is not None and ret_val != 1:
        return False
    return True


def _init_logger_impl(logger: logging.Logger, log_level: int, format_str: str, show_stdout: bool,
                      log_file: Optional[str]):
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


def init_logger(log_level: int = logging.INFO,
                show_stdout: bool = False,
                log_file: Optional[str] = None) -> logging.Logger:
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
    format_str = '[DVR-Scan] %(message)s'
    if log_level == logging.DEBUG:
        format_str = '%(levelname)s: %(module)s.%(funcName)s(): %(message)s'
    _init_logger_impl(logging.getLogger('dvr_scan'), log_level, format_str, show_stdout, log_file)
    # The `scenedetect` package also has useful log messages when opening and decoding videos.
    # We still want to make sure we can tell the messages apart, so we add a short prefix [::].
    format_str = '[DVR-Scan] :: %(message)s'
    if log_level == logging.DEBUG:
        format_str = '%(levelname)s: [scenedetect] %(module)s.%(funcName)s(): %(message)s'
    _init_logger_impl(
        logging.getLogger('pyscenedetect'), log_level, format_str, show_stdout, log_file)
    return logging.getLogger('dvr_scan')


def get_filename(path: AnyStr, include_extension: bool) -> AnyStr:
    """Get filename of the given path, optionally excluding extension."""
    filename = os.path.basename(path)
    if not include_extension:
        dot_position = filename.rfind('.')
        if dot_position > 0:
            filename = filename[:dot_position]
    return filename


def set_icon(window_name: str):
    icon_path = get_icon_path()
    if not icon_path:
        return
    if not IS_WINDOWS:
        # TODO: Set icon on Linux/OSX.
        return
    SendMessage = ctypes.windll.user32.SendMessageW
    FindWindow = ctypes.windll.user32.FindWindowW
    LoadImage = ctypes.windll.user32.LoadImageW
    SetFocus = ctypes.windll.user32.SetFocus
    IMAGE_ICON = 1
    ICON_SMALL = 1
    ICON_BIG = 1
    LR_LOADFROMFILE = 0x00000010
    LR_CREATEDIBSECTION = 0x00002000
    WM_SETICON = 0x0080
    hWnd = FindWindow(None, window_name)
    hIcon = LoadImage(None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_CREATEDIBSECTION)
    SendMessage(hWnd, WM_SETICON, ICON_SMALL, hIcon)
    SendMessage(hWnd, WM_SETICON, ICON_BIG, hIcon)
    SetFocus(hWnd)


@contextmanager
def temp_tk_window():
    """Used to provide a hidden Tk window as a root for pop-up dialog boxes to return focus to
    main region window when destroyed."""
    root = tkinter.Tk()
    try:
        root.withdraw()
        # TODO: Set icon on Linux/OSX.
        if IS_WINDOWS:
            icon_path = get_icon_path()
            if icon_path:
                root.iconbitmap(os.path.abspath(icon_path))
        yield root
    finally:
        root.destroy()
