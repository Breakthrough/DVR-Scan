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
"""``dvr_scan.subtractor`` Module

Defines an interface to background subtraction (`Subtractor`), and provides several implementations.
All current subtractors use algorithms backed by OpenCV, but this is not a requirement.
"""

from abc import ABC, abstractmethod

import cv2
import numpy


class Subtractor(ABC):
    """Provides a consistent interface for mapping sequences of video frames to masks of pixels
    containing motion on each frame (currently via background subtraction)."""

    @abstractmethod
    def apply(self, frame: numpy.ndarray) -> numpy.ndarray:
        """Apply the background subtractor to the given frame.

        Arguments:
            frame: Frame to perform background subtraction on.

        Returns:
            Mask of areas in the frame containing motion.
        """
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def is_available():
        """True if this detector is available (e.g. has all dependencies), False otherwise."""
        raise NotImplementedError()


class SubtractorMOG2(Subtractor):
    """MOG2 background subtractor."""

    def __init__(
        self,
        kernel_size: int,
        history: int = 500,
        variance_threshold: int = 16,
        detect_shadows: bool = False,
    ):
        if kernel_size < 0 or (kernel_size > 1 and kernel_size % 2 == 0):
            raise ValueError("kernel_size must be >= 0")
        self._kernel = numpy.ones(
            (kernel_size, kernel_size), numpy.uint8) if kernel_size > 1 else None
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=variance_threshold,
            detectShadows=detect_shadows,
        )
        # Default shadow value is 127, set to 0 so they are discarded before filtering.
        self._subtractor.setShadowValue(0)

    def apply(self, frame: numpy.ndarray) -> numpy.ndarray:
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_mask = self._subtractor.apply(frame_gray)
        if not self._kernel is None:
            frame_filt = cv2.morphologyEx(frame_mask, cv2.MORPH_OPEN, self._kernel)
        else:
            frame_filt = frame_mask
        return frame_filt

    @staticmethod
    def is_available():
        return hasattr(cv2, 'createBackgroundSubtractorMOG2')


class SubtractorCNT(SubtractorMOG2):
    """CNT background subtractor."""

    def __init__(
        self,
        kernel_size: int,
        min_pixel_stability: int = 15,
        use_history: bool = True,
        max_pixel_stability: int = 15 * 60,
        is_parallel: bool = True,
    ):
        if kernel_size < 0 or (kernel_size > 1 and kernel_size % 2 == 0):
            raise ValueError("kernel_size must be odd integer >= 1 or zero (0)")
        self._kernel = numpy.ones(
            (kernel_size, kernel_size), numpy.uint8) if kernel_size > 1 else None
        self._subtractor = cv2.bgsegm.createBackgroundSubtractorCNT(
            minPixelStability=min_pixel_stability,
            useHistory=use_history,
            maxPixelStability=max_pixel_stability,
            isParallel=is_parallel,
        )

    @staticmethod
    def is_available():
        return hasattr(cv2, 'bgsegm') and hasattr(cv2.bgsegm, 'createBackgroundSubtractorCNT')


class SubtractorCudaMOG2(SubtractorMOG2):
    """CUDA-accelerated MOG2 background subtractor."""

    def __init__(
        self,
        kernel_size: int,
        history: int = 500,
        variance_threshold: int = 16,
        detect_shadows: bool = False,
    ):
        if kernel_size < 0 or (kernel_size > 1 and kernel_size % 2 == 0):
            raise ValueError("kernel_size must be odd integer >= 1 or zero (0)")
        self._filter = cv2.cuda.createMorphologyFilter(
            cv2.MORPH_OPEN, cv2.CV_8UC1, numpy.ones(
                (kernel_size, kernel_size), numpy.uint8)) if kernel_size > 1 else None
        self._subtractor = cv2.cuda.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=variance_threshold,
            detectShadows=detect_shadows,
        )
        # Default shadow value is 127, set to 0 so they are discarded before filtering.
        self._subtractor.setShadowValue(0)

    def apply(self, frame: numpy.ndarray) -> numpy.ndarray:
        stream = cv2.cuda_Stream()
        frame_rgb_dev = cv2.cuda_GpuMat()
        frame_rgb_dev.upload(frame, stream=stream)
        frame_gray_dev = cv2.cuda.cvtColor(frame_rgb_dev, cv2.COLOR_BGR2GRAY, stream=stream)
        frame_mask_dev = self._subtractor.apply(frame_gray_dev, -1, stream=stream)
        if not self._filter is None:
            frame_filt_dev = self._filter.apply(frame_mask_dev, stream=stream)
        else:
            frame_filt_dev = frame_mask_dev
        frame_filt = frame_filt_dev.download(stream=stream)
        stream.waitForCompletion()
        return frame_filt

    @staticmethod
    def is_available():
        return hasattr(cv2, 'cuda') and hasattr(cv2.cuda, 'createBackgroundSubtractorMOG2')
