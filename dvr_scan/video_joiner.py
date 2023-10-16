# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2014-2023 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
""" ``dvr_scan.video_joiner`` Module

Contains a helper class to concatenate multiple videos and treat it as a single,
contiguous video file.
"""

import logging
import os
from typing import AnyStr, List, Optional, Tuple, Union

import cv2
import numpy
from scenedetect import FrameTimecode
from scenedetect.backends import VideoStreamCv2
from scenedetect.video_stream import VideoOpenFailure

FRAMERATE_DELTA_TOLERANCE: float = 0.1

logger = logging.getLogger('dvr_scan')


# TODO: Replace this with the equivalent from PySceneDetect when available.
class VideoJoiner:
    """Handles concatenating multiple videos together.

    Raises:
        VideoOpenFailure: Failed to open a video, or video parameters don't match.
    """

    def __init__(self, paths: Union[AnyStr, List[AnyStr]]):
        if isinstance(paths, (str, bytes)):
            paths = [paths]

        assert paths
        self._paths = paths

        self._cap: Optional[VideoStreamCv2] = None
        self._curr_cap_index = 0
        self._total_frames: int = 0
        self._decode_failures: int = 0
        self._load_input_videos()
        # Initialize position now that the framerate is valid.
        self._position: FrameTimecode = FrameTimecode(0, self.framerate)
        self._last_cap_pos: FrameTimecode = FrameTimecode(0, self.framerate)

    @property
    def paths(self) -> List[AnyStr]:
        """All paths this object was created with."""
        return self._paths

    @property
    def resolution(self) -> Tuple[int, int]:
        """Video resolution (width x height) in pixels."""
        return self._cap.frame_size

    @property
    def framerate(self) -> float:
        """Video framerate (frames/sec)."""
        return self._cap.frame_rate

    @property
    def total_frames(self) -> float:
        """Total number of frames of all input videos combined. May be inaccurate."""
        return self._total_frames

    @property
    def decode_failures(self) -> float:
        """Number of frames which failed to decode (may indicate video corruption)."""
        return self._decode_failures + self._cap._decode_failures

    @property
    def position(self) -> FrameTimecode:
        """Current position of the video including presentation time of the current frame."""
        return self._position + 1

    def read(self, decode: bool = True) -> Optional[numpy.ndarray]:
        """Read/decode the next frame."""
        next = self._cap.read(decode=decode)
        if next is False:
            if (self._curr_cap_index + 1) < len(self._paths):
                self._curr_cap_index += 1
                # Compensate for presentation time of last frame
                self._position += 1
                self._decode_failures += self._cap._decode_failures
                logger.debug("End of current video, loading next: %s" %
                             self._paths[self._curr_cap_index])
                self._cap = VideoStreamCv2(self._paths[self._curr_cap_index])
                self._last_cap_pos = self._cap.base_timecode
                return self.read(decode=decode)
            logger.debug("No more input to process.")
            return None

        self._position += self._cap.position.frame_num - self._last_cap_pos.frame_num
        self._last_cap_pos = self._cap.position
        return next

    def seek(self, target: FrameTimecode):
        """Seek to the target offset. Only seeking forward is supported (i.e. `target` must be
        greater than the current `position`."""
        if len(self._paths) == 1 or self._curr_cap_index == 0 and target <= self._cap.duration:
            self._cap.seek(target)
        else:
            # TODO: This is ineffient if we have multiple input videos.
            while self.position < target:
                if self.read(decode=False) is None:
                    break

    def _load_input_videos(self):
        unsupported_codec: bool = False
        validated_paths: List[str] = []
        opened_video: bool = False
        for video_path in self._paths:
            video_name = os.path.basename(video_path)
            try:
                cap = VideoStreamCv2(video_path)
            except VideoOpenFailure as ex:
                logger.error("Error: Couldn't load video %s", video_path)
                raise
            validated_paths.append(video_path)
            self._total_frames += cap.duration.frame_num
            # Set the resolution/framerate based on the first video.
            if not opened_video:
                self._cap = cap
                logger.info("Opened video %s (%d x %d at %2.3f FPS).", video_name,
                            cap.frame_size[0], cap.frame_size[1], cap.frame_rate)
                opened_video = True
                continue
            # Otherwise, validate the appended video's parameters.
            logger.info("Appending video %s (%d x %d at %2.3f FPS).", video_name, cap.frame_size[0],
                        cap.frame_size[1], cap.frame_rate)
            if cap.frame_size != self._cap.frame_size:
                logger.error("Error: Video resolution does not match the first input.")
                raise VideoOpenFailure("Video resolutions must match to be concatenated!")
            if abs(cap.frame_rate - self._cap.frame_rate) > FRAMERATE_DELTA_TOLERANCE:
                logger.warning("Warning: framerate does not match first input."
                               " Timecodes may be incorrect.")
            if round(cap.capture.get(cv2.CAP_PROP_FOURCC)) == 0:
                unsupported_codec = True

        self._paths = validated_paths

        if unsupported_codec:
            logger.error('Unsupported or invalid codec, output may be incorrect. Possible fixes:\n'
                         '  - Re-encode the input video with ffmpeg\n'
                         '  - Update OpenCV (pip install --upgrade opencv-python)')
