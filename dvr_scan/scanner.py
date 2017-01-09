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
        self.initialized = False



        #self.cap = cv2.VideoCapture()
        self.cap_list = None
        self.frames_read = -1
        self.frames_processed = -1

        self.video_paths = [input_file.name for input_file in args.input]
        [input_file.close() for input_file in args.input]
        self.curr_video_path = None

        print(self.video_paths)
        
        if self._load_input_videos():
            self.initialized = True

        #self.curr_pos = FrameTimecode()

        #self.initialized = True
    


    def _load_input_videos(self):
        """ Opens and checks that all input video files are valid, can
        be processed, and have the same resolution and framerate. """
        self.cap_list = []
        video_resolution = None
        video_framerate = None
        for video_path in self.video_paths:
            cap = cv2.VideoCapture()
            cap.open(video_path)
            video_name = os.path.basename(video_path)
            if not cap.isOpened():
                print("[DVR-Scan] Error: Couldn't load video %s." % video_name)
                print("[DVR-Scan] Check that the given file is a valid video"
                      " clip, and ensure all required software dependencies"
                      " are installed and configured properly.")
                return False
            curr_resolution = (cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                               cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            curr_framerate = cap.get(cv2.CAP_PROP_FPS)
            video_valid = False
            if video_resolution is None and video_framerate is None:
                video_resolution = curr_resolution
                video_framerate = curr_framerate
                print("[DVR-Scan] Opened video %s (%d x %d at %2.3f FPS)." % (
                    video_name, video_resolution[0], video_resolution[1],
                    video_framerate))
                video_valid = True
            elif curr_resolution != video_resolution:
                print("[DVR-Scan] Error: Can't append clip %s, video resolution"
                      " does not match the first input file." % video_name)
                return False
            else:
                print("[DVR-Scan] Appended video %s." % video_name)
                video_valid = True
            if video_valid is True:
                self.cap_list.append(cap)


        # Check that all other videos specified have the same resolution
        # (we'll assume the framerate is the same if the resolution matches,
        # since the VideoCapture FPS information is not always accurate).

        # Seek to starting position.



        return True


    def scan_motion(self):
        """ Performs motion analysis on the ScanContext's input video(s). """
        pass

