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
""" ``dvr_scan`` Module

This is the main DVR-Scan module containing all application logic,
motion detection implementation, and command line processing. The
modules are organized as follows:

  dvr_scan.cli:
    Command-line interface (argparse)

  dvr_scan.scanner:
    Application logic + motion detection algorithm (ScanContext)
"""

import logging
import sys

# OpenCV is a required package, but we don't have it as an explicit dependency since we
# need to support both opencv-python and opencv-python-headless. Include some additional
# context with the exception if this is the case.
try:
    import cv2 as _
except ModuleNotFoundError as ex:
    raise ModuleNotFoundError(
        "OpenCV could not be found, try installing opencv-python:\n\npip install opencv-python",
        name='cv2',
    ) from ex

# Top-level imports for easier access from the dvr_scan module.
from dvr_scan.scanner import ScanContext

# Used for module/distribution identification.
__version__ = 'v1.5.dev0'

# About & copyright message string shown for the -v/--version CLI argument.
ABOUT_STRING = """-----------------------------------------------
DVR-Scan %s
-----------------------------------------------
Copyright (C) 2016-2022 Brandon Castellano
< https://github.com/Breakthrough/DVR-Scan >

This DVR-Scan is licensed under the BSD 2-Clause license; see the
included LICENSE file, or visit the above link for details. This
software uses the following third-party components; see the included
LICENSE-THIRDPARTY file for details.

 NumPy:  Copyright (C) 2005-2022, Numpy Developers.
 OpenCV: Copyright (C) 2022, OpenCV Team.
 FFmpeg: Copyright (C) 2001, Fabrice Bellard.
 CUDA:   Copyright (C) 2020, Nvidia Corporation.

THIS SOFTWARE CONTAINS SOURCE CODE AS PROVIDED BY NVIDIA CORPORATION.
THE SOFTWARE IS PROVIDED "AS IS" WITHOUT ANY WARRANTY, EXPRESS OR IMPLIED.
""" % __version__


def init_logger(quiet_mode: bool, log_level: int = logging.INFO):
    """Initializes the Python logger named 'dvr_scan'."""
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


init_logger(quiet_mode=True)
