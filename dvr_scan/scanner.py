# -*- coding: utf-8 -*-
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
# Copyright (C) 2016-2021 Brandon Castellano <http://www.bcastell.com>.
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

""" ``dvr_scan.scanner`` Module

This module contains the ScanContext class, which implements the
DVR-Scan program logic, as well as the motion detection algorithm.
"""

# Standard Library Imports
from __future__ import print_function
import os
import time
import logging

# Third-Party Library Imports
import cv2
import numpy as np

# DVR-Scan Library Imports
from dvr_scan.timecode import FrameTimecode
import dvr_scan.platform


DEFAULT_VIDEOWRITER_CODEC = cv2.VideoWriter_fourcc('X', 'V', 'I', 'D')


class ScanContext(object):
    """ The ScanContext object represents the DVR-Scan program state,
    which includes application initialization, handling the options,
    and coordinating overall application logic (via scan_motion()). """

    def __init__(self, args, show_progress=True):
        """ Initializes the ScanContext with the supplied arguments.

        Arguments:
            args: TODO - Remove.

            show_progress: Shows a progress bar if tqdm is available.
        """

        self._logger = logging.getLogger('dvr_scan')
        self._logger.info("Initializing scan context...")

        self.initialized = False
        self.running = True         # Allows asynchronous termination of scanning loop.
        self.event_list = []
        self._show_progress = show_progress

        # Output Parameters (set_output)
        self._scan_only = False                     # -so/--scan-only
        self._comp_file = None                      # -o/--output
        self._fourcc = DEFAULT_VIDEOWRITER_CODEC    # -c/--codec

        # Motion Detection Parameters (set_detection_params)
        self._threshold = 0.15                      # -t/--threshold
        self._kernel = None                         # -k/--kernel-size
        self._downscale_factor = 1                  # -df/--downscale-factor

        # TODO: Remove args, replace with explicit methods (#33)
        # Remaining parameters to transition to named methods:
        self._cap = None
        self._cap_path = None

        self._video_resolution = None
        self.video_fps = None
        self.video_paths = args.input
        self.frames_total = 0
        self.frames_processed = 0

        # Check the input video(s) and obtain the framerate/resolution.
        if self._load_input_videos():
            # Motion detection and output related arguments
            self._threshold = args.threshold
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

            # timecode and ROI:
            self.draw_timecode = args.draw_timecode
            self.roi = args.roi
            if self.roi is not None:
                if self.roi:
                    if len(self.roi) != 4:
                        self._logger.error(
                            "Error: ROI must be specified as a rectangle of the form x/y/w/h!\n"
                            "  For example: -roi 200 250 50 100")
                        return
                    for i in range(0, 4):
                        self.roi[i] = int(self.roi[i])
                else:
                    self.roi = []
            self.initialized = True


    def set_output(self, scan_only=False, comp_file=None, codec='XVID'):
        # type: (bool, str, str) -> None
        """ Sets the path and encoder codec to use when exporting videos.

        Arguments:
            scan_only (bool): If True, only scans input for motion, but
                does not write any video(s) to disk.  In this case,
                comp_file and codec are ignored.
            comp_file (str): If set, represents the path that all
                concatenated motion events will be written to.
                If None, each motion event will be saved as a separate file.
            codec (str): The four-letter identifier of the encoder/video
                codec to use when exporting motion events as videos.
                Possible values are: XVID, MP4V, MP42, H264.

        Raises:
            ValueError if codec is not four characters.
        """
        self._scan_only = scan_only
        self._comp_file = comp_file
        if len(codec) != 4:
            raise ValueError("codec must be exactly four (4) characters")
        self._fourcc = cv2.VideoWriter_fourcc(*codec.upper())


    def set_detection_params(self, threshold=0.15, kernel_size=None, downscale_factor=1):
        """ Sets motion detection parameters.

        Arguments:
            threshold (float): Threshold value representing the amount of motion
                in a frame required to trigger a motion event. Lower values
                require less movement, and are more sensitive to motion. If the
                threshold is too high, some movement in the scene may not be
                detected, while a threshold too low can trigger a false events.
            kernel_size (int): Size in pixels of the noise reduction kernel.
                Must be an odd integer greater than 1. If not set, will
                automatically be calculated based on input video resolution.
                If too large, some movement in the scene may not be detected.
                Values < 0 are treated as if kernel_size is None. If kernel_size
                is set to 0, no noise reduction is performed.
            downscale_factor (int): Factor to downscale (shrink) video before
                processing, to improve performance. For example, if input video
                resolution is 1024 x 400, and factor=2, each frame is reduced to'
                1024/2 x 400/2=512 x 200 before processing. 1 (the default)
                indicates no downscaling.
        Raises:
            ValueError if kernel_size is not odd, or downscale_factor < 1.
        """
        self._threshold = threshold

        if downscale_factor < 1:
            raise ValueError("Downscale factor must be at least 1.")
        self._downscale_factor = downscale_factor

        if kernel_size is None or kernel_size < 0:
            # If kernel_size is None, set based on video resolution.
            video_width = self._video_resolution[0] / float(self._downscale_factor)
            if video_width >= 1920:
                kernel_size = 7
            elif video_width >= 1280:
                kernel_size = 5
            else:
                kernel_size = 3
        if (kernel_size % 2) == 0:
            raise ValueError("kernel_size must be odd (or None)")
        self._kernel = None if kernel_size == 0 else (
            np.ones((kernel_size, kernel_size), np.uint8))


    def _load_input_videos(self):
        """ Opens and checks that all input video files are valid, can
        be processed, and have the same resolution and framerate. """
        if not len(self.video_paths) > 0:
            return False
        for video_path in self.video_paths:
            cap = cv2.VideoCapture()
            cap.open(video_path)
            video_name = os.path.basename(video_path)
            if not cap.isOpened():
                self._logger.error("Error: Couldn't load video %s.", video_name)
                self._logger.info("Check that the given file is a valid video"
                                  " clip, and ensure all required software dependencies"
                                  " are installed and configured properly.")
                cap.release()
                return False
            curr_resolution = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                               int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            curr_framerate = cap.get(cv2.CAP_PROP_FPS)
            self.frames_total += cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if self._video_resolution is None and self.video_fps is None:
                self._video_resolution = curr_resolution
                self.video_fps = curr_framerate
                self._logger.info(
                    "Opened video %s (%d x %d at %2.3f FPS).",
                    video_name, self._video_resolution[0],
                    self._video_resolution[1], self.video_fps)
            # Check that all other videos specified have the same resolution
            # (we'll assume the framerate is the same if the resolution matches,
            # since the VideoCapture FPS information is not always accurate).
            elif curr_resolution != self._video_resolution:
                self._logger.error(
                    "Error: Can't append clip %s, video resolution"
                    " does not match the first input file.", video_name)
                return False
            self._logger.info("Appended video %s.", video_name)
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
                self._logger.error("Error: Unable to load video for processing.")
                self._cap = None

        return None

    def _stamp_text(self, frame, text, line):
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        margin = 5
        thickness = 2
        color = (255, 255, 255)

        size = cv2.getTextSize(text, font, font_scale, thickness)

        text_width = size[0][0]
        text_height = size[0][1]
        line_height = text_height + size[1] + margin

        text_pos = (margin, margin + size[0][1] + line * line_height)
        cv2.rectangle(frame, (margin, margin),
                      (margin + text_width, margin + text_height + 2), (0, 0, 0), -1)
        cv2.putText(frame, text, text_pos, font, font_scale, color, thickness)
        return None

    def scan_motion(self):
        """ Performs motion analysis on the ScanContext's input video(s). """
        if self.initialized is not True:
            self._logger.error("Error: Scan context uninitialized, no analysis performed.")
            return
        self._logger.info("Scanning %s for motion events...",
            "%d input videos" % len(self.video_paths) if len(self.video_paths) > 1
            else "input video")

        bg_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=False)
        buffered_frames = []
        event_window = []
        self.event_list = []
        num_frames_post_event = 0
        event_start = None

        video_writer = None
        output_prefix = ''
        if self._comp_file:
            video_writer = cv2.VideoWriter(self._comp_file, self._fourcc,
                                           self.video_fps, self._video_resolution)
        elif len(self.video_paths[0]) > 0:
            output_prefix = os.path.basename(self.video_paths[0])
            dot_index = output_prefix.rfind('.')
            if dot_index > 0:
                output_prefix = output_prefix[:dot_index]

        curr_pos = FrameTimecode(self.video_fps, 0)
        #curr_state = 'no_event'     # 'no_event', 'in_event', or 'post_even
        in_motion_event = False
        self.frames_processed = 0
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
            self._logger.info("Selecting area of interest:")
            frame_for_crop = self._get_next_frame()
            if self.draw_timecode:
                self._stamp_text(frame_for_crop, curr_pos.get_timecode(), 0)
            self.roi = cv2.selectROI("DVR-Scan ROI Selection", frame_for_crop)
            cv2.destroyAllWindows()
            if all([coord == 0 for coord in self.roi]):
                self._logger.info("ROI selection cancelled. Aborting...")
                return
        # Motion event scanning/detection loop.
        assert self.roi is None or len(self.roi) == 4
        if self.roi:
            self._logger.info("ROI selected (x,y,w,h): %s", str(self.roi))


        tqdm = dvr_scan.platform.get_tqdm()
        progress_bar = None
        self.frames_total = int(self.frames_total)
        if tqdm is not None and self.frames_total > 0 and self._show_progress:
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
            # Cut frame to selected sub-set if ROI area provided.
            if self.roi:
                frame_rgb = frame_rgb[
                    int(self.roi[1]):int(self.roi[1] + self.roi[3]),
                    int(self.roi[0]):int(self.roi[0] + self.roi[2])]
            # Apply downscaling factor if provided.
            if self._downscale_factor > 1:
                frame_rgb = frame_rgb[
                    ::self._downscale_factor, ::self._downscale_factor, :]

            frame_gray = cv2.cvtColor(frame_rgb, cv2.COLOR_BGR2GRAY)
            frame_mask = bg_subtractor.apply(frame_gray)
            if self._kernel is not None:
                frame_filt = cv2.morphologyEx(frame_mask, cv2.MORPH_OPEN, self._kernel)
            else:
                frame_filt = frame_mask
            frame_score = np.sum(frame_filt) / float(frame_filt.shape[0] * frame_filt.shape[1])
            event_window.append(frame_score)
            event_window = event_window[-self.min_event_len.frame_num:]

            if in_motion_event:
                # in event or post event, write all queued frames to file,
                # and write current frame to file.
                # if the current frame doesn't meet the threshold, increment
                # the current scene's post-event counter.
                if not self._scan_only:
                    if self.draw_timecode:
                        self._stamp_text(frame_rgb_origin, curr_pos.get_timecode(), 0)
                    video_writer.write(frame_rgb_origin)
                if frame_score >= self._threshold:
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
                        if not self._comp_file and not self._scan_only:
                            video_writer.release()
            else:
                if not self._scan_only:
                    buffered_frames.append(frame_rgb_origin)
                    buffered_frames = buffered_frames[-self.pre_event_len.frame_num:]
                if len(event_window) >= self.min_event_len.frame_num and all(
                        score >= self._threshold for score in event_window):
                    in_motion_event = True
                    event_window = []
                    num_frames_post_event = 0
                    event_start = FrameTimecode(
                        self.video_fps, curr_pos.frame_num)
                    # Open new VideoWriter if needed, write buffered_frames to file.
                    if not self._scan_only:
                        if not self._comp_file:
                            output_path = '%s.DSME_%04d.avi' % (
                                output_prefix, len(self.event_list))
                            video_writer = cv2.VideoWriter(
                                output_path, self._fourcc, self.video_fps,
                                self._video_resolution)
                        for frame in buffered_frames:
                            if self.draw_timecode:
                                self._stamp_text(frame, curr_pos.get_timecode(), 0)
                            video_writer.write(frame)
                        buffered_frames = []

            curr_pos.frame_num += 1
            self.frames_processed += 1
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

        processing_time = time.time() - processing_start
        processing_rate = float(self.frames_processed) / processing_time
        self._logger.info(
            "Processed %d frames read in %3.1f secs (avg %3.1f FPS).",
            self.frames_processed, processing_time, processing_rate)
        if not len(self.event_list) > 0:
            self._logger.info("No motion events detected in input.")
            return

        self._logger.info("Detected %d motion events in input.", len(self.event_list))

        if self.event_list:
            output_strs = [
                "-------------------------------------------------------------",
                "|   Event #    |  Start Time  |   Duration   |   End Time   |",
                "-------------------------------------------------------------" ]
            output_strs += [
                "|  Event %4d  |  %s  |  %s  |  %s  |" % (
                    event_num + 1, event_start.get_timecode(precision=1),
                    event_duration.get_timecode(precision=1),
                    event_end.get_timecode(precision=1))
                for event_num, (event_start, event_end, event_duration)
                in enumerate(self.event_list) ]
            output_strs += [
                "-------------------------------------------------------------" ]
            self._logger.info("Scan-only mode specified, list of motion events:\n%s",
                              '\n'.join(output_strs))

            timecode_list = []
            for event_start, event_end, event_duration in self.event_list:
                timecode_list.append(event_start.get_timecode())
                timecode_list.append(event_end.get_timecode())
            print("[DVR-Scan] Comma-separated timecode values:\n%s" % (
                ','.join(timecode_list)))

        if not self._scan_only:
            self._logger.info("Motion events written to disk.")
