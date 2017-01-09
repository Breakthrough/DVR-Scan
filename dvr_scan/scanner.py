#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# This file contains the implementation of the ScanContext class, which
# is used to provide a high level interface to the logic used by
# DVR-Scan to implement the motion detection/scanning algorithm.
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
from dvr_scan.timecode import FrameTimecode

# Third-Party Library Imports
import cv2
import numpy



class ScanContext(object):

    def __init__(self, args):
        self.cap = cv2.VideoCapture()
        self.frames_read = -1
        self.frames_processed = -1

        self.video_path = args.input

        print(self.video_path)
        pass

        #self.curr_pos = FrameTimecode()


    def process_video(self):
        pass
