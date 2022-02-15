# -*- coding: utf-8 -*-
#
#       DVR-Scan: Find & Export Motion Events in Video Footage
#   --------------------------------------------------------------
#     [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#     [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# This file contains all code for the main `dvr_scan` module.
#
# Copyright (C) 2016-2021 Brandon Castellano <http://www.bcastell.com>.
#
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file or visit one of the following pages for details:
#  - https://github.com/Breakthrough/DVR-Scan/
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
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

# Standard Library Imports
from __future__ import print_function
import logging
import sys

# DVR-Scan Library Imports
from dvr_scan.scanner import ScanContext
from dvr_scan.scanner import VideoLoadFailure


# Used for module identification and when printing copyright & version info.
__version__ = 'v1.4.1-dev'

# About & copyright message string shown for the -v/--version CLI argument.
ABOUT_STRING = """-----------------------------------------------
DVR-Scan %s
-----------------------------------------------
Copyright (C) 2016-2022 Brandon Castellano
< https://github.com/Breakthrough/DVR-Scan >

This DVR-Scan is licensed under the BSD 2-Clause license; see the
included LICENSE file, or visit the above link for details. This
software uses the following third-party components:
  NumPy: Copyright (C) 2005-2013, Numpy Developers.
 OpenCV: Copyright (C) 2016, Itseez.
THE SOFTWARE IS PROVIDED "AS IS" WITHOUT ANY WARRANTY, EXPRESS OR IMPLIED.

""" % __version__



def init_logger(quiet_mode, log_level=logging.INFO):
    """ Initializes the Python logging module for DVR-Scan.

    The logger instance used is 'dvr_scan'.
    """

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
