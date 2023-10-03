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

from collections import namedtuple
from logging import getLogger
from copy import deepcopy
import math
import typing as ty

import cv2
import numpy as np

from dvr_scan.detector import Rectangle

WINDOW_NAME = "DVR-Scan: Select ROI"
"""Title given to the ROI selection window."""

MIN_SIZE = 16
"""Minimum height/width for a ROI created using the mouse."""

logger = getLogger('dvr_scan')

Point = namedtuple("Point", ['x', 'y'])
Size = namedtuple("Size", ['w', 'h'])
InputRectangle = ty.Tuple[Point, Point]

MIN_NUM_POINTS = 3
"""Minimum number of points that can be in a polygon."""

MIN_POINT_SPACING = 16
"""Minimum spacing between points in pixels."""

POINT_HANDLE_RADIUS = 8
"""Radius of the point control handle."""

POINT_CONTROL_RADIUS = 16
"""Radius of action for hovering/interacting with a point handle."""

MAX_HISTORY_SIZE = 1024


MAX_UPDATE_RATE_NORMAL = 20
MAX_UPDATE_RATE_DRAGGING = 5


def initial_point_list(frame_size: Size) -> ty.List[Point]:
    # For now start with a rectangle covering 1/4 of the frame in the middle.
    top_left = Point(x=frame_size.w // 4, y=frame_size.h // 4)
    box_size = Size(w=frame_size.w // 2, h=frame_size.h // 2)
    return [
        top_left,
        Point(x=top_left.x + box_size.w, y=top_left.y),
        Point(x=top_left.x + box_size.w, y=top_left.y + box_size.h),
        Point(x=top_left.x, y=top_left.y + box_size.h),
    ]


def squared_distance(a: Point, b: Point):
    return (a.x - b.x)**2 + (a.y - b.y)**2


def bound_point(point: Point, size: Size):
    return Point(min(max(0, point.x), size.w), min(max(0, point.y), size.h))


# TODO(v1.7): Allow multiple polygons by adding new ones using keyboard.
# TODO(v1.7): Allow shifting polygons by using middle mouse button.
class SelectionWindow:

    def __init__(self, frame: np.ndarray, initial_scale: ty.Optional[int]):
        self._source_frame = frame.copy()   # Frame before downscaling
        self._source_size = Size(w=frame.shape[1], h=frame.shape[0])
        self._scale: int = 1 if initial_scale is None else initial_scale
        self._frame = frame.copy()          # Workspace
        self._frame_size = Size(w=frame.shape[1], h=frame.shape[0])
        self._original_frame = frame.copy() # Copy to redraw on
        self._point_list = initial_point_list(self._frame_size)
        self._history = []
        self._history_pos = 0
        self._commit()
        self._curr_mouse_pos = None
        self._redraw = True
        self._recalculate = True
        self._hover_point = None
        self._nearest_points = None
        self._dragging = False
        self._drag_start = None
        self._use_aa = True

        self._line_color = (255, 0, 0)
        self._hover_color = (0, 127, 255)
        self._hover_color_alt = (0, 0, 255)
        self._interact_color = (0, 255, 255)

        # TODO: press 's' to "save" the current ROI by printing it to terminal (or saving to file?)

        self._segment_distances = [] # Squared distance of segment from point i to i+1
        self._mouse_distances = []   # Squared distance of mouse to point i

        if self._scale > 1:
            self._rescale()

    def _rescale(self):
        self._original_frame = self._source_frame[::self._scale, ::self._scale, :].copy()
        self._frame = self._original_frame.copy()
        self._frame_size = Size(w=self._frame.shape[1], h=self._frame.shape[0])
        self._redraw = True
        logger.debug("Resizing window: scale = 1/%d%s, resolution = %d x %d", self._scale,
                     ' (off)' if self._scale == 1 else '', self._frame_size.w, self._frame_size.h)

    def _undo(self):
        if self._history_pos < (len(self._history) - 1):
            self._history_pos += 1
            self._point_list = deepcopy(self._history[self._history_pos])
            self._recalculate = True
            self._redraw = True
            logger.debug("Undo Applied[%d/%d]", self._history_pos, len(self._history))

    def _redo(self):
        if self._history_pos > 0:
            self._history_pos -= 1
            self._point_list = deepcopy(self._history[self._history_pos])
            self._recalculate = True
            self._redraw = True
            logger.debug("Redo Applied [%d/%d]", self._history_pos, len(self._history))

    def _commit(self):
        self._history = self._history[self._history_pos:]
        self._history.insert(0, deepcopy(self._point_list))
        self._history = self._history[:MAX_HISTORY_SIZE]
        self._history_pos = 0
        self._recalculate = True
        self._redraw = True
        logger.debug("Commit: size = %d, data = [%s]", len(self._history),
                     ', '.join(f'P({x},{y})' for x, y in [point for point in self._point_list]))
        
    def _emit_points(self):
        logger.info("ROI:\n--roi %s", " ".join("%d %d" % (point.x, point.y) for point in self._point_list))

    def _draw(self):
        # TODO: Can cache a lot of the calculations below. Need to keep drawing as fast as possible.
        if self._recalculate:
            self._recalculate_data()
        if not self._redraw:
            return
        line_type = cv2.LINE_AA if self._use_aa else cv2.LINE_4
        self._frame = self._original_frame.copy()
        points = np.array([self._point_list], np.int32)
        if self._scale > 1:
            points = points // self._scale
        self._frame = cv2.polylines(
            self._frame,
            points,
            isClosed=True,
            color=self._line_color,
            thickness=2,
            lineType=line_type)
        if not self._hover_point is None:
            first, mid, last = ((self._hover_point - 1) % len(self._point_list), self._hover_point,
                                (self._hover_point + 1) % len(self._point_list))
            points = np.array(
                [[self._point_list[first], self._point_list[mid], self._point_list[last]]],
                np.int32)
            if self._scale > 1:
                points = points // self._scale
            self._frame = cv2.polylines(
                self._frame,
                points,
                isClosed=False,
                color=self._hover_color if not self._dragging else self._hover_color_alt,
                thickness=3,
                lineType=line_type)
        elif not self._nearest_points is None:
            points = np.array([[
                self._point_list[self._nearest_points[0]], self._point_list[self._nearest_points[1]]
            ]], np.int32)
            if self._scale > 1:
                points = points // self._scale
            self._frame = cv2.polylines(
                self._frame,
                points,
                isClosed=False,
                color=self._hover_color,
                thickness=3,
                lineType=line_type)

        for i, point in enumerate(self._point_list):
            color = self._line_color

            if not self._hover_point is None:
                if self._hover_point == i:
                    color = self._hover_color_alt if not self._dragging else self._interact_color
            elif not self._nearest_points is None and i in self._nearest_points:
                color = self._hover_color if self._dragging else self._interact_color
            start, end = (
                Point((point.x // self._scale) - POINT_HANDLE_RADIUS,
                      (point.y // self._scale) - POINT_HANDLE_RADIUS),
                Point((point.x // self._scale) + POINT_HANDLE_RADIUS,
                      (point.y // self._scale) + POINT_HANDLE_RADIUS),
            )
            cv2.rectangle(
                self._frame,
                start,
                end,
                color,
                thickness=cv2.FILLED,
            )
        cv2.imshow(WINDOW_NAME, self._frame)
        self._redraw = False

    def _find_nearest(self) -> ty.Tuple[int, int]:
        nearest_seg, nearest_dist, largest_cosine = 0, 2**31, math.pi
        for i in range(len(self._point_list)):
            # Create a triangle where side a's length is the mouse to closest point on the line,
            # side c is the length to the furthest point, and side b is the line segment length.
            next = (i + 1) % len(self._point_list)
            a_sq = min(self._mouse_distances[i], self._mouse_distances[next])
            c_sq = max(self._mouse_distances[i], self._mouse_distances[next])
            b_sq = self._segment_distances[i]
            # Calculate "angle" C (angle between line segment and closest line to mouse)
            a = math.sqrt(a_sq)
            b = math.sqrt(b_sq)
            cos_C = ((a_sq + b_sq) - c_sq) / (2.0 * a * b)
            # If cos_C is between [0,1] the triangle is acute. If it's not, just take the distance
            # of the closest point.
            dist = int(a_sq - (int(a * cos_C)**2)) if cos_C > 0 else a_sq
            if dist < nearest_dist or (dist == nearest_dist and cos_C > largest_cosine):
                nearest_seg, nearest_dist, largest_cosine = i, dist, cos_C
        return (nearest_seg, (nearest_seg + 1) % len(self._point_list))

    def _hovering_over(self) -> ty.Optional[int]:

        min_i = 0
        for i in range(1, len(self._mouse_distances)):
            if self._mouse_distances[i] < self._mouse_distances[min_i]:
                min_i = i
        # If we've shrunk the image, we need to compensate for the size difference in the image.
        # The control handles remain the same size but the image is smaller
        return min_i if self._mouse_distances[min_i] <= (POINT_CONTROL_RADIUS * self._scale)**2 else None

    def run(self):
        logger.debug('Creating window for frame (scale = %d)', self._scale)
        cv2.imshow(WINDOW_NAME, self._frame)
        cv2.setMouseCallback(WINDOW_NAME, self._handle_mouse_input)
        while True:
            self._draw()
            key = cv2.waitKey(
                MAX_UPDATE_RATE_NORMAL if not self._dragging else MAX_UPDATE_RATE_DRAGGING) & 0xFF
            if key in (ord(' '), 27):
                break
            elif key == ord('b'):
                breakpoint()
                self._find_nearest()
            elif key == ord('a'):
                self._use_aa = not self._use_aa
                self._redraw = True
                logger.debug("Antialiasing: %s", 'ON' if self._use_aa else 'OFF')
            elif key == ord('w'):
                self._scale += 1
                self._rescale()
            elif key == ord('s'):
                self._scale = max(1, self._scale - 1)
                self._rescale()
            elif key == ord('z'):
                self._undo()
            elif key == ord('y'):
                self._redo()
            elif key == ord('c'):
                self._emit_points()

    def _recalculate_data(self):
        # TODO: Optimize further, only need to do a lot of work below if certain things changed
        # from the last calculation point.
        if self._curr_mouse_pos is None:
            return
        last_hover = self._hover_point
        last_nearest = self._nearest_points
        # Calculate distance from mouse cursor to each point.
        self._mouse_distances = [
            squared_distance(self._curr_mouse_pos, point) for point in self._point_list
        ]
        # Check if we're hovering over a point.
        self._hover_point = self._hovering_over()
        # Optimization: Only recalculate segment distances if we aren't hovering over a point.
        if self._hover_point is None:
            num_points = len(self._point_list)
            self._segment_distances = [
                squared_distance(self._point_list[i], self._point_list[(i + 1) % num_points])
                for i in range(num_points)
            ]
            self._nearest_points = self._find_nearest()
        if last_hover != self._hover_point or last_nearest != self._nearest_points:
            self._redraw = True
        self._recalculate = False

    def _handle_mouse_input(self, event, x, y, flags, param):
        # TODO: Handle case where mouse leaves frame (stop highlighting).
        self._curr_mouse_pos = bound_point(point=Point(x, y), size=self._frame_size)
        self._curr_mouse_pos = Point(self._curr_mouse_pos.x * self._scale,
                                     self._curr_mouse_pos.y * self._scale)
        drag_started = False
        # scale coordinates

        if event == cv2.EVENT_LBUTTONDOWN:
            if not self._hover_point is None:
                self._dragging = True
                drag_started = True
                self._drag_start = self._curr_mouse_pos
                self._redraw = True
            elif not self._nearest_points is None:
                insert_pos = (1 + self._nearest_points[0] if self._nearest_points[0]
                              < self._nearest_points[1] else self._nearest_points[1])
                insert_pos = insert_pos % len(self._point_list)
                self._point_list.insert(insert_pos, self._curr_mouse_pos)
                self._nearest_points = None
                self._hover_point = insert_pos
                self._dragging = True # Wait for dragging to stop to commit to history.
                drag_started = True
                self._drag_start = self._curr_mouse_pos
                self._redraw = True

        elif event == cv2.EVENT_MOUSEMOVE:
            if self._dragging:
                self._point_list[self._hover_point] = self._curr_mouse_pos
                self._redraw = True
            else:
                self._recalculate = True

        elif event == cv2.EVENT_LBUTTONUP:
            if self._dragging:
                assert not self._hover_point is None
                if (len(self._point_list) != len(self._history[self._history_pos])
                        or self._curr_mouse_pos != self._drag_start):
                    self._point_list[self._hover_point] = self._curr_mouse_pos
                    self._commit()
                self._redraw = True
            self._dragging = False

        elif event == cv2.EVENT_RBUTTONDOWN:
            if not self._hover_point is None:
                if len(self._point_list) > MIN_NUM_POINTS:
                    del self._point_list[self._hover_point]
                    self._hover_point = None
                    self._commit()
                else:
                    logger.error("Cannot remove point, shape must have at least 3 points.")
                self._dragging = False

        if not self._dragging or drag_started:
            self._draw()
