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
"""``dvr_scan.platform`` Module

Contains platform, library, or OS-specific compatibility helpers.
"""

import logging
import sys

import cv2


def get_tqdm():
    """ Safely attempts to import the tqdm module, returning either a
    reference to the imported module, or None if tqdm was not found."""
    try:
        import tqdm
        return tqdm
    except ImportError:
        pass
    return None


def cnt_is_available():
    return hasattr(cv2, 'bgsegm') and hasattr(cv2.bgsegm, 'createBackgroundSubtractorCNT')


def cuda_mog_is_available():
    return hasattr(cv2, 'cuda') and hasattr(cv2.cuda, 'createBackgroundSubtractorMOG2')


def get_min_screen_bounds():
    """ Safely attempts to get the minimum screen resolution of all monitors
    using the `screeninfo` package. Returns the minimum of all monitor's heights
    and widths with 10% padding."""
    try:
        import screeninfo
        try:
            monitors = screeninfo.get_monitors()
            return (int(0.9 * min(m.height for m in monitors)),
                    int(0.9 * min(m.width for m in monitors)))
        except screeninfo.common.ScreenInfoError as ex:
            logging.getLogger('dvr_scan').warning("Unable to get screen resolution: %s", ex)
    except ImportError:
        pass
    return None


def init_logger(quiet_mode: bool, log_level: int = logging.INFO):
    """Initializes Python logger named 'dvr_scan' for use by the CLI and API."""
    logger = logging.getLogger('dvr_scan')
    logger.setLevel(log_level)
    if quiet_mode:
        for handler in logger.handlers:
            logger.removeHandler(handler)
        return
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter(fmt='[DVR-Scan] %(message)s'))
    logger.addHandler(handler)
    return logger
