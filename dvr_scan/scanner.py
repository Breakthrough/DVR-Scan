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
# Copyright (C) 2016-2020 Brandon Castellano <http://www.bcastell.com>.
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
import os
import time

# DVR-Scan Library Imports
from dvr_scan.timecode import FrameTimecode
import dvr_scan.platform

# Third-Party Library Imports
import cv2
import numpy as np


class ScanContext(object):
    """ The ScanContext object represents the DVR-Scan program state,
    which includes application initialization, handling the options,
    and coordinating overall application logic (via scan_motion()). """

    def __init__(self, args, gui=None):
        """ Initializes the ScanContext with the supplied arguments. """
        if not args.quiet_mode:
            print("[DVR-Scan] Initializing scan context...")

        self.initialized = False

        self.event_list = []

        self.suppress_output = args.quiet_mode
        self.frames_processed = -1
        self.frames_processed = -1
        self.frames_total = -1
        self._cap = None
        self._cap_path = None

        self.video_resolution = None
        self.video_fps = None
        self.video_paths = [input_file.name for input_file in args.input]
        self.frames_processed = 0
        self.running = True
        # We close the open file handles, as only the paths are required.
        for input_file in args.input:
            input_file.close()
        if not len(args.fourcc_str) == 4:
            print("[DVR-Scan] Error: Specified codec (-c/--codec) must be exactly 4 characters.")
            return
        if args.kernel_size == -1:
            self.kernel = None
        elif (args.kernel_size % 2) == 0:
            print("[DVR-Scan] Error: Kernel size must be an odd, positive integer (e.g. 3, 5, 7.")
            return
        else:
            self.kernel = np.ones((args.kernel_size, args.kernel_size), np.uint8)
        self.fourcc = cv2.VideoWriter_fourcc(*args.fourcc_str.upper())
        self.comp_file = None
        self.scan_only_mode = args.scan_only_mode
        if args.output:
            self.comp_file = args.output.name
            args.output.close()
        # Check the input video(s) and obtain the framerate/resolution.
        if self._load_input_videos():
            # Motion detection and output related arguments
            self.threshold = args.threshold
            if self.kernel is None:
                if self.video_resolution[0] >= 1920:
                    self.kernel = np.ones((7, 7), np.uint8)
                elif self.video_resolution[0] >= 1280:
                    self.kernel = np.ones((5, 5), np.uint8)
                else:
                    self.kernel = np.ones((3, 3), np.uint8)
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

            # timecode and ROI:
            self.draw_timecode = args.draw_timecode
            self.roi = args.roi
            if self.roi is not None:
                if self.roi:
                    if len(self.roi) != 4:
                        print("[DVR-Scan] Error: ROI must be specified as a rectangle of the form x/y/w/h!")
                        print("    For example: -roi 200 250 50 100")
                        return
                    for i in range(0, 4):
                        self.roi[i] = int(self.roi[i])
                else:
                    self.roi = []
            self.initialized = True

    def _load_input_videos(self):
        """ Opens and checks that all input video files are valid, can
        be processed, and have the same resolution and framerate. """
        self.video_resolution = None
        self.video_fps = None
        self.frames_total = 0
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
            curr_resolution = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                               int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            curr_framerate = cap.get(cv2.CAP_PROP_FPS)
            self.frames_total += cap.get(cv2.CAP_PROP_FRAME_COUNT)
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

    def _get_next_frame(self, retrieve=True):
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

    def _stampText(self, frame, text, line):
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        margin = 5
        thickness = 2
        color = (255, 255, 255)

        size = cv2.getTextSize(text, font, font_scale, thickness)

        text_width = size[0][0]
        text_height = size[0][1]
        line_height = text_height + size[1] + margin

        x = margin
        y = margin + size[0][1] + line * line_height
        cv2.rectangle(frame, (margin, margin),
                      (margin + text_width, margin + text_height + 2), (0, 0, 0), -1)
        cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)
        return None

    def scan_motion(self):
        """ Performs motion analysis on the ScanContext's input video(s). """
        if self.initialized is not True:
            print("[DVR-Scan] Error: Scan context uninitialized, no analysis performed.")
            return
        print("[DVR-Scan] Scanning %s for motion events..." % (
            "%d input videos" % len(self.video_paths) if len(self.video_paths) > 1
            else "input video"))

        bg_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=False)
        buffered_frames = []
        event_window = []
        self.event_list = []
        num_frames_post_event = 0
        event_start = None

        video_writer = None
        output_prefix = ''
        if self.comp_file:
            video_writer = cv2.VideoWriter(self.comp_file, self.fourcc,
                                           self.video_fps, self.video_resolution)
        elif len(self.video_paths[0]) > 0:
            output_prefix = os.path.basename(self.video_paths[0])
            dot_index = output_prefix.rfind('.')
            if dot_index > 0:
                output_prefix = output_prefix[:dot_index]

        curr_pos = FrameTimecode(self.video_fps, 0)
        #curr_state = 'no_event'     # 'no_event', 'in_event', or 'post_even
        in_motion_event = False
        self.frames_processed = 0
        num_frames_processed = 0
        processing_start = time.time()

        # Seek to starting position if required.
        if self.start_time is not None:
            while curr_pos.frame_num < self.start_time.frame_num:
                if self._get_next_frame(False) is None:
                    break
                self.frames_processed += 1
                curr_pos.frame_num += 1

        # area selection
        if self.roi is not None and len(self.roi) == 0:
            print("[DVR-Scan] selecting area of interest:")
            frame_for_crop = self._get_next_frame()
            if self.draw_timecode:
                self._stampText(frame_for_crop, curr_pos.get_timecode(), 0)
            self.roi = cv2.selectROI("DVR-Scan ROI Selection", frame_for_crop)
            cv2.destroyAllWindows()
            if all([coord == 0 for coord in self.roi]):
                print("[DVR-Scan] ROI selection cancelled.")
                print("[DVR-Scan] Aborting...")
                return
        # Motion event scanning/detection loop.
        assert self.roi is None or len(self.roi) == 4
        if self.roi:
            print("[DVR-Scan] area selected (x,y,w,h): %s" % str(self.roi))


        tqdm = dvr_scan.platform.get_tqdm()
        progress_bar = None
        self.frames_total = int(self.frames_total)
        if tqdm is not None and self.frames_total > 0 and not self.suppress_output:
            if self.end_time and self.end_time.frame_num < self.frames_total:
                self.frames_total = self.end_time.frame_num
            if self.start_time:
                self.frames_total -= self.start_time.frame_num
            if self.frames_total < 0:
                self.frames_total = 0
            progress_bar = tqdm.tqdm(
                total=self.frames_total,
                unit=' frames',
                desc="[DVR-Scan] Processed")

        # Motion event scanning/detection loop.
        while self.running:
            if self.end_time is not None and curr_pos.frame_num >= self.end_time.frame_num:
                break
            if self.frame_skip > 0:
                for _ in range(self.frame_skip):
                    if self._get_next_frame(False) is None:
                        break
                    curr_pos.frame_num += 1
                    self.frames_processed += 1
                    if progress_bar:
                        progress_bar.update(1)
            frame_rgb = self._get_next_frame()
            if frame_rgb is None:
                break

            frame_rgb_origin = frame_rgb

            if self.roi:
                frame_rgb = frame_rgb[
                    int(self.roi[1]):int(self.roi[1] + self.roi[3]),
                    int(self.roi[0]):int(self.roi[0] + self.roi[2])]  # area selection

            frame_gray = cv2.cvtColor(frame_rgb, cv2.COLOR_BGR2GRAY)
            frame_mask = bg_subtractor.apply(frame_gray)
            frame_filt = cv2.morphologyEx(frame_mask, cv2.MORPH_OPEN, self.kernel)
            frame_score = np.sum(frame_filt) / float(frame_filt.shape[0] * frame_filt.shape[1])
            event_window.append(frame_score)
            event_window = event_window[-self.min_event_len.frame_num:]

            if in_motion_event:
                # in event or post event, write all queued frames to file,
                # and write current frame to file.
                # if the current frame doesn't meet the threshold, increment
                # the current scene's post-event counter.
                if not self.scan_only_mode:
                    if self.draw_timecode:
                        self._stampText(frame_rgb_origin, curr_pos.get_timecode(), 0)
                    video_writer.write(frame_rgb_origin)
                if frame_score >= self.threshold:
                    num_frames_post_event = 0
                else:
                    num_frames_post_event += 1
                    if num_frames_post_event >= self.post_event_len.frame_num:
                        in_motion_event = False
                        event_end = FrameTimecode(
                            self.video_fps, curr_pos.frame_num)
                        event_duration = FrameTimecode(
                            self.video_fps, curr_pos.frame_num - event_start.frame_num)
                        self.event_list.append((event_start, event_end, event_duration))
                        if not self.comp_file and not self.scan_only_mode:
                            video_writer.release()
            else:
                if not self.scan_only_mode:
                    buffered_frames.append(frame_rgb_origin)
                    buffered_frames = buffered_frames[-self.pre_event_len.frame_num:]
                if len(event_window) >= self.min_event_len.frame_num and all(
                        score >= self.threshold for score in event_window):
                    in_motion_event = True
                    event_window = []
                    num_frames_post_event = 0
                    event_start = FrameTimecode(
                        self.video_fps, curr_pos.frame_num)
                    # Open new VideoWriter if needed, write buffered_frames to file.
                    if not self.scan_only_mode:
                        if not self.comp_file:
                            output_path = '%s.DSME_%04d.avi' % (
                                output_prefix, len(self.event_list))
                            video_writer = cv2.VideoWriter(
                                output_path, self.fourcc, self.video_fps,
                                self.video_resolution)
                        for frame in buffered_frames:
                            if self.draw_timecode:
                                self._stampText(frame, curr_pos.get_timecode(), 0)
                            video_writer.write(frame)
                        buffered_frames = []

            curr_pos.frame_num += 1
            self.frames_processed += 1
            num_frames_processed += 1
            if progress_bar:
                progress_bar.update(1)

        # If we're still in a motion event, we still need to compute the duration
        # and ending timecode and add it to the event list.
        if in_motion_event:
            curr_pos.frame_num -= 1  # Correct for the increment at the end of the loop
            event_end = FrameTimecode(
                self.video_fps, curr_pos.frame_num)
            event_duration = FrameTimecode(
                self.video_fps, curr_pos.frame_num - event_start.frame_num)
            self.event_list.append((event_start, event_end, event_duration))

        if video_writer is not None:
            video_writer.release()
        if progress_bar is not None:
            progress_bar.close()
        elif not self.suppress_output:
            processing_time = time.time() - processing_start
            processing_rate = float(self.frames_processed) / processing_time
            print("[DVR-Scan] Processed %d / %d frames read in %3.1f secs (avg %3.1f FPS)." % (
                num_frames_processed, self.frames_processed, processing_time, processing_rate))
        if not len(self.event_list) > 0:
            print("[DVR-Scan] No motion events detected in input.")
            return

        print("[DVR-Scan] Detected %d motion events in input." % len(self.event_list))
        print("[DVR-Scan] Scan-only mode specified, list of motion events:")
        print("-------------------------------------------------------------")
        print("|   Event #    |  Start Time  |   Duration   |   End Time   |")
        print("-------------------------------------------------------------")
        for event_num, (event_start, event_end, event_duration) in enumerate(self.event_list):
            print("|  Event %4d  |  %s  |  %s  |  %s  |" % (
                event_num + 1, event_start.get_timecode(precision=1),
                event_duration.get_timecode(precision=1),
                event_end.get_timecode(precision=1)))
        print("-------------------------------------------------------------")

        if self.scan_only_mode:
            print("[DVR-Scan] Comma-separated timecode values:")
            timecode_list = []
            for event_start, event_end, event_duration in self.event_list:
                timecode_list.append(event_start.get_timecode())
                timecode_list.append(event_end.get_timecode())
            print(','.join(timecode_list))
        else:
            print("[DVR-Scan] Motion events written to disk.")

