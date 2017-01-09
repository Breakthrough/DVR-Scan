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
import time

# DVR-Scan Library Imports
from dvr_scan.timecode import FrameTimecode

# Third-Party Library Imports
import cv2
import numpy


class ScanContext(object):
    """ The ScanContext object represents the DVR-Scan program state,
    which includes application initialization, handling the options,
    and coordinating overall application logic (via scan_motion()). """

    def __init__(self, args):
        """ Initializes the ScanContext with the supplied arguments. """
        if not args.quiet_mode:
            print("[DVR-Scan] Initializing scan context...")

        self.initialized = False

        self.suppress_output = args.quiet_mode
        self.frames_read = -1
        self.frames_processed = -1
        self._cap = None
        self._cap_path = None

        self.video_resolution = None
        self.video_fps = None
        self.video_paths = [input_file.name for input_file in args.input]
        # We close the open file handles, as only the paths are required.
        for input_file in args.input:
            input_file.close()

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
        self.video_resolution = None
        self.video_fps = None
        if not len(self.video_paths) > 0:
            return False
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
                cap.release()
                return False
            curr_resolution = (cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                               cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            curr_framerate = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            if self.video_resolution is None and self.video_fps is None:
                self.video_resolution = curr_resolution
                self.video_fps = curr_framerate
                if not self.suppress_output:
                    print("[DVR-Scan] Opened video %s (%d x %d at %2.3f FPS)." % (
                        video_name, self.video_resolution[0],
                        self.video_resolution[1], self.video_fps))
            # Check that all other videos specified have the same resolution
            # (we'll assume the framerate is the same if the resolution matches,
            # since the VideoCapture FPS information is not always accurate).
            elif curr_resolution != self.video_resolution:
                if not self.suppress_output:
                    print("[DVR-Scan] Error: Can't append clip %s, video resolution"
                          " does not match the first input file." % video_name)
                return False
            else:
                if not self.suppress_output:
                    print("[DVR-Scan] Appended video %s." % video_name)
        # If we get to this point, all videos have the same parameters.
        return True

    def _get_next_frame(self, retrieve = True):
        """ Returns a new frame from the current series of video files,
        or None when no more frames are available. """
        if self._cap:
            if retrieve:
                (ret_val, frame) = self._cap.read()
            else:
                ret_val = self._cap.grab()
                frame = True
            if ret_val:
                return frame
            else:
                self._cap.release()
                self._cap = None
        if self._cap is None and len(self.video_paths) > 0:
            self._cap_path = self.video_paths[0]
            self.video_paths = self.video_paths[1:]
            self._cap = cv2.VideoCapture(self._cap_path)
            if self._cap.isOpened():
                return self._get_next_frame()
            else:
                print("[DVR-Scan] Error: Unable to load video for processing.")
                self._cap = None

        return None


    def scan_motion(self):
        """ Performs motion analysis on the ScanContext's input video(s). """
        if self.initialized is not True:
            print("[DVR-Scan] Error: Scan context uninitialized, no analysis performed.")
            return
        print("[DVR-Scan] Scanning %s for motion events..." % (
            "%d input videos" % len(self.video_paths) if len(self.video_paths) > 1
            else "input video"))

        curr_pos = FrameTimecode(self.video_fps, 0)

        # Seek to starting position if required.
        if self.start_time is not None:
            while curr_pos.frame_num < self.start_time.frame_num:
                if self._get_next_frame() is None:
                    break
        while True:
            if self.end_time is not None and curr_pos.frame_num >= self.end_time:
                break
            if self.frame_skip > 0:
                for i in range(self.frame_skip):
                    if self._get_next_frame(False) is None:
                        break
                    curr_pos.frame_num += 1
            frame_rgb = self._get_next_frame()
            if frame_rgb is None:
                break

            curr_pos.frame_num += 1

        num_frames = curr_pos.frame_num
        if self.start_time is not None:
            num_frames -= self.start_time.frame_num
        print("[DVR-Scan] Read %d frames total." % num_frames)

