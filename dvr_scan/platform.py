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
""" ``dvr_scan.platform`` Module

This file contains all platform/library/OS-specific compatibility fixes,
intended to improve the systems that are able to run DVR-Scan, and allow
for maintaining backwards compatibility with existing libraries going forwards.
"""

import logging

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
    try:
        return 'createBackgroundSubtractorCNT' in dir(cv2.bgsegm)
    except AttributeError:
        return False


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
