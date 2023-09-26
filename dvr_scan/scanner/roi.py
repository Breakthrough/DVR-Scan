# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Copyright (C) 2014-2023 Brandon Castellano <http://www.bcastell.com>.
# PySceneDetect is licensed under the BSD 2-Clause License; see the
# included LICENSE file, or visit one of the above pages for details.
#

import typing as ty

import numpy as np

Rectangle = ty.Tuple[int, int, int, int]


class RegionsOfInterest:
    """Applies a region of interest to motion masks to limit detection to certain parts of the
    frame, or to downscale via pixel skipping."""

    def __init__(self, frame_size: ty.Tuple[int, int], downscale: int,
                 regions: ty.Optional[ty.Iterable[Rectangle]]):
        self._regions: ty.List[Rectangle] = []
        self._frame_size = frame_size
        self._downscale = downscale
        if len(self._regions) > 1:
            raise NotImplementedError("TODO(v1.6): Implement area for multiple ROIs.")
        self._regions = regions
        # TODO(v1.6): For multiple regions, generate a ndarray representing a mask to apply.

    def area(self) -> int:
        """Total area the current ROI covers *after* compensating for downscale factor."""
        if not self._regions:
            return self._frame_size[0] * self._frame_size[1]
        elif len(self._regions) == 1:
            return self._regions[0][2] * self._regions[0][3]
        raise NotImplementedError("TODO(v1.6): Implement area for multiple ROIs.")

    def crop_and_scale(self, frame: np.ndarray) -> np.ndarray:
        """Crops and downscales `frame` in place."""
        cropped = None
        if not self._regions:
            cropped = frame
        elif len(self._regions) == 1:
            cropped = frame[self._regions[0][1]:self._regions[0][1] + self._regions[0][3],
                            self._regions[0][0]:self._regions[0][0] + self._regions[0][2]]
        else:
            raise NotImplementedError("TODO(v1.6): Find largest bounding box and crop to that.")
        if self._downscale > 1:
            return cropped[::self._downscale, ::self._downscale, :]
        return cropped

    def mask(self, mask: np.ndarray) -> int:
        """Remove motion from areas in `mask` outside of the regions of interest. Returns number of
        pixels remaining inside the mask."""
        if self._regions and len(self._regions) > 1:
            raise NotImplementedError("TODO(v1.6): Mask out pixels in the mask outside of the ROI.")
        return mask.shape[0] * mask.shape[1]
