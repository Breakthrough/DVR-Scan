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
""" ``dvr_scan.detector`` Module

Contains the motion detection algorithm (`MotionDetector`) for DVR-Scan.  It calculates a score that
represents the relative amount of movement of consecutive frames in a video.
"""

from collections import namedtuple
from dataclasses import dataclass
import logging
import typing as ty

import numpy as np

from dvr_scan.subtractor import Subtractor

Rectangle = namedtuple("Rectangle", ['x', 'y', 'w', 'h'])

logger = logging.getLogger('dvr_scan')


@dataclass
class ProcessedFrame:
    """Result of processing a frame through the `MotionDetector`."""

    subtracted: np.ndarray
    """Mask representing areas of cropped input frame that have motion."""
    masked: ty.Union[np.ndarray, np.ma.MaskedArray]
    """The background mask with the specified ROIs applied."""
    score: float
    """Score representing relative amount of motion in this frame inside the specified ROIs."""


class MotionDetector:
    """Detects motion on the input provided by the associated MotionScanner."""

    def __init__(self, subtractor: Subtractor, frame_size: ty.Tuple[int, int], downscale: int,
                 regions: ty.Optional[ty.Iterable[Rectangle]]):
        logging.debug('frame size = %s', str(frame_size))
        self._subtractor = subtractor
        self._frame_size = frame_size
        self._downscale = downscale
        self._regions = list(regions) if not regions is None else []
        self._mask: np.ndarray = np.ones((0, 0))
        self._area: Rectangle = Rectangle(x=0, y=0, w=self._frame_size[0], h=self._frame_size[1])
        logging.debug('%s', str(self._area))
        if len(self._regions) > 1:
            # For multiple ROIs, we calculate a mask array where True denotes ignored (masked)
            # elements, and False represents unmasked elements - those inside the defined ROI.
            min_x, min_y, max_x, max_y = self._frame_size[0], self._frame_size[1], 0, 0
            for region in self._regions:
                min_x, min_y = min(min_x, region.x), min(min_y, region.y)
                max_x, max_y = max(max_x, region.x + region.w), max(max_y, region.y + region.h)
            width, height = max(0, max_x - min_x), max(0, max_y - min_y)
            logger.debug(f"creating mask, covers [{min_x},{min_y}] to [{max_x}, {max_y}]")
            self._mask = np.ones((height, width), dtype=bool)
            for region in self._regions:
                region = Rectangle(x=region.x - min_x, y=region.y, w=region.w, h=region.h)
                self._mask[region.y:region.y + region.h, region.x:region.x + region.w] = False
            if self._downscale > 1:
                self._mask = self._mask[::self._downscale, ::self._downscale]
            self._area = Rectangle(x=min_x, y=min_y, w=width, h=height)
        elif len(self._regions) == 1:
            self._area = self._regions[0]

    @property
    def area(self) -> Rectangle:
        """Area the region of interest covers in the original frame."""
        return self._area

    @property
    def background_mask(self) -> np.ndarray:
        raise NotImplementedError()

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        cropped = None
        if not self._regions:
            cropped = frame
        elif len(self._regions) == 1:
            cropped = frame[self._regions[0].y:self._regions[0].y + self._regions[0].h,
                            self._regions[0].x:self._regions[0].x + self._regions[0].w]
        else:
            cropped = frame[
                self._area.y:self._area.y + self._area.h,
                self._area.x:self._area.x + self._area.w,
            ]
        if self._downscale > 1:
            return cropped[::self._downscale, ::self._downscale, :]

        return cropped

    def update(self, frame: np.ndarray) -> ProcessedFrame:
        frame = self._preprocess(frame)
        subtracted = self._subtractor.apply(frame)

        if len(self._regions) <= 1:
            return ProcessedFrame(
                subtracted=subtracted, masked=subtracted, score=np.average(subtracted))

        motion_mask = np.ma.array(subtracted, mask=self._mask)
        return ProcessedFrame(
            subtracted=subtracted,
            masked=motion_mask,
            score=np.ma.sum(motion_mask) / float(np.ma.count(motion_mask)))
