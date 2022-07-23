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
""" ``dvr_scan.video_joiner`` Module

Contains a helper class to concatenate multiple videos and treat it as a single,
contiguous video file.
"""

import logging
import os
from typing import AnyStr, List, Optional, Tuple

import cv2
import numpy
from scenedetect import FrameTimecode
from scenedetect.video_stream import VideoOpenFailure

FRAMERATE_DELTA_TOLERANCE: float = 0.1


class VideoJoiner:
    """Handles concatenating multiple videos together.

    Raises:
        VideoOpenFailure: Failed to open a video, or video parameters don't match.
    """

    def __init__(self, paths: List[AnyStr]):
        self._logger = logging.getLogger('dvr_scan')

        assert paths
        self._paths = paths

        self._cap: Optional[cv2.VideoCapture] = None
        self._curr_cap_index = 0
        self._resolution: Tuple[int, int] = None
        self._framerate: float = None
        self._total_frames: int = 0
        self._decode_failures: int = 0
        self._load_input_videos()
        # Initialize position now that the framerate is valid.
        self._position: FrameTimecode = FrameTimecode(0, self.framerate)

    @property
    def paths(self) -> List[AnyStr]:
        """All paths this object was created with."""
        return self._paths

    @property
    def resolution(self) -> Tuple[int, int]:
        """Video resolution (width x height) in pixels."""
        return self._resolution

    @property
    def framerate(self) -> float:
        """Video framerate (frames/sec)."""
        return self._framerate

    @property
    def total_frames(self) -> float:
        """Total number of frames of all input videos combined. May be inaccurate."""
        return self._total_frames

    @property
    def decode_failures(self) -> float:
        """Number of frames which failed to decode (may indicate video corruption)."""
        return self._decode_failures

    @property
    def position(self) -> FrameTimecode:
        """Current position of the video including presentation time of the current frame (thus, the
        first frame has a frame number of 1)."""
        return self._position

    def read(self, decode: bool = True, num_retries: int = 5) -> Optional[numpy.ndarray]:
        """Read/decode the next frame."""
        if self._cap:
            for _ in range(num_retries + 1):
                if decode:
                    (ret_val, frame) = self._cap.read()
                else:
                    ret_val = self._cap.grab()
                    frame = True
                if ret_val:
                    self._position += 1
                    return frame
                if self._total_frames > 0 and self._position.frame_num >= self._total_frames:
                    break
                self._decode_failures += 1
            self._cap.release()
            self._cap = None

        if self._cap is None and (1 + self._curr_cap_index) < len(self._paths):
            self._curr_cap_index += 1
            self._cap = cv2.VideoCapture(self._paths[self._curr_cap_index])
            if self._cap.isOpened():
                return self._get_next_frame()
            else:
                self._logger.error("Error: Unable to load video for processing.")
                raise VideoOpenFailure("Unable to open %s" % self._paths[self._curr_cap_index])
        return None

    def seek(self, target: FrameTimecode):
        """Seek to the target offset. Only seeking forward is supported (i.e. `target` must be
        greater than the current `position`."""
        # TODO: This should be optimized by actually seeking on the underlying VideoCapture objects.
        while self.position < target:
            if self.read(decode=False) is None:
                break

    def _load_input_videos(self):
        for i, video_path in enumerate(self._paths):
            cap = cv2.VideoCapture(video_path)
            video_name = os.path.basename(video_path)
            if not cap.isOpened():
                self._logger.error("Error: Couldn't load video %s.", video_name)
                self._logger.info("Check that the given file is a valid video clip, and ensure all"
                                  " required dependencies are installed and configured properly.")
                raise VideoOpenFailure("isOpened() returned False for %s!" % video_name)
            resolution = (round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                          round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            framerate = cap.get(cv2.CAP_PROP_FPS)
            self._total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # Set the resolution/framerate based on the first video.
            if i == 0:
                self._cap = cap
                self._resolution = resolution
                self._framerate = framerate
                self._logger.info("Opened video %s (%d x %d at %2.3f FPS).", video_name,
                                  resolution[0], resolution[1], framerate)
                continue
            # Otherwise, validate the appended video's parameters.
            self._logger.info("Appending video %s (%d x %d at %2.3f FPS).", video_name,
                              resolution[0], resolution[1], framerate)
            if resolution != self._resolution:
                self._logger.error("Error: Video resolution does not match the first input.")
                raise VideoOpenFailure("Video resolutions must match to be concatenated!")
            if abs(framerate - self._framerate) > FRAMERATE_DELTA_TOLERANCE:
                self._logger.warning("Warning: framerate does not match first input."
                                     " Timecodes may be incorrect.")
