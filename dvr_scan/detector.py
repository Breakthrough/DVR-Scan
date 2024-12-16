#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""``dvr_scan.detector`` Module

Contains the motion detection algorithm (`MotionDetector`) for DVR-Scan.  It calculates a score that
represents the relative amount of movement of consecutive frames in a video.
"""

import logging
import typing as ty
from collections import namedtuple
from dataclasses import dataclass

import cv2
import numpy as np

from dvr_scan.region import Point
from dvr_scan.subtractor import Subtractor

Rectangle = namedtuple("Rectangle", ["x", "y", "w", "h"])

logger = logging.getLogger("dvr_scan")


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

    def __init__(
        self,
        subtractor: Subtractor,
        frame_size: ty.Tuple[int, int],
        downscale: int,
        regions: ty.Optional[ty.Iterable[ty.Iterable[Rectangle]]],
    ):
        self._subtractor = subtractor
        self._frame_size = frame_size
        self._downscale = downscale
        self._regions = list(regions) if regions is not None else []
        self._mask: np.ndarray = np.ones((0, 0))
        self._area: ty.Tuple[Point, Point] = (
            Point(0, 0),
            Point(self._frame_size[0] - 1, self._frame_size[1] - 1),
        )
        if self._regions:
            # TODO: See if this can be done using a single color channel or in a bitmap
            mask = np.zeros((frame_size[1], frame_size[0], 3), dtype=np.uint8)
            for shape in self._regions:
                points = np.array([shape], np.int32)
                mask = cv2.fillPoly(mask, points, color=(255, 255, 255), lineType=cv2.LINE_4)
            mask = mask[:, :, 0].astype(bool)
            active_pixels = mask.sum()
            # False marks unmasked elements (those inside the active region), so we invert the mask.
            mask = np.logical_not(mask)
            # Calculate subset of frame to use to speed up calculations.
            min_x, min_y, max_x, max_y = self._frame_size[0], self._frame_size[1], 0, 0
            for shape in self._regions:
                for point in shape:
                    min_x, min_y = min(min_x, point.x), min(min_y, point.y)
                    max_x, max_y = max(max_x, point.x), max(max_y, point.y)
            self._area = (Point(min_x, min_y), Point(max_x, max_y))
            coverage = 100.0 * (active_pixels / float(frame_size[0] * frame_size[1]))
            mask = mask[self._area[0].y : self._area[1].y, self._area[0].x : self._area[1].x]
            logger.debug(
                "Region Mask: area = ("
                f"{self._area[0].x},{self._area[0].y}),({self._area[1].x},{self._area[1].y}"
                f"), coverage = {coverage:.2f}%"
            )
            if self._downscale > 1:
                mask = mask[:: self._downscale, :: self._downscale]
                logger.debug(f"Mask Downscaled: size = {mask.shape[0]}, {mask.shape[1]}")
            self._mask = mask

    @property
    def area(self) -> Rectangle:
        """Area the region of interest covers in the original frame."""
        return self._area

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        cropped = None
        if not self._regions:
            cropped = frame
        else:
            cropped = frame[
                self._area[0].y : self._area[1].y,
                self._area[0].x : self._area[1].x,
            ]
        if self._downscale > 1:
            return cropped[:: self._downscale, :: self._downscale, :]

        return cropped

    def update(self, frame: np.ndarray) -> ProcessedFrame:
        frame = self._preprocess(frame)
        subtracted = self._subtractor.apply(frame)
        if not self._regions:
            return ProcessedFrame(
                subtracted=subtracted, masked=subtracted, score=np.average(subtracted)
            )
        motion_mask = np.ma.array(subtracted, mask=self._mask)
        return ProcessedFrame(
            subtracted=subtracted,
            masked=motion_mask,
            score=np.ma.sum(motion_mask) / float(np.ma.count(motion_mask)),
        )
