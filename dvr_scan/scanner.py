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
""" ``dvr_scan.scanner`` Module

This module contains the ScanContext class, which implements the
DVR-Scan program logic, as well as the motion detection algorithm.
"""

from dataclasses import dataclass
from enum import Enum
import logging
import os
import os.path
import queue
import sys
import time
import threading
from typing import Any, AnyStr, Iterable, List, Optional, Tuple, Union

import cv2
import numpy
from scenedetect import FrameTimecode, VideoStream, VideoOpenFailure, split_video_ffmpeg

from dvr_scan.overlays import BoundingBoxOverlay, TextOverlay
from dvr_scan.platform import get_min_screen_bounds, get_tqdm
from dvr_scan.motion_detector import (
    MotionDetectorMOG2,
    MotionDetectorCNT,
    MotionDetectorCudaMOG2,
)

logger = logging.getLogger('dvr_scan')

DEFAULT_VIDEOWRITER_CODEC = 'XVID'
"""Default codec to use with OpenCV VideoWriter."""

MAX_DECODE_QUEUE_SIZE: int = 4
"""Maximum size of the queue of frames waiting to be processed after decoding."""

MAX_ENCODE_QUEUE_SIZE: int = 4
"""Maximum size of the queue of frames waiting to be processed after decoding."""

COPY_OUTPUT_ARGS = '-map 0 -c:v copy -c:a copy'
"""Arguments passed to ffmpeg when using OutputMode.COPY."""

DEFAULT_FFMPEG_OUTPUT_ARGS = '-map 0 -c:v libx264 -preset fast -crf 21 -c:a aac'
"""Default arguments passed to ffmpeg when using OutputMode.COPY."""

OUTPUT_FILE_TEMPLATE = '{VIDEO_NAME}.DSME_{EVENT_NUMBER}.{EXTENSION}'
"""Template to use for generating output files."""


class DetectorType(Enum):
    MOG = MotionDetectorMOG2
    CNT = MotionDetectorCNT
    MOG_CUDA = MotionDetectorCudaMOG2


class OutputMode(Enum):
    SCAN_ONLY = 1
    OPENCV = 2
    COPY = 3
    FFMPEG = 4


@dataclass
class DecodeEvent:
    frame_rgb: numpy.ndarray
    timecode: FrameTimecode


@dataclass
class EncodeEvent:
    frame_rgb: numpy.ndarray
    timecode: FrameTimecode
    bounding_box: Tuple[int, int, int, int]
    end_of_event: bool = False


@dataclass
class FfmpegEvent:
    start_time: FrameTimecode
    end_time: FrameTimecode


@dataclass
class MaskEvent:
    motion_mask: numpy.ndarray
    # TODO: Add options to overlay timecode, overlay frame score, bounding box,
    # and option to blend original frame with mask.


def _scale_kernel_size(kernel_size: int, downscale_factor: int):
    corrected_size = round(kernel_size / float(downscale_factor))
    if corrected_size % 2 == 0:
        corrected_size -= 1
    return max(corrected_size, 3)


# TODO(#75): See if this needs to be tweaked for the CNT algorithm.
def _recommended_kernel_size(frame_width: int, downscale_factor: int) -> int:
    corrected_width = round(frame_width / float(downscale_factor))
    return 7 if corrected_width >= 1920 else 5 if corrected_width >= 1280 else 3


class ScanContext(object):
    """ The ScanContext object represents the DVR-Scan program state,
    which includes application initialization, handling the options,
    and coordinating overall application logic (via scan_motion()). """

    def __init__(self,
                 input_videos: List[AnyStr],
                 frame_skip: int = 0,
                 show_progress: bool = False):
        """ Initializes the ScanContext with the supplied arguments.

        Arguments:
            config_file: List of paths of videos to process.
            input_videos: List of paths of videos to process.
            frame_skip: Skip every 1 in (frame_skip+1) frames to speed up processing at
                expense of accuracy (default is 0 for no skipping).
            show_progress: Show a progress bar if tqdm is available.
        """

        self._logger = logging.getLogger('dvr_scan')
        self._logger.info("Initializing scan context...")

        self._stop = threading.Event()
        self._decode_thread_exception = None
        self._encode_thread_exception = None

        self.event_list = []
        self._in_motion_event = False

        self._show_progress = show_progress
        self._curr_pos = None     # FrameTimecode representing number of decoded frames
        self._num_corruptions = 0 # The number of times we failed to read a frame

        # Output Parameters (set_output)
        self._comp_file: Optional[AnyStr] = None       # -o/--output
        self._mask_file: Optional[AnyStr] = None       # -mo/--mask-output
        self._fourcc: Any = None                       # opencv-codec
        self._output_mode: OutputMode = None           # -m/--output-mode / -so/--scan-only
        self._ffmpeg_output_args: Optional[str] = None # output args for OutputMode.FFMPEG
        self._output_dir: AnyStr = ''                  # -d/--directory

        # Overlay Parameters (set_overlays)
        self._timecode_overlay = None # -tc/--time-code, None or TextOverlay
        self._bounding_box = None     # -bb/--bounding-box, None or BoundingBoxOverlay

        # Motion Detection Parameters (set_detection_params)
        self._threshold = 0.15     # -t/--threshold
        self._kernel_size = None   # -k/--kernel-size
        self._downscale_factor = 1 # -df/--downscale-factor
        self._roi = None           # --roi
        self._max_roi_size = None  # --roi
        self._show_roi_window = False

        # Motion Event Parameters (set_event_params)
        self._min_event_len = None  # -l/--min-event-length
        self._pre_event_len = None  # -tb/--time-before-event
        self._post_event_len = None # -tp/--time-post-event

        # Input Video Parameters
        self._video_paths: Iterable[AnyStr] = input_videos # -i/--input
        self._frame_skip: int = frame_skip                 # -fs/--frame-skip
        self._start_time: FrameTimecode = None             # -st/--start-time
        self._end_time: FrameTimecode = None               # -et/--end-time

        # TODO(v1.6): Put self._cap and video paths in a separate object that handles concatenation.
        # Doesn't need to handle seeking backwards, just forwards.
        self._cap: VideoStream = None
        self._cap_path: AnyStr = None
        self._video_resolution = None
        self._video_fps = None
        self._frames_total = 0
        self._frames_processed = 0
        self._first_input_path: AnyStr = '' # path of first input video
        self._output_prefix: AnyStr = ''    # path of the input video minus extension

        self._load_input_videos()

    @property
    def framerate(self) -> float:
        return self._video_fps

    def set_output(
        self,
        output_dir: AnyStr = '',
        comp_file: Optional[AnyStr] = None,
        mask_file: Optional[AnyStr] = None,
        output_mode: Union[OutputMode, str] = OutputMode.SCAN_ONLY,
        opencv_fourcc: str = DEFAULT_VIDEOWRITER_CODEC,
        ffmpeg_output_args: str = DEFAULT_FFMPEG_OUTPUT_ARGS,
    ):
        """ Sets the path and encoder codec to use when exporting videos.

        Arguments:
            output_dir: If set, folder where output files will be written to.
                If empty string, output will be the current working directory.
            comp_file: If set, represents path to single video that all motion events will
                be written to. Otherwise each motion event will be saved as a separate file
                based on the (first) input video filename.
            output_mode: The mode to use when generating/encoding the output file. Certain
                features may not be compatible with all ouptut modes.
            opencv_fourcc: The four-letter identifier of the encoder/video
                codec to use when output_mode is OutputMode.OPENCV. Possible values are:
                XVID, MP4V, MP42, H264.
            ffmpeg_out_args: Arguments to pass to ffmpeg for the output video. Only used if
                output_mode is OutputMode.FFMPEG.

        Raises:
            ValueError:
             - codec is not four characters
             - comp_file is set but output_mode is not OutputMode.OPENCV
             - output_dir is set but either comp_file or mask_file are absolute paths
             - multiple input videos and output_mode is not OutputMode.OPENCV
            KeyError:
             - output_mode does not exist in OutputMode
        """
        if output_dir:
            if comp_file and os.path.isabs(comp_file):
                raise ValueError("output file cannot be absolute path if output directory is set!")
            if mask_file and os.path.isabs(mask_file):
                raise ValueError("mask file cannot be absolute path if output directory is set!")
        if len(opencv_fourcc) != 4:
            raise ValueError("codec must be exactly FOUR (4) characters")
        if not isinstance(output_mode, OutputMode):
            output_mode = OutputMode[output_mode.upper().replace('-', '_')]
        if len(self._video_paths) > 1 and output_mode not in (OutputMode.SCAN_ONLY,
                                                              OutputMode.OPENCV):
            raise ValueError(
                "input concatenation is only supported in `scan-only` or `opencv` mode.")
        if comp_file is not None and output_mode != OutputMode.OPENCV:
            raise ValueError("output concatenation is only supported using output mode `opencv`")
        self._comp_file = comp_file
        self._mask_file = mask_file
        self._output_mode = (
            output_mode if isinstance(output_mode, OutputMode) else OutputMode[output_mode.upper()])
        self._fourcc = cv2.VideoWriter_fourcc(*opencv_fourcc.upper())
        self._ffmpeg_output_args = ffmpeg_output_args
        # If an output directory is defined, ensure it exists, and if not, try to create it.
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        self._output_dir = output_dir

    def set_overlays(self,
                     timecode_overlay: Optional[TextOverlay] = None,
                     bounding_box: Optional[BoundingBoxOverlay] = None):
        """ Sets options to use if/when drawing overlays on the resulting frames.

        Arguments:
            draw_timecode: If True, draw a timecode (presentation time) on each frame.
            bounding_box_smoothing: Value to use for temporal smoothing (in time) for drawing a
                bounding box containing all detected motion in each frame. If None, no box will
                be drawn. If <= 1, smoothing will be disabled.
        """
        self._timecode_overlay = timecode_overlay
        self._bounding_box = bounding_box

    def set_detection_params(self,
                             threshold: float = 0.15,
                             kernel_size: Optional[int] = None,
                             downscale_factor: int = 1,
                             roi: Optional[List[int]] = None):
        """ Sets motion detection parameters.

        Arguments:
            threshold (float): Threshold value representing the amount of motion
                in a frame required to trigger a motion event. Lower values
                require less movement, and are more sensitive to motion. If the
                threshold is too high, some movement in the scene may not be
                detected, while a threshold too low can trigger a false events.
            kernel_size (int): Size in pixels of the noise reduction kernel.
                Must be an odd integer greater than 1. If None, size will
                automatically be calculated based on input video resolution.
                If too large, some movement in the scene may not be detected.
            downscale_factor (int): Factor to downscale (shrink) video before
                processing, to improve performance. For example, if input video
                resolution is 1024 x 400, and factor=2, each frame is reduced to'
                1024/2 x 400/2=512 x 200 before processing. 0 or 1 (default)
                indicate no downscaling.
            roi (List[int]): Rectangle of form [x y w h] representing bounding
                box of subset of each frame to look at. If an empty list, the ROI
                is set by popping up a GUI window when scan_motion() is called.
        Raises:
            ValueError if kernel_size is not odd, downscale_factor < 0, or roi
            is invalid.
        """
        assert self._video_resolution is not None

        self._threshold = threshold

        if downscale_factor < 0:
            raise ValueError("Error: Downscale factor must be positive.")
        self._downscale_factor = max(downscale_factor, 1)

        if not kernel_size is None:
            if kernel_size < 3 or (kernel_size % 2) == 0:
                raise ValueError("Error: kernel_size must be odd number greater than 1, or None")
        self._kernel_size = kernel_size

        # Validate ROI.
        if roi is not None:
            if roi:
                if not all(isinstance(i, int) for i in roi):
                    raise TypeError('Error: Non-integral type found in specified roi.')
                if any(x < 0 for x in roi):
                    raise ValueError('Error: Negative value found in roi.')
                if len(roi) == 2:
                    self._max_roi_size = roi
                    self._show_roi_window = True
                elif len(roi) == 4:
                    self._roi = roi
                    self._show_roi_window = False
                else:
                    raise ValueError('Error: Expected either 2 or 4 elements in roi.')
            # -roi with no arguments.
            else:
                self._show_roi_window = True

    def set_event_params(self,
                         min_event_len: int = 2,
                         time_pre_event: Union[int, float, str] = "1.5s",
                         time_post_event: Union[int, float, str] = "2s"):
        """ Sets motion event parameters. """
        assert self._video_fps is not None
        self._min_event_len = FrameTimecode(min_event_len, self._video_fps)
        # Make sure minimum event length is at least 1.
        if not self._min_event_len.frame_num >= 1:
            raise ValueError('min_event_len must be >= 1 frame!')
        self._pre_event_len = FrameTimecode(time_pre_event, self._video_fps)
        self._post_event_len = FrameTimecode(time_post_event, self._video_fps)

    def set_video_time(self,
                       start_time: Optional[Union[int, float, str]] = None,
                       end_time: Optional[Union[int, float, str]] = None,
                       duration: Optional[Union[int, float, str]] = None):
        """ Used to select a sub-set of the video in time for processing. """
        assert self._video_fps is not None
        if start_time is not None:
            self._start_time = FrameTimecode(start_time, self._video_fps)
        if duration is not None:
            duration = FrameTimecode(duration, self._video_fps)
            if self._start_time is not None:
                self._end_time = self._start_time + duration.frame_num
            else:
                self._end_time = duration
        elif end_time is not None:
            self._end_time = FrameTimecode(end_time, self._video_fps)

    def _load_input_videos(self):
        """ Opens and checks that all input video files are valid, can
        be processed, and have the same resolution and framerate. """
        if not len(self._video_paths) > 0:
            raise VideoOpenFailure()
        for i, video_path in enumerate(self._video_paths):
            cap = cv2.VideoCapture()
            cap.open(video_path)
            video_name = os.path.basename(video_path)
            if not cap.isOpened():
                self._logger.error("Error: Couldn't load video %s.", video_name)
                self._logger.info("Check that the given file is a valid video"
                                  " clip, and ensure all required software dependencies"
                                  " are installed and configured properly.")
                cap.release()
                raise VideoOpenFailure()
            curr_resolution = (round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                               round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            curr_framerate = cap.get(cv2.CAP_PROP_FPS)
            self._frames_total += round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            if self._video_resolution is None and self._video_fps is None:
                self._video_resolution = curr_resolution
                self._video_fps = curr_framerate
                self._logger.info("Opened video %s (%d x %d at %2.3f FPS).", video_name,
                                  self._video_resolution[0], self._video_resolution[1],
                                  self._video_fps)
            # Check that all other videos specified have the same resolution
            # (we'll assume the framerate is the same if the resolution matches,
            # since the VideoCapture FPS information is not always accurate).
            elif curr_resolution != self._video_resolution:
                self._logger.error(
                    "Error: Can't append clip %s, video resolution"
                    " does not match the first input file.", video_name)
                raise VideoOpenFailure()
            if i > 0:
                self._logger.info("Appended video %s.", video_name)
        # Make sure we initialize defaults.
        self.set_detection_params()
        self.set_event_params()
        self.set_video_time()

    def _get_next_frame(self,
                        retrieve: bool = True,
                        num_retries: int = 5) -> Optional[numpy.ndarray]:
        """ Returns a new frame from the current series of video files,
        or None when no more frames are available. """
        assert num_retries >= 0

        if self._cap:
            for _ in range(num_retries + 1):
                if retrieve:
                    (ret_val, frame) = self._cap.read()
                else:
                    ret_val = self._cap.grab()
                    frame = True
                if ret_val:
                    self._curr_pos += 1
                    return frame
                elif self._frames_total > 0 and self._curr_pos.frame_num >= self._frames_total:
                    break
                self._num_corruptions += 1
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

    # TODO(v1.6): Assume tqdm is available now as it is listed as a required package.
    def _create_progress_bar(self, show_progress: bool):
        """Create and return a `tqdm` object. If show_progress is False, a fake is returned."""
        tqdm = None if not show_progress else get_tqdm()
        if tqdm is not None:
            num_frames = self._frames_total
            # Correct for end time.
            if self._end_time and self._end_time.frame_num < num_frames:
                num_frames = self._end_time.frame_num
            # Correct for current seek position.
            num_frames = max(0, num_frames - self._curr_pos.frame_num)
            return tqdm.tqdm(
                total=num_frames, unit=' frames', desc="[DVR-Scan] Processed", dynamic_ncols=True)

        class NullProgressBar(object):
            """ Acts like a tqdm.tqdm object, but really a no-operation. """

            def update(self, _):
                """ No-op. """

            def close(self):
                """ No-op. """

        return NullProgressBar()

    def _select_roi(self) -> bool:
        # area selection
        if self._show_roi_window:
            self._logger.info("Selecting area of interest:")
            frame_for_crop = self._get_next_frame()
            scale_factor = None
            if self._max_roi_size is None:
                self._max_roi_size = get_min_screen_bounds()
            if self._max_roi_size is not None:
                frame_h, frame_w = (frame_for_crop.shape[0], frame_for_crop.shape[1])
                max_w, max_h = self._max_roi_size
                # Downscale the image if it's too large for the screen.
                if frame_h > max_h or frame_w > max_w:
                    factor_h = frame_h / float(max_h)
                    factor_w = frame_w / float(max_w)
                    scale_factor = max(factor_h, factor_w)
                    new_height = round(frame_h / scale_factor)
                    new_width = round(frame_w / scale_factor)
                    frame_for_crop = cv2.resize(
                        frame_for_crop, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            roi = cv2.selectROI("DVR-Scan ROI Selection", frame_for_crop)
            cv2.destroyAllWindows()
            if any([coord == 0 for coord in roi[2:]]):
                self._logger.info("ROI selection cancelled. Aborting...")
                return False
            # Unscale coordinates if we downscaled the image.
            if scale_factor:
                roi = [round(x * scale_factor) for x in roi]
            self._roi = roi
        if self._roi:
            self._logger.info(
                'ROI set: (x,y)/(w,h) = (%d,%d)/(%d,%d)',
                self._roi[0],
                self._roi[1],
                self._roi[2],
                self._roi[3],
            )
        return True

    def _set_paths(self, video_path: AnyStr):
        self._output_prefix = ''
        self._first_input_path = video_path
        if not self._comp_file:
            output_prefix = os.path.basename(video_path)
            dot_index = output_prefix.rfind('.')
            if dot_index > 0:
                output_prefix = output_prefix[:dot_index]
            self._output_prefix = output_prefix

    def stop(self):
        """Stop the current scan_motion call. This is the only thread-safe public method."""
        self._stop.set()
        self._logger.debug("Stop event set.")

    def scan_motion(
        self,
        detector_type: DetectorType = DetectorType.MOG,
    ) -> List[Tuple[FrameTimecode, FrameTimecode, FrameTimecode]]:
        """ Performs motion analysis on the ScanContext's input video(s). """
        self._stop.clear()
        buffered_frames = []
        event_window = []
        self.event_list = []
        num_frames_post_event = 0
        event_start = None
        self._set_paths(self._video_paths[0])

        self._curr_pos = FrameTimecode(0, self._video_fps)
        in_motion_event = False
        self._frames_processed = 0
        processing_start = time.time()

        # Seek to starting position if required.
        if self._start_time is not None:
            while self._curr_pos.frame_num < self._start_time.frame_num:
                if self._get_next_frame(False) is None:
                    break
        start_frame = self._curr_pos.frame_num

        # Show ROI selection window if required.
        if not self._select_roi():
            return

        # Initialize overlays.
        if self._roi is not None:
            assert len(self._roi) == 4 and all([isinstance(coord, int) for coord in self._roi])
        if self._bounding_box:
            self._bounding_box.set_corrections(
                downscale_factor=self._downscale_factor, roi=self._roi, frame_skip=self._frame_skip)

        # Calculate size of noise reduction kernel.
        if self._kernel_size is None:
            kernel_size = _recommended_kernel_size(self._video_resolution[0],
                                                   self._downscale_factor)
        else:
            kernel_size = _scale_kernel_size(self._kernel_size, self._downscale_factor)
        assert kernel_size >= 1 and kernel_size % 2 == 1

        # Create motion detector.
        logger.debug('Using detector %s with params: kernel_size = %d', detector_type.name,
                     kernel_size)
        motion_detector = detector_type.value(kernel_size=kernel_size)

        # Correct pre/post and minimum event lengths to account for frame skip factor.
        post_event_len: int = self._post_event_len.frame_num // (self._frame_skip + 1)
        pre_event_len: int = self._pre_event_len.frame_num // (self._frame_skip + 1)
        # min_event_len must be at least 1
        min_event_len: int = max(self._min_event_len.frame_num // (self._frame_skip + 1), 1)
        # Ensure that we include the exact amount of time specified in `-tb`/`--time-before` when
        # shifting the event start time. Instead of using `-l`/`--min-event-len` directly, we
        # need to compensate for rounding errors when we corrected it for frame skip. This is
        # important as this affects the number of frames we consider for the actual motion event.
        start_event_shift: int = (
            self._pre_event_len.frame_num + min_event_len * (self._frame_skip + 1))

        # Length of buffer we require in memory to keep track of all frames required for -l and -tb.
        buff_len = pre_event_len + min_event_len
        event_end = FrameTimecode(timecode=0, fps=self._video_fps)
        last_frame_above_threshold = 0

        # Motion event scanning/detection loop. Need to avoid CLI output/logging until end of the
        # main scanning loop below, otherwise it will interrupt the progress bar.
        self._logger.info(
            "Scanning %s for motion events...", "%d input videos" %
            len(self._video_paths) if len(self._video_paths) > 1 else "input video")

        # Don't use the first result from the background subtractor.
        processed_first_frame = False

        progress_bar = self._create_progress_bar(show_progress=self._show_progress)

        decode_queue = queue.Queue(MAX_DECODE_QUEUE_SIZE)
        decode_thread = threading.Thread(
            target=ScanContext._decode_thread, args=(self, decode_queue), daemon=True)
        decode_thread.start()

        encode_thread = None
        if self._output_mode != OutputMode.SCAN_ONLY or self._mask_file is not None:
            encode_queue = queue.Queue(MAX_ENCODE_QUEUE_SIZE)
            encode_thread = threading.Thread(
                target=ScanContext._encode_thread, args=(self, encode_queue), daemon=True)
            encode_thread.start()

        while not self._stop.is_set():
            # Keep polling decode queue until it's empty (signaled via None).
            frame: Optional[DecodeEvent] = decode_queue.get()
            if frame is None:
                break
            assert frame.frame_rgb is not None
            frame_rgb_origin = frame.frame_rgb
            # Cut frame to selected sub-set if ROI area provided.
            if self._roi:
                frame.frame_rgb = frame.frame_rgb[self._roi[1]:self._roi[1] + self._roi[3],
                                                  self._roi[0]:self._roi[0] + self._roi[2]]
            # Apply downscaling factor if provided.
            if self._downscale_factor > 1:
                frame.frame_rgb = frame.frame_rgb[::self._downscale_factor, ::self
                                                  ._downscale_factor, :]
            # Apply motion detector, calculate motion amount/score normalized by frame size.
            motion_mask = motion_detector.apply(frame.frame_rgb)
            frame_score = cv2.sumElems(motion_mask)[0] / float(
                motion_mask.shape[0] * motion_mask.shape[1])
            above_threshold = frame_score >= self._threshold
            # Always assign the first frame a score of 0 since some subtractors will output a mask
            # indicating motion on every pixel of the first frame.
            if not processed_first_frame:
                frame_score = 0.0
                processed_first_frame = True
            event_window.append(frame_score)
            event_window = event_window[-min_event_len:]

            bounding_box = None
            if self._bounding_box:
                bounding_box = (
                    self._bounding_box.update(motion_mask)
                    if above_threshold else self._bounding_box.clear())

            if self._mask_file and not self._stop.is_set():
                encode_queue.put(MaskEvent(motion_mask=motion_mask,))

            # Last frame was part of a motion event, or still within the post-event window.
            if in_motion_event:
                # If this frame still has motion, reset the post-event window.
                if above_threshold:
                    num_frames_post_event = 0
                    last_frame_above_threshold = frame.timecode.frame_num
                # Otherwise, we wait until the post-event window has passed before ending
                # this motion event and start looking for a new one.
                #
                # TODO(#72): We should wait until the max of *both* the pre-event and post-
                # event windows have passed. Right now we just consider the post-event window.
                else:
                    num_frames_post_event += 1
                    if num_frames_post_event >= post_event_len:
                        in_motion_event = False
                        # Calculate event end based on the last frame we had with motion plus the
                        # post event length time. We also need to compensate for the number of
                        # frames that we skipped that could have had motion.
                        event_end = FrameTimecode(
                            last_frame_above_threshold + self._post_event_len.frame_num +
                            self._frame_skip, self._video_fps)
                        # The duration, however, should include the PTS of the end frame.
                        event_duration = FrameTimecode(
                            (event_end.frame_num + 1) - event_start.frame_num, self._video_fps)
                        self.event_list.append((event_start, event_end, event_duration))
                        if self._output_mode in (OutputMode.FFMPEG, OutputMode.COPY):
                            encode_queue.put(
                                FfmpegEvent(start_time=event_start, end_time=event_end))

                # Send frame to encode thread.
                if self._output_mode == OutputMode.OPENCV:
                    encode_queue.put(
                        EncodeEvent(
                            frame_rgb=frame_rgb_origin,
                            timecode=frame.timecode,
                            bounding_box=bounding_box,
                            end_of_event=not in_motion_event,
                        ))
            # Not already in a motion event, look for a new one.
            else:
                # Buffer the required amount of frames and overlay data until we find an event.
                if self._output_mode == OutputMode.OPENCV:
                    buffered_frames.append(
                        EncodeEvent(
                            frame_rgb=frame_rgb_origin,
                            timecode=frame.timecode,
                            bounding_box=bounding_box,
                        ))
                    buffered_frames = buffered_frames[-buff_len:]
                # Start a new event once all frames in the event window have motion.
                if len(event_window) >= min_event_len and all(
                        score >= self._threshold for score in event_window):
                    in_motion_event = True
                    event_window = []
                    num_frames_post_event = 0
                    frames_since_last_event = frame.timecode.frame_num - event_end.frame_num
                    shift_amount = min(frames_since_last_event, start_event_shift)
                    shifted_start = max(start_frame, frame.timecode.frame_num + 1 - shift_amount)
                    event_start = FrameTimecode(shifted_start, self._video_fps)
                    # Send buffered frames to encode thread.
                    if self._output_mode == OutputMode.OPENCV:
                        for encode_frame in buffered_frames:
                            # We have to be careful here. Since we're putting multiple items
                            # into the queue, we have to keep making sure the encode thread
                            # is running. Otherwise, the queue will never empty we will block
                            # indefinitely here waiting for a spot.
                            if self._stop.is_set():
                                break
                            encode_queue.put(encode_frame)
                        buffered_frames = []

            self._frames_processed += 1 + self._frame_skip
            progress_bar.update(1 + self._frame_skip)

        # Video ended, finished processing frames. If we're still in a motion event,
        # compute the duration and ending timecode and add it to the event list.
        if in_motion_event and not self._stop.is_set():
            event_end = FrameTimecode(self._curr_pos.frame_num, self._video_fps)
            event_duration = FrameTimecode(self._curr_pos.frame_num - event_start.frame_num,
                                           self._video_fps)
            self.event_list.append((event_start, event_end, event_duration))
            if self._output_mode in (OutputMode.FFMPEG, OutputMode.COPY):
                encode_queue.put(FfmpegEvent(start_time=event_start, end_time=event_end))
        # Close the progress bar before producing any more output.
        if progress_bar is not None:
            progress_bar.close()
        # Unblock any remaining puts, wait for decode thread to finish, and re-raise any exceptions.
        while not decode_queue.empty():
            _ = decode_queue.get_nowait()

        decode_thread.join()
        if self._decode_thread_exception is not None:
            raise self._decode_thread_exception[1].with_traceback(self._decode_thread_exception[2])
        # Push sentinel to queue, wait for encode thread to finish, and re-raise any exceptions.
        if encode_thread is not None:
            encode_queue.put(None)
            encode_thread.join()
            if self._encode_thread_exception is not None:
                raise self._encode_thread_exception[1].with_traceback(
                    self._encode_thread_exception[2])
        # Allow up to 1 corrupt/failed decoded frame without displaying an error.
        if self._num_corruptions > 1:
            self._logger.error(
                "Failed to decode %d frame(s) from video, result may be incorrect. "
                "Try re-encoding or remuxing video (e.g. ffmpeg -i video.mp4 -c:v copy out.mp4). "
                "See https://github.com/Breakthrough/DVR-Scan/issues/62 for details.",
                self._num_corruptions)

        self._post_scan_motion(processing_start=processing_start)

        return self.event_list

    # TODO(v1.6): Move this into cli.controller and just add a getter for frames_processed.
    def _post_scan_motion(self, processing_start: float):
        processing_time = time.time() - processing_start
        processing_rate = float(self._frames_processed) / processing_time
        self._logger.info("Processed %d frames read in %3.1f secs (avg %3.1f FPS).",
                          self._frames_processed, processing_time, processing_rate)
        if not len(self.event_list) > 0:
            self._logger.info("No motion events detected in input.")
            return

        self._logger.info("Detected %d motion events in input.", len(self.event_list))

        if self.event_list:
            output_strs = [
                "-------------------------------------------------------------",
                "|   Event #    |  Start Time  |   Duration   |   End Time   |",
                "-------------------------------------------------------------"
            ]
            output_strs += [
                "|  Event %4d  |  %s  |  %s  |  %s  |" % (
                    event_num + 1,
                    str(event_start.frame_num),                               #event_start.get_timecode(precision=1),
                    event_duration.get_timecode(precision=1),
                    event_end.get_timecode(precision=1))
                for event_num, (event_start, event_end,
                                event_duration) in enumerate(self.event_list)
            ]
            output_strs += ["-------------------------------------------------------------"]
            self._logger.info("List of motion events:\n%s", '\n'.join(output_strs))

            timecode_list = []
            for event_start, event_end, _ in self.event_list:
                timecode_list.append(event_start.get_timecode())
                timecode_list.append(event_end.get_timecode())
            print("[DVR-Scan] Comma-separated timecode values:\n%s" % (','.join(timecode_list)))

        if self._output_mode != OutputMode.SCAN_ONLY:
            self._logger.info("Motion events written to disk.")

    def _decode_thread(self, decode_queue: queue.Queue):
        try:
            while not self._stop.is_set():
                if self._end_time is not None and self._curr_pos >= self._end_time:
                    break
                if self._frame_skip > 0:
                    for _ in range(self._frame_skip):
                        if self._get_next_frame(False) is None:
                            break
                frame_rgb = self._get_next_frame()
                if frame_rgb is None:
                    break
                # self._curr_pos points to the time at the end of the current frame (i.e. the
                # first frame has a frame_num of 1), so we correct that for presentation time.
                presentation_time = FrameTimecode(
                    timecode=self._curr_pos.frame_num - 1, fps=self._video_fps)
                if not self._stop.is_set():
                    decode_queue.put(DecodeEvent(frame_rgb, presentation_time))

        # We'll re-raise any exceptions from the main thread.
        # pylint: disable=bare-except
        except:
            self._stop.set()
            logger.critical('Fatal error: Exception raised in decode thread.')
            logger.debug(sys.exc_info())
            self._decode_thread_exception = sys.exc_info()
        finally:
            # Make sure main thread stops processing loop.
            decode_queue.put(None)

    def _init_video_writer(self, path: AnyStr, frame_size: Tuple[int, int]) -> cv2.VideoWriter:
        """Create a new cv2.VideoWriter using the correct framerate."""
        if self._output_dir:
            path = os.path.join(self._output_dir, path)
        effective_framerate = (
            self._video_fps if self._frame_skip < 1 else self._video_fps / (1 + self._frame_skip))
        return cv2.VideoWriter(path, self._fourcc, effective_framerate, frame_size)

    def _encode_thread(self, encode_queue: queue.Queue):
        video_writer: Optional[cv2.VideoWriter] = None
        mask_writer: Optional[cv2.VideoWriter] = None
        try:
            num_events = 0
            while True:
                event: Optional[Union[EncodeEvent, MaskEvent]] = encode_queue.get()
                if event is None:
                    break
                if isinstance(event, EncodeEvent):
                    if video_writer is None:
                        num_events += 1
                        output_path = (
                            self._comp_file if self._comp_file else OUTPUT_FILE_TEMPLATE.format(
                                VIDEO_NAME=self._output_prefix,
                                EVENT_NUMBER='%04d' % num_events,
                                EXTENSION='avi',
                            ))
                        resolution = (event.frame_rgb.shape[1], event.frame_rgb.shape[0])
                        video_writer = self._init_video_writer(output_path, resolution)
                    # Render all overlays onto frame.
                    if not self._timecode_overlay is None:
                        self._timecode_overlay.draw(
                            frame=event.frame_rgb, text=event.timecode.get_timecode())
                    if not self._bounding_box is None and not event.bounding_box is None:
                        self._bounding_box.draw(event.frame_rgb, event.bounding_box)
                    # Encode and write frame to disk.
                    video_writer.write(event.frame_rgb)
                    # If we're at the end of the event, make sure we start using a new output
                    # unless we're compiling all motion events together.
                    if event.end_of_event and not self._comp_file:
                        video_writer.release()
                        video_writer = None
                elif isinstance(event, MaskEvent):
                    if mask_writer is None:
                        resolution = event.motion_mask.shape[1], event.motion_mask.shape[0]
                        mask_writer = self._init_video_writer(self._mask_file, resolution)
                    out_frame = cv2.cvtColor(event.motion_mask, cv2.COLOR_GRAY2BGR)
                    mask_writer.write(out_frame)
                elif isinstance(event, FfmpegEvent):
                    assert self._output_mode in (OutputMode.FFMPEG, OutputMode.COPY)
                    num_events += 1
                    output_args = (
                        self._ffmpeg_output_args
                        if self._output_mode == OutputMode.FFMPEG else COPY_OUTPUT_ARGS)
                    output_path = (
                        self._comp_file if self._comp_file else OUTPUT_FILE_TEMPLATE.format(
                            VIDEO_NAME=self._output_prefix,
                            EVENT_NUMBER='%04d' % num_events,
                            EXTENSION='mp4',
                        ))
                    if self._output_dir:
                        output_path = os.path.join(self._output_dir, output_path)
                    # TODO(v1.5): Add config option to allow showing ffmpeg output, and disable
                    # the progress bar when set. Do this automatically in debug mode.

                    # TODO(v1.6): Don't use this wrapper and instead just invoke ffmpeg directly
                    # so that the output can be displayed in the main thread if encoding fails.
                    # We should also stop processing once the video splitting fails.
                    exit_code = split_video_ffmpeg(
                        input_video_path=self._first_input_path,
                        scene_list=[(event.start_time, event.end_time)],
                        output_file_template=output_path,
                        arg_override=output_args,
                        show_output=False,
                        show_progress=False,
                    )
                    if exit_code != 0:
                        self._stop.set()
                        self._logger.debug("Ffmpeg exited with code: %d", exit_code)

        # We'll re-raise any exceptions from the main thread.
        # pylint: disable=bare-except
        except:
            self._stop.set()
            logger.critical('Fatal error: Exception raised in encode thread.')
            logger.debug(sys.exc_info())
            self._encode_thread_exception = sys.exc_info()
        finally:
            if video_writer is not None:
                video_writer.release()
            if mask_writer is not None:
                mask_writer.release()
            # Unblock any waiting puts if we stopped early.
            while not encode_queue.empty():
                _ = encode_queue.get_nowait()
