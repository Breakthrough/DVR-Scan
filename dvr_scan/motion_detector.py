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
"""``dvr_scan.motion_detector`` Module"""

from abc import ABC, abstractmethod

import cv2
import numpy


class MotionDetector(ABC):
    """Provides a consistent interface for calculating a mask of areas within each video
    frame containing any motion."""

    @abstractmethod
    def apply(self, frame: numpy.ndarray, update_model: bool = True) -> numpy.ndarray:
        """Apply the background subtractor to the given frame.

        Arguments:
            frame: Frame to perform background subtraction on.
            update_model: If True (default), update the background model.

        Returns:
            Mask of areas in the frame containing motion.
        """
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def is_available():
        """True if this detector is available (e.g. has all dependencies), False otherwise."""
        raise NotImplementedError()


class MotionDetectorMOG2(MotionDetector):
    """MOG2 background subtractor."""

    def __init__(
        self,
        kernel_size: int,
        history: int = 500,
        variance_threshold: int = 16,
        detect_shadows: bool = False,
    ):
        assert kernel_size % 2 == 1 and kernel_size >= 3
        self._kernel = numpy.ones((kernel_size, kernel_size), numpy.uint8)
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=variance_threshold,
            detectShadows=detect_shadows,
        )

    def apply(self, frame: numpy.ndarray, update_model: bool = True) -> numpy.ndarray:
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_mask = self._subtractor.apply(frame_gray)
        frame_filt = cv2.morphologyEx(frame_mask, cv2.MORPH_OPEN, self._kernel)
        return frame_filt

    @staticmethod
    def is_available():
        return hasattr(cv2, 'createBackgroundSubtractorMOG2')


class MotionDetectorCNT(MotionDetectorMOG2):
    """CNT background subtractor."""

    def __init__(
        self,
        kernel_size: int,
        min_pixel_stability: int = 15,
        use_history: bool = True,
        max_pixel_stability: int = 15 * 60,
        is_parallel: bool = True,
    ):
        assert kernel_size % 2 == 1 and kernel_size >= 3
        self._kernel = numpy.ones((kernel_size, kernel_size), numpy.uint8)
        self._subtractor = cv2.bgsegm.createBackgroundSubtractorCNT(
            minPixelStability=min_pixel_stability,
            useHistory=use_history,
            maxPixelStability=max_pixel_stability,
            isParallel=is_parallel,
        )

    @staticmethod
    def is_available():
        return hasattr(cv2, 'bgsegm') and hasattr(cv2.bgsegm, 'createBackgroundSubtractorCNT')


class MotionDetectorCudaMOG2(MotionDetectorMOG2):
    """CUDA-accelerated MOG2 background subtractor."""

    def __init__(
        self,
        kernel_size: int,
        history: int = 500,
        variance_threshold: int = 16,
        detect_shadows: bool = False,
    ):
        assert kernel_size % 2 == 1 and kernel_size >= 3
        self._filter = cv2.cuda.createMorphologyFilter(
            cv2.MORPH_OPEN, cv2.CV_8UC1, numpy.ones((kernel_size, kernel_size), numpy.uint8))
        self._subtractor = cv2.cuda.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=variance_threshold,
            detectShadows=detect_shadows,
        )

    def apply(self, frame: numpy.ndarray, update_model: bool = True) -> numpy.ndarray:
        stream = cv2.cuda_Stream()
        frame_rgb_dev = cv2.cuda_GpuMat()
        frame_rgb_dev.upload(frame, stream=stream)
        frame_gray_dev = cv2.cuda.cvtColor(frame_rgb_dev, cv2.COLOR_BGR2GRAY, stream=stream)
        learning_rate = -1 if update_model else 0
        frame_mask_dev = self._subtractor.apply(frame_gray_dev, learning_rate, stream=stream)
        frame_filt_dev = self._filter.apply(frame_mask_dev, stream=stream)
        frame_filt = frame_filt_dev.download(stream=stream)
        stream.waitForCompletion()
        return frame_filt

    @staticmethod
    def is_available():
        return hasattr(cv2, 'cuda') and hasattr(cv2.cuda, 'createBackgroundSubtractorMOG2')