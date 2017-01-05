#
#       DVR-Scan: Find & Export Motion Events in Video Footage
#   --------------------------------------------------------------
#     [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#     [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# This file contains all code for the main `dvr_scan` module.
#
# Copyright (C) 2016-2017 Brandon Castellano <http://www.bcastell.com>.
#
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file or visit one of the following pages for details:
#  - https://github.com/Breakthrough/DVR-Scan/
#
# This software uses Numpy and OpenCV; see the LICENSE-NUMPY and
# LICENSE-OPENCV files or visit the above URL for details.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

# Standard Library Imports
from __future__ import print_function
import sys
import os
import argparse
import time
import csv

# DVR-Scan Library Imports
import dvr_scan.platform
import dvr_scan.timecode
import dvr_scan.cli

# Third-Party Library Imports
import cv2
import numpy


# Used for module identification and when printing copyright & version info.
__version__ = 'v0.1-dev'

# About & copyright message string shown for the -v / --version CLI argument.
ABOUT_STRING   = """-----------------------------------------------
DVR-Scan %s
-----------------------------------------------
Copyright (C) 2016-2017 Brandon Castellano
< https://github.com/Breakthrough/DVR-Scan >

This DVR-Scan is licensed under the BSD 2-Clause license; see the
included LICENSE file, or visit the above link for details. This
software uses the following third-party components:
  NumPy: Copyright (C) 2005-2013, Numpy Developers.
 OpenCV: Copyright (C) 2016, Itseez.
THE SOFTWARE IS PROVIDED "AS IS" WITHOUT ANY WARRANTY, EXPRESS OR IMPLIED.

""" % __version__

 
def compute_frame_score(frame):
    pass


def main():
    """Entry point for running main DVR-Scan program.

    Handles high-level interfacing of video IO and motion event detection.
    """

    # Parse CLI arguments.
    args = dvr_scan.cli.get_cli_parser().parse_args()


