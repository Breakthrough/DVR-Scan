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
        """ Initializes the ScanContext with the supplied arguments. """
        if not args.quiet_mode:
            print("[DVR-Scan] Initializing scan context...")

        self.initialized = False

        self.suppress_output = args.quiet_mode
        self.frames_read = -1
        self.frames_processed = -1
        self.cap_list = None
        self.curr_video_path = None

        self.video_resolution = None
        self.video_fps = None
        self.video_paths = [input_file.name for input_file in args.input]
        [input_file.close() for input_file in args.input]

        if self._load_input_videos():
            # Motion detection and output related arguments
            self.fourcc_str = args.fourcc_str
            self.threshold = args.threshold
            self.kernel_size = args.kernel_size
            # Event detection window properties
            self.min_event_len = FrameTimecode(self.video_fps, args.min_event_len)
            self.pre_event_len = FrameTimecode(self.video_fps, args.time_pre_event)
            self.post_event_len = FrameTimecode(self.video_fps, args.time_post_event)
            # Start time, end time, and duration
            self.start_time, self.end_time = None, None
            if args.start_time is not None:
                self.start_time = FrameTimecode(self.video_fps, args.start_time)
            if args.duration is not None:
                duration = FrameTimecode(self.video_fps, args.duration)
                if isinstance(self.start_time, FrameTimecode):
                    self.end_time = FrameTimecode(
                        self.video_fps, self.start_time.frame_num + duration.frame_num)
                else:
                    self.end_time = duration
            elif args.end_time is not None:
                self.end_time = FrameTimecode(self.video_fps, args.end_time)
            # Video processing related arguments
            self.frame_skip = args.frame_skip
            self.downscale_factor = args.downscale_factor

            self.initialized = True

    def _load_input_videos(self):
        """ Opens and checks that all input video files are valid, can
        be processed, and have the same resolution and framerate. """
        self.cap_list = []
        video_resolution = None
        video_fps = None
        for video_path in self.video_paths:
            cap = cv2.VideoCapture()
            cap.open(video_path)
            video_name = os.path.basename(video_path)
            if not cap.isOpened():
                if not self.suppress_output:
                    print("[DVR-Scan] Error: Couldn't load video %s." % video_name)
                    print("[DVR-Scan] Check that the given file is a valid video"
                          " clip, and ensure all required software dependencies"
                          " are installed and configured properly.")
                return False
            curr_resolution = (cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                               cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            curr_framerate = cap.get(cv2.CAP_PROP_FPS)
            video_valid = False
            if video_resolution is None and video_fps is None:
                video_resolution = curr_resolution
                video_fps = curr_framerate
                if not self.suppress_output:
                    print("[DVR-Scan] Opened video %s (%d x %d at %2.3f FPS)." % (
                        video_name, video_resolution[0], video_resolution[1],
                        video_fps))
                video_valid = True
            # Check that all other videos specified have the same resolution
            # (we'll assume the framerate is the same if the resolution matches,
            # since the VideoCapture FPS information is not always accurate).
            elif curr_resolution != video_resolution:
                if not self.suppress_output:
                    print("[DVR-Scan] Error: Can't append clip %s, video resolution"
                          " does not match the first input file." % video_name)
                return False
            else:
                if not self.suppress_output:
                    print("[DVR-Scan] Appended video %s." % video_name)
                video_valid = True
            if video_valid is True:
                self.cap_list.append(cap)

        return True


    def scan_motion(self):
        """ Performs motion analysis on the ScanContext's input video(s). """
        if self.initialized is not True:
            print("[DVR-Scan] Error: Scan context uninitialized, no analysis performed.")
            return

        print("[DVR-Scan] Scanning %s for motion events..." % (
            "%d input videos" % len(self.video_paths) if len(self.video_paths) > 1
            else "input video"))
        

        curr_pos = FrameTimecode(self.video_fps, 0)
        # Seek to starting position.


        pass

