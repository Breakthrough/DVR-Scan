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
""" ``dvr_scan.overlays`` Module

This module contains various classes used to draw overlays onto video frames.
"""

from enum import Enum
from typing import Tuple

import cv2
import numpy


class TextOverlay(object):
    """Renders text onto video frames, primarily used for drawing timecodes.

    Text is currently anchored to the top left of the frame.
    """

    class Corner(Enum):
        TopLeft = 1
        TopRight = 2

    def __init__(self,
                 font: int = cv2.FONT_HERSHEY_SIMPLEX,
                 font_scale: float = 1.0,
                 margin: int = 4,
                 border: int = 4,
                 thickness: int = 2,
                 color: Tuple[int, int, int] = (255, 255, 255),
                 bg_color: Tuple[int, int, int] = (0, 0, 0),
                 corner: Corner = Corner.TopLeft):
        """Initialize a TextOverlay with the given parameters.

        Arguments:
            font: Any of cv2.FONT_*.
            font_scale: Scale factor passed to OpenCV text rendering functions.
            margin: Amount of margin from edge of frame.
            border: Amount of padding added within background box.
            thickness: Thickness of lines used to draw text.
            color: Foreground color of the text (RGB).
            bg_color: Background color behind the text, or None for no background (RGB).
        """
        self._font = font
        self._font_scale = font_scale
        self._margin = margin
        self._border = border
        self._thickness = thickness
        self._color = color[::-1]
        self._bg_color = bg_color[::-1]
        assert corner in (TextOverlay.Corner.TopLeft, TextOverlay.Corner.TopRight)
        self._corner = corner

    def draw(self, frame: numpy.ndarray, text: str):
        """Render text onto the given frame.

        Arguments:
            frame: Frame to render text onto.
            text: Text to render.
            line_spacing: Spacing defined as a ratio of line height.
        """

        lines = text.splitlines()
        sizes = [
            cv2.getTextSize(text, self._font, self._font_scale, self._thickness) for text in lines
        ]
        line_spacing = max(size[0][1] for size in sizes)
        max_width = max(size[0][0] for size in sizes)
        total_height = sum(size[0][1] for size in sizes) + (line_spacing * (len(sizes) - 1))

        if self._bg_color:
            rect_width = max_width + (2 * self._border)
            rect_height = total_height + (2 * self._border)
            if self._corner == TextOverlay.Corner.TopLeft:
                top_left = (self._margin, self._margin)
                bottom_right = (self._margin + rect_width, self._margin + rect_height)
            elif self._corner == TextOverlay.Corner.TopRight:
                top_left = (max(0, frame.shape[1] - (self._margin + max_width)), self._margin)
                bottom_right = (max(0, frame.shape[1] - self._margin), self._margin + rect_height)
            cv2.rectangle(frame, top_left, bottom_right, self._bg_color, -1)

        if self._corner == TextOverlay.Corner.TopLeft:
            x_offset = self._margin + self._border
        elif self._corner == TextOverlay.Corner.TopRight:
            x_offset = max(0, frame.shape[1] - (self._margin + self._border + max_width))
        y_offset = self._margin + self._border

        for (text, size) in zip(lines, sizes):
            text_pos = (x_offset, y_offset + size[0][1])
            cv2.putText(frame, text, text_pos, self._font, self._font_scale, self._color,
                        self._thickness)
            y_offset += size[0][1] + line_spacing


class BoundingBoxOverlay(object):
    """Calculates and draws a bounding box onto of video frames based on a binary mask
    representing areas of interest/motion."""

    DEFAULT_MIN_SIZE_RATIO: float = 0.032
    """Minimum side length of bounding box relative to largest dimension of the video frame."""

    DEFAULT_THICKNESS_RATIO: float = 0.0032
    """Thickness of bounding box lines relative to largest dimension of the video frame."""

    DEFAULT_COLOUR: Tuple[int, int, int] = (0, 0, 255)
    """Bounding box colour. Tuple of (B, G, R) values in [0, 255]"""

    DEFAULT_SMOOTHING: int = 5
    """Number of frames to use for smoothing/averaging. Values <= 1 indicate no smoothing."""

    def __init__(self,
                 min_size_ratio: float = DEFAULT_MIN_SIZE_RATIO,
                 thickness_ratio: float = DEFAULT_THICKNESS_RATIO,
                 color: Tuple[int, int, int] = DEFAULT_COLOUR,
                 smoothing: int = DEFAULT_SMOOTHING):
        """Initialize a BoundingBoxOverlay with the given parameters.

        Arguments:
            min_size_ratio: Minimum size of resulting bounding box relative to frame size.
            thickness_ratio: Box edge thickness relative to the frame size.
            color: Color to use for drawing edges of the bounding box (RGB).
            smoothing: Amount of temporal smoothing, in frames. Values <= 1 indicate no smoothing.
        """
        self._min_size_ratio = min_size_ratio
        self._thickness_ratio = thickness_ratio
        self._color = color[::-1]

        self._smoothing_amount = max(1, smoothing)
        self._smoothing_window = []

        self._downscale_factor = 1
        self._shift = (0, 0)
        self._frame_skip = 0

    def set_corrections(self, downscale_factor: int, shift: Tuple[int, int], frame_skip: int):
        """Set various correction factors which need to be compensated for when drawing the
        resulting bounding box onto a given target frame.

        Arguments:
            downscale_factor: Integer downscale factor which was applied before calculating
                the motion_mask passed to `update`. The resulting bounding box is upscaled
                by this amount to match the original video frame scale.
            shift: Offset to apply to boxes when drawing on source frame.
            frame_skip: Amount of frames skipped for every processed frame. Used to correct
                the smoothing amount.
        """
        self._downscale_factor = max(1, downscale_factor)
        self._shift = shift
        # We're reducing the number of frames by 1 / (frame_skip + 1)
        self._frame_skip = frame_skip

    def _get_smoothed_window(self) -> Tuple[int, int, int, int]:
        """Average all cached bounding boxes based on the temporal smoothing factor.

        Returns:
            Tuple of ints representing (x, y, width, height) of the smoothed bounding box.
        """
        assert self._smoothing_window
        return [
            round(sum([box[i]
                       for box in self._smoothing_window]) / len(self._smoothing_window))
            for i in range(4)
        ]

    def clear(self):
        """Clear all frames cached within the sliding window."""
        self._smoothing_window = []

    def update(self, motion_mask: numpy.ndarray):
        """Calculate the minimum bounding box given a binary/thresholded mask image, and
        caches it for the next call to `draw`.

        Arguments:
            motion_mask: Greyscale mask where non-zero pixels indicate motion.
        """
        # TODO: We can draw boxes around areas of the frame with motion by doing some kind of
        # contour detection on the motion mask, but that might be computationally expensive. We can
        # instead darken pixels of the frame without motion, and lighten (or adjust the colours) of
        # those pixels that do.
        bounding_box = cv2.boundingRect(motion_mask)
        self._smoothing_window.append(bounding_box)
        # Correct smoothing amount for frame skip.
        smoothing_amount = max(1, self._smoothing_amount // (1 + self._frame_skip))
        # Ensure window size doesn't exceed amount of smoothing required.
        self._smoothing_window = self._smoothing_window[-smoothing_amount:]
        return self._get_smoothed_window()

    def draw(self, frame: numpy.ndarray, bounding_box: Tuple[int, int, int, int], use_shift: bool):
        """Draw a bounding box onto a target frame using the provided ROI and downscale factor."""
        # Correct for downscale factor
        bounding_box = [side_len * self._downscale_factor for side_len in bounding_box]
        top_left = (bounding_box[0], bounding_box[1])
        bottom_right = (bounding_box[0] + bounding_box[2], bounding_box[1] + bounding_box[3])
        max_frame_side = max(frame.shape[0], frame.shape[1])
        thickness = max(2, 2 * (round(self._thickness_ratio * max_frame_side // 2)))
        # If bounding box is too small, pad the bounding box by the specified ratio.
        min_side_len = max(1, round(self._min_size_ratio * max_frame_side))
        correction_x = max(0, min_side_len - bounding_box[2])
        correction_y = max(0, min_side_len - bounding_box[3])
        top_left = (top_left[0] - correction_x // 2, top_left[1] - correction_y // 2)
        bottom_right = (bottom_right[0] + correction_x // 2, bottom_right[1] + correction_y // 2)
        # Shift bounding box if ROI was set
        if self._shift and use_shift:
            top_left = (top_left[0] + self._shift[0], top_left[1] + self._shift[1])
            bottom_right = (bottom_right[0] + self._shift[0], bottom_right[1] + self._shift[1])
        # Ensure coordinates are positive. Values greater than frame size are okay, and should be
        # handled correctly by cv2.rectangle below. Note that we do not currently limit the
        # bounding box to fit within the ROI.
        top_left = (max(0, top_left[0]), max(0, top_left[1]))
        bottom_right = (max(0, bottom_right[0]), max(0, bottom_right[1]))
        # Draw resulting bounding box rectangle ontop of the frame.
        cv2.rectangle(frame, top_left, bottom_right, self._color, thickness=thickness)
