#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2026 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""Tests for the thumbnail imaging helpers. These cover the pure (Tk-free) functions
only; the background loader and Tk wiring are verified manually in the GUI."""

import numpy as np

from dvr_scan.app.thumbnails import (
    FILMSTRIP_GAP,
    PLACEHOLDER_COLOR,
    THUMBNAIL_HEIGHT,
    filmstrip_image,
    frame_to_image,
    placeholder_image,
)


def test_frame_to_image_scales_to_height_preserving_aspect():
    # 160x90 (w x h) BGR frame; a 54px-tall thumbnail keeps the 16:9 ratio -> 96px wide.
    frame = np.zeros((90, 160, 3), dtype=np.uint8)
    image = frame_to_image(frame, height=54)
    assert image.size == (96, 54)
    assert image.mode == "RGB"


def test_frame_to_image_converts_bgr_to_rgb():
    # Uniform frame with distinct channels: B=10, G=20, R=30 -> RGB pixel (30, 20, 10).
    frame = np.empty((20, 20, 3), dtype=np.uint8)
    frame[:, :, 0] = 10
    frame[:, :, 1] = 20
    frame[:, :, 2] = 30
    image = frame_to_image(frame, height=10)
    assert image.getpixel((0, 0)) == (30, 20, 10)


def test_frame_to_image_default_height():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    image = frame_to_image(frame)
    assert image.height == THUMBNAIL_HEIGHT


def test_frame_to_image_non_default_height():
    # 100x100 (square) frame at a non-default height stays square.
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    image = frame_to_image(frame, height=27)
    assert image.size == (27, 27)


def test_placeholder_image_is_16_by_9():
    image = placeholder_image(height=54)
    assert image.size == (96, 54)
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == PLACEHOLDER_COLOR


def test_placeholder_image_custom_height():
    image = placeholder_image(height=27)
    assert image.height == 27


def test_filmstrip_image_concatenates_frames():
    # Three 100x100 (square) frames at height=10 -> three 10px-wide cells plus 2 gaps.
    frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(3)]
    image = filmstrip_image(frames, height=10)
    expected_width = 3 * 10 + 2 * FILMSTRIP_GAP
    assert image.size == (expected_width, 10)
    assert image.mode == "RGB"


def test_filmstrip_image_empty_falls_back_to_placeholder():
    image = filmstrip_image([], height=54)
    assert image.size == placeholder_image(height=54).size
