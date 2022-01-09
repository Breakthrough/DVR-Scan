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
# Copyright (C) 2016-2022 Brandon Castellano <http://www.bcastell.com>.
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


class VideoLoadFailure(Exception):
    """ Raised when the input video(s) fail to load. """
    def __init__(self, message="One or more videos(s) failed to load!"):
        # type: (str)
        super(VideoLoadFailure, self).__init__(message)


class ScanContext(object):
    """ The ScanContext object represents the DVR-Scan program state,
    which includes application initialization, handling the options,
    and coordinating overall application logic (via scan_motion()). """

    def __init__(self, input_videos, frame_skip=0, show_progress=False):
        # type: (..., bool) -> None
        """ Initializes the ScanContext with the supplied arguments.

        Arguments:
            input_videos (List[str]): List of paths of videos to process.
            frame_skip (int): Skip every 1 in (frame_skip+1) frames to
                speed up processing at expense of accuracy (default is 0
                for no frame skipping).
            show_progress: Shows a progress bar if tqdm is available.
        """

        self._logger = logging.getLogger('dvr_scan')
        self._logger.info("Initializing scan context...")

        self.running = True         # Allows asynchronous termination of scanning loop.
        self.event_list = []
        self._show_progress = show_progress

        # Output Parameters (set_output)
        self._scan_only = True                      # -so/--scan-only
        self._comp_file = None                      # -o/--output
        self._fourcc = DEFAULT_VIDEOWRITER_CODEC    # -c/--codec
        self._draw_timecode = False                 # -tc/--time-code

        # Motion Detection Parameters (set_detection_params)
        self._threshold = 0.15                      # -t/--threshold
        self._kernel = None                         # -k/--kernel-size
        self._downscale_factor = 1                  # -df/--downscale-factor
        self._roi = None                            # --roi
        self._max_roi_size = dvr_scan.platform.get_min_screen_bounds()
        self._show_roi_window = False

        # Motion Event Parameters (set_event_params)
        self._min_event_len = None                  # -l/--min-event-length
        self._pre_event_len = None                  # -tb/--time-before-event
        self._post_event_len = None                 # -tp/--time-post-event

        # Input Video Parameters
        self._video_paths = input_videos            # -i/--input
        self._frame_skip = frame_skip               # -fs/--frame-skip
        self._start_time = None                     # -st/--start-time
        self._end_time = None                       # -et/--end-time

        self._cap = None
        self._cap_path = None
        self._video_resolution = None
        self._video_fps = None
        self._frames_total = 0
        self._frames_processed = 0

        self._load_input_videos()

    def set_output(self, scan_only=True, comp_file=None, codec='XVID', draw_timecode=False):
        # type: (bool, str, str) -> None
        """ Sets the path and encoder codec to use when exporting videos.

        Arguments:
            scan_only (bool): If True, only scans input for motion, but
                does not write any video(s) to disk.  In this case,
                comp_file and codec are ignored. Note that the default
                value here is the opposite of the CLI default.
            comp_file (str): If set, represents the path that all
                concatenated motion events will be written to.
                If None, each motion event will be saved as a separate file.
            codec (str): The four-letter identifier of the encoder/video
                codec to use when exporting motion events as videos.
                Possible values are: XVID, MP4V, MP42, H264.
            draw_timecode (bool): If True, draws timecode on each frame.

        Raises:
            ValueError if codec is not four characters.
        """
        self._scan_only = scan_only
        self._comp_file = comp_file
        if len(codec) != 4:
            raise ValueError("codec must be exactly four (4) characters")
        self._fourcc = cv2.VideoWriter_fourcc(*codec.upper())
        self._draw_timecode = draw_timecode


    def set_detection_params(self, threshold=0.15, kernel_size=None,
                             downscale_factor=1, roi=None):
        # type: (float, int, int) -> None
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
            roi (List[int]): Rectangle of form [x y w h] representing bounding
                box of subset of each frame to look at. If an empty list, the ROI
                is set by popping up a GUI window when scan_motion() is called.
        Raises:
            ValueError if kernel_size is not odd, downscale_factor < 1, or roi
            is invalid.
        """
        assert self._video_resolution is not None

        self._threshold = threshold

        if downscale_factor < 1:
            raise ValueError("Error: Downscale factor must be at least 1.")
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
            raise ValueError("Error: kernel_size must be odd (or None)")
        self._kernel = None if kernel_size == 0 else (
            np.ones((kernel_size, kernel_size), np.uint8))

        # Validate ROI.
        error_string = (
            'ROI must be specified as a rectangle of the form (x,y,w,h) or '
            'the max window size (w,h).\n  For example: -roi 200 250 50 100')
        if roi is not None:
            if roi:
                if not all(isinstance(i, int) for i in roi):
                    roi = [i.replace(',', '') for i in roi]
                    if any(not i.isdigit() for i in roi):
                        raise ValueError(
                            'Error: Non-numeric character specified in ROI.\n%s' % error_string)
                roi = [int(x) for x in roi]
                if any(x < 0 for x in roi):
                    raise ValueError('Error: value passed to -roi was negative')
                if len(roi) == 2:
                    self._max_roi_size = roi
                    self._show_roi_window = True
                elif len(roi) == 4:
                    self._roi = roi
                    self._show_roi_window = False
                else:
                    raise ValueError('Error: %s' % error_string)
            # -roi
            else:
                self._show_roi_window = True

    def set_event_params(self, min_event_len=2, time_pre_event="1.5s", time_post_event="2s"):
        # type: (...) -> None
        """ Sets motion event parameters. """
        assert self._video_fps is not None
        self._min_event_len = FrameTimecode(min_event_len, self._video_fps)
        # Make sure minimum event length is at least 1.
        if not self._min_event_len.frame_num >= 1:
            raise ValueError('min_event_len must be >= 1!')
        self._pre_event_len = FrameTimecode(time_pre_event, self._video_fps)
        self._post_event_len = FrameTimecode(time_post_event, self._video_fps)

    def set_video_time(self, start_time=None, end_time=None, duration=None):
        # type: (str, str, str) -> None
        """ Used to select a sub-set of the video in time for processing. """
        assert self._video_fps is not None
        if start_time is not None:
            self._start_time = FrameTimecode(start_time, self._video_fps)
        if duration is not None:
            duration = FrameTimecode(duration, self._video_fps)
            if self._start_time is not None:
                self._end_time = FrameTimecode(
                    self._start_time.frame_num + duration.frame_num, self._video_fps)
            else:
                self._end_time = duration
        elif end_time is not None:
            self._end_time = FrameTimecode(end_time, self._video_fps)

    def _load_input_videos(self):
        # type: () -> bool
        """ Opens and checks that all input video files are valid, can
        be processed, and have the same resolution and framerate. """
        if not len(self._video_paths) > 0:
            raise VideoLoadFailure()
        for video_path in self._video_paths:
            cap = cv2.VideoCapture()
            cap.open(video_path)
            video_name = os.path.basename(video_path)
            if not cap.isOpened():
                self._logger.error("Error: Couldn't load video %s.", video_name)
                self._logger.info("Check that the given file is a valid video"
                                  " clip, and ensure all required software dependencies"
                                  " are installed and configured properly.")
                cap.release()
                raise VideoLoadFailure()
            curr_resolution = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                               int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            curr_framerate = cap.get(cv2.CAP_PROP_FPS)
            self._frames_total += int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            if self._video_resolution is None and self._video_fps is None:
                self._video_resolution = curr_resolution
                self._video_fps = curr_framerate
                self._logger.info(
                    "Opened video %s (%d x %d at %2.3f FPS).",
                    video_name, self._video_resolution[0],
                    self._video_resolution[1], self._video_fps)
            # Check that all other videos specified have the same resolution
            # (we'll assume the framerate is the same if the resolution matches,
            # since the VideoCapture FPS information is not always accurate).
            elif curr_resolution != self._video_resolution:
                self._logger.error(
                    "Error: Can't append clip %s, video resolution"
                    " does not match the first input file.", video_name)
                raise VideoLoadFailure()
            self._logger.info("Appended video %s.", video_name)
        # Make sure we initialize defaults.
        self.set_detection_params()
        self.set_event_params()
        self.set_video_time()


    def _get_next_frame(self, retrieve=True):
        # type: (Optional[bool]) -> Optional[numpy.ndarray]
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

        if self._cap is None and len(self._video_paths) > 0:
            self._cap_path = self._video_paths[0]
            self._video_paths = self._video_paths[1:]
            self._cap = cv2.VideoCapture(self._cap_path)
            if self._cap.isOpened():
                return self._get_next_frame()
            else:
                self._logger.error("Error: Unable to load video for processing.")
                self._cap = None

        return None


    def _stamp_text(self, frame, text, line=0):
        # type: (numpy.ndarray, str, Optional[int]) -> None
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


    def _create_progress_bar(self, show_progress, num_frames):
        # type: (bool, int) -> tqdm.tqdm
        tqdm = None if not show_progress else dvr_scan.platform.get_tqdm()
        if tqdm is not None:
            if self._end_time and self._end_time.frame_num < num_frames:
                num_frames = self._end_time.frame_num
            if self._start_time:
                num_frames -= self._start_time.frame_num
            if num_frames < 0:
                num_frames = 0
            return tqdm.tqdm(
                total=num_frames,
                unit=' frames',
                desc="[DVR-Scan] Processed")
        class NullProgressBar(object):
            """ Acts like a tqdm.tqdm object, but really a no-operation. """
            def update(self, _):
                """ No-op. """
            def close(self):
                """ No-op. """
        return NullProgressBar()


    def _select_roi(self, curr_time=None, add_timecode=False):
        # type: (FrameTimecode, bool) -> bool
        # area selection
        if self._show_roi_window:
            self._logger.info("Selecting area of interest:")
            frame_for_crop = self._get_next_frame()
            scale_factor = None
            if self._max_roi_size is not None:
                frame_h, frame_w = (frame_for_crop.shape[0], frame_for_crop.shape[1])
                max_w, max_h = self._max_roi_size
                if frame_h > max_h or frame_w > max_w:
                    factor_h = frame_h / float(max_h)
                    factor_w = frame_w / float(max_w)
                    scale_factor = max(factor_h, factor_w)
                    new_height = int(frame_h / scale_factor)
                    new_width = int(frame_w / scale_factor)
                    frame_for_crop = cv2.resize(
                        frame_for_crop, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            # Downscale the image if it's too large for the screen.
            #if self._max_roi_size is not None and frame_for_crop.shape[0]
            if add_timecode:
                assert curr_time is not None
                self._stamp_text(frame_for_crop, curr_time.get_timecode())
            roi = cv2.selectROI("DVR-Scan ROI Selection", frame_for_crop)
            cv2.destroyAllWindows()
            if any([coord == 0 for coord in roi[2:]]):
                self._logger.info("ROI selection cancelled. Aborting...")
                return False
            # Unscale coordinates if we downscaled the image.
            if scale_factor:
                roi = [int(x * scale_factor) for x in roi]
            self._roi = roi
        if self._roi:
            self._logger.info("ROI selected (x,y,w,h): %s", str(self._roi))
        return True


    def scan_motion(self, method='mog'):
        # type: () -> None
        """ Performs motion analysis on the ScanContext's input video(s). """
        if method.lower() == 'cnt':
            bg_subtractor = cv2.bgsegm.createBackgroundSubtractorCNT()
        else:
            bg_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=False)
        buffered_frames = []
        event_window = []
        self.event_list = []
        num_frames_post_event = 0
        event_start = None

        video_writer = None
        output_prefix = ''
        if not self._comp_file and len(self._video_paths[0]) > 0:
            output_prefix = os.path.basename(self._video_paths[0])
            dot_index = output_prefix.rfind('.')
            if dot_index > 0:
                output_prefix = output_prefix[:dot_index]

        curr_pos = FrameTimecode(0, self._video_fps)
        in_motion_event = False
        self._frames_processed = 0
        processing_start = time.time()

        # Seek to starting position if required.
        if self._start_time is not None:
            while curr_pos.frame_num < self._start_time.frame_num:
                if self._get_next_frame(False) is None:
                    break
                self._frames_processed += 1
                curr_pos.frame_num += 1

        # Show ROI selection window if required.
        if not self._select_roi(
            curr_time=curr_pos, add_timecode=self._draw_timecode):
            return

        # TQDM-based progress bar, or a stub if in quiet mode (or no TQDM).
        progress_bar = self._create_progress_bar(
            show_progress=self._show_progress, num_frames=self._frames_total)

        self._logger.info("Scanning %s for motion events...",
            "%d input videos" % len(self._video_paths) if len(self._video_paths) > 1
            else "input video")

        # Length of buffer we require in memory to keep track of all frames required for -l and -tb.
        buff_len = self._pre_event_len.frame_num + self._min_event_len.frame_num

        # Motion event scanning/detection loop.
        while self.running:
            if self._end_time is not None and curr_pos.frame_num >= self._end_time.frame_num:
                break
            if self._frame_skip > 0:
                for _ in range(self._frame_skip):
                    if self._get_next_frame(False) is None:
                        break
                    curr_pos.frame_num += 1
                    self._frames_processed += 1
                    progress_bar.update(1)
            frame_rgb = self._get_next_frame()
            if frame_rgb is None:
                break
            frame_rgb_origin = frame_rgb
            # Cut frame to selected sub-set if ROI area provided.
            if self._roi:
                frame_rgb = frame_rgb[
                    int(self._roi[1]):int(self._roi[1] + self._roi[3]),
                    int(self._roi[0]):int(self._roi[0] + self._roi[2])]
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
            event_window = event_window[-self._min_event_len.frame_num:]

            if in_motion_event:
                # in event or post event, write all queued frames to file,
                # and write current frame to file.
                # if the current frame doesn't meet the threshold, increment
                # the current scene's post-event counter.
                if not self._scan_only:
                    if self._draw_timecode:
                        self._stamp_text(frame_rgb_origin, curr_pos.get_timecode())
                    video_writer.write(frame_rgb_origin)
                if frame_score >= self._threshold:
                    num_frames_post_event = 0
                else:
                    num_frames_post_event += 1
                    if num_frames_post_event >= self._post_event_len.frame_num:
                        in_motion_event = False
                        event_end = FrameTimecode(
                            curr_pos.frame_num, self._video_fps)
                        event_duration = FrameTimecode(
                            curr_pos.frame_num - event_start.frame_num, self._video_fps)
                        self.event_list.append((event_start, event_end, event_duration))
                        if not self._comp_file and not self._scan_only:
                            video_writer.release()
            else:
                buffered_frames.append(
                    (frame_rgb_origin if not self._scan_only else None,
                     FrameTimecode(curr_pos.frame_num, curr_pos.framerate)))
                buffered_frames = buffered_frames[-buff_len:]
                if len(event_window) >= self._min_event_len.frame_num and all(
                        score >= self._threshold for score in event_window):
                    in_motion_event = True
                    event_window = []
                    num_frames_post_event = 0
                    # Need to add 1 since the frame is included in buffered_frames
                    # (i.e. on frame 0, len(buffered_frames) == 1).
                    shifted_start = 1 + curr_pos.frame_num - len(buffered_frames)
                    if shifted_start < 0:
                        shifted_start = 0
                    event_start = FrameTimecode(shifted_start, self._video_fps)
                    # Open new VideoWriter if needed, write buffered_frames to file.
                    if not self._scan_only:
                        if not self._comp_file or video_writer is None:
                            output_path = (
                                self._comp_file if self._comp_file else
                                '%s.DSME_%04d.avi' % (output_prefix, len(self.event_list)))
                            video_writer = cv2.VideoWriter(
                                output_path, self._fourcc, self._video_fps,
                                self._video_resolution)
                        for frame, frame_pos in buffered_frames:
                            if self._draw_timecode:
                                self._stamp_text(frame, frame_pos.get_timecode())
                            video_writer.write(frame)
                    buffered_frames = []

            curr_pos.frame_num += 1
            self._frames_processed += 1
            progress_bar.update(1)

        # If we're still in a motion event, we still need to compute the duration
        # and ending timecode and add it to the event list.
        if in_motion_event:
            curr_pos.frame_num -= 1  # Correct for the increment at the end of the loop
            event_end = FrameTimecode(curr_pos.frame_num, self._video_fps)
            event_duration = FrameTimecode(
                curr_pos.frame_num - event_start.frame_num, self._video_fps)
            self.event_list.append((event_start, event_end, event_duration))

        if video_writer is not None:
            video_writer.release()
        if progress_bar is not None:
            progress_bar.close()

        self._post_scan_motion(processing_start=processing_start)

        return self.event_list


    def _post_scan_motion(self, processing_start):
        # type: (float) -> None
        processing_time = time.time() - processing_start
        processing_rate = float(self._frames_processed) / processing_time
        self._logger.info(
            "Processed %d frames read in %3.1f secs (avg %3.1f FPS).",
            self._frames_processed, processing_time, processing_rate)
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
                    event_num + 1,
                    event_start.get_timecode(precision=1),
                    event_duration.get_timecode(precision=1),
                    event_end.get_timecode(precision=1)
                )
                for event_num, (event_start, event_end, event_duration)
                in enumerate(self.event_list) ]
            output_strs += [
                "-------------------------------------------------------------" ]
            self._logger.info("List of motion events:\n%s", '\n'.join(output_strs))

            timecode_list = []
            for event_start, event_end, _ in self.event_list:
                timecode_list.append(event_start.get_timecode())
                timecode_list.append(event_end.get_timecode())
            print("[DVR-Scan] Comma-separated timecode values:\n%s" % (
                ','.join(timecode_list)))

        if not self._scan_only:
            self._logger.info("Motion events written to disk.")
