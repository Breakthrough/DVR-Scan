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
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from logging import getLogger
import math
import os
import typing as ty

import cv2
import numpy as np

from dvr_scan.platform import HAS_TKINTER, IS_WINDOWS, temp_tk_window, set_icon

if HAS_TKINTER:
    import tkinter
    import tkinter.filedialog

WINDOW_NAME = "DVR-Scan: Select ROI"
"""Title given to the ROI selection window."""

# TODO(v1.6): Figure out how to properly get icon path in the package.
ICON_PATH = "dist/dvr-scan.ico"

DEFAULT_WINDOW_MODE = (cv2.WINDOW_AUTOSIZE if IS_WINDOWS else cv2.WINDOW_KEEPRATIO)
"""Minimum height/width for a ROI created using the mouse."""

MIN_SIZE = 16
"""Minimum height/width for a ROI created using the mouse."""

logger = getLogger('dvr_scan')
Point = namedtuple("Point", ['x', 'y'])
Size = namedtuple("Size", ['w', 'h'])
InputRectangle = ty.Tuple[Point, Point]


def check_tkinter_support():
    # TODO(v1.6): Only show the warning if the user hasn't specified a file to save the ROI to.
    if not HAS_TKINTER:
        logger.warning(
            "Warning: Tkinter is not installed. To save the region to disk, use "
            "-s/--save-region [FILE], or install python3-tk (e.g. `sudo apt install python3-tk`).")


class RegionValue:
    """Validator for a set of points representing a closed polygon."""

    _IGNORE_CHARS = [',', '/', '(', ')', '[', ']']
    """Characters to ignore."""

    def __init__(self, value: str):
        translation_table = str.maketrans({char: ' ' for char in RegionValue._IGNORE_CHARS})
        values = value.translate(translation_table).split()
        if not all([val.isdigit() for val in values]):
            raise ValueError("Regions can only contain numbers and the following characters:"
                             f" , / ( )\n  Input: {value}")
        if not len(values) % 2 == 0:
            raise ValueError(f"Could not parse region, missing X or Y component.\n  Input: {value}")
        if not len(values) >= 6:
            raise ValueError(f"Regions must have at least 3 points.\n  Input: {value}")

        self._value = [Point(int(x), int(y)) for x, y in zip(values[0::2], values[1::2])]

    @property
    def value(self) -> ty.List[Point]:
        return self._value

    def __repr__(self) -> str:
        return repr(self.value)

    def __str__(self) -> str:
        return ", ".join(f'P({x},{y})' for x, y in self._value)


# TODO(v1.6): Allow controlling some of these settings in the config file.
@dataclass
class SelectionWindowSettings:
    use_aa: bool = True
    mask_source: bool = False
    window_mode: int = DEFAULT_WINDOW_MODE
    line_color: ty.Tuple[int, int, int] = (255, 0, 0)
    line_color_alt: ty.Tuple[int, int, int] = (255, 153, 51)
    hover_color: ty.Tuple[int, int, int] = (0, 127, 255)
    hover_color_alt: ty.Tuple[int, int, int] = (0, 0, 255)
    interact_color: ty.Tuple[int, int, int] = (0, 255, 255)
    highlight_insert: bool = False


# TODO(v1.6): Move more of these to SelectionWindowSettings.
MIN_NUM_POINTS = 3
MAX_HISTORY_SIZE = 1024
MAX_DOWNSCALE_FACTOR = 100
MAX_UPDATE_RATE_NORMAL = 20
MAX_UPDATE_RATE_DRAGGING = 5
HOVER_DISPLAY_DISTANCE = 200000
MAX_DOWNSCALE_AA_LEVEL = 4

KEYBIND_POINT_DELETE = 'x'
KEYBIND_POINT_ADD = 'q'
KEYBIND_UNDO = 'z'
KEYBIND_REDO = 'y'
KEYBIND_MASK = 'm'
KEYBIND_TOGGLE_AA = 'a'
KEYBIND_WINDOW_MODE = 'r'
KEYBIND_DOWNSCALE_INC = 'w'
KEYBIND_DOWNSCALE_DEC = 'e'
KEYBIND_OUTPUT_LIST = 'c'
KEYBIND_HELP = 'h'
KEYBIND_BREAKPOINT = 'b'
KEYBIND_LOAD = 'l'
KEYBIND_SAVE = 's'


def control_handle_radius(scale: int):
    """Get size of point control handles based on scale factor."""
    # TODO: This should be based on the video resolution as well, not just scale factor.
    if scale == 1:
        return 12
    elif scale == 2:
        return 7
    elif scale == 3:
        return 5
    elif scale <= 10:
        return 4
    elif scale <= 20:
        return 3
    elif scale <= 64:
        return 2
    return 1


def edge_thickness(scale: int, ext: int = 0):
    """Get thickness of polygon connecting edges based on scale factor."""
    # TODO: This should be based on the video resolution as well, not just scale factor.
    if scale < 2:
        return 4 + ext
    elif scale < 5:
        return 3 + ext
    elif scale <= 10:
        return 2 + ext
    return 1 + ext if scale <= 20 else 0


def show_controls():
    """Display keyboard/mouse controls."""
    # Right click is disabled on Linux/OSX due to a context manager provided by the UI framework
    # showing up when right clicking.
    _WINDOWS_ONLY = 'Right, ' if IS_WINDOWS else ''
    logger.info(f"""ROI Window Controls:

Add Point           Key: {KEYBIND_POINT_ADD}    Mouse: Left
Delete Point        Key: {KEYBIND_POINT_DELETE}    Mouse: {_WINDOWS_ONLY}Middle
Print Points        Key: {KEYBIND_OUTPUT_LIST}

Start Scan          Key: Space, Enter
Quit                Key: Escape
Save                Key: {KEYBIND_SAVE}
Load                Key: {KEYBIND_LOAD}
Undo                Key: {KEYBIND_UNDO}
Redo                Key: {KEYBIND_REDO}

Toggle Mask         Key: {KEYBIND_MASK}
Downscale Set       Key: 1 - 9
Downscale +/-       Key: {KEYBIND_DOWNSCALE_INC}(+), {KEYBIND_DOWNSCALE_DEC} (-)
Antialiasing        Key: {KEYBIND_TOGGLE_AA}
Window Mode         Key: {KEYBIND_WINDOW_MODE}
""")


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

    def __init__(self, frame: np.ndarray, initial_scale: ty.Optional[int], debug_mode: bool):
        self._source_frame = frame.copy()   # Frame before downscaling
        self._source_size = Size(w=frame.shape[1], h=frame.shape[0])
        self._scale: int = 1 if initial_scale is None else initial_scale
        self._frame = frame.copy()          # Workspace
        self._frame_size = Size(w=frame.shape[1], h=frame.shape[0])
        self._original_frame = frame.copy() # Copy to redraw on
        self._shapes = [initial_point_list(self._frame_size)]
        self._history = []
        self._history_pos = 0
        self._curr_mouse_pos = None
        self._redraw = True
        self._recalculate = True
        self._hover_point = None
        self._nearest_points = None
        self._dragging = False
        self._drag_start = None
        self._debug_mode = debug_mode
        self._segment_dist = []             # Square distance of segment from point i to i+1
        self._mouse_dist = []               # Square distance of mouse to point i
        if self._scale > 1:
            self._rescale()
        self._settings = SelectionWindowSettings()
        self._commit()

    @property
    def shapes(self) -> ty.Iterable[ty.Iterable[Point]]:
        return self._shapes

    def _rescale(self):
        assert self._scale > 0
        self._original_frame = self._source_frame[::self._scale, ::self._scale, :].copy()
        self._frame = self._original_frame.copy()
        self._frame_size = Size(w=self._frame.shape[1], h=self._frame.shape[0])
        self._redraw = True
        logger.debug("Resize: scale = 1/%d%s, res = %d x %d", self._scale,
                     ' (off)' if self._scale == 1 else '', self._frame_size.w, self._frame_size.h)

    def _undo(self):
        if self._history_pos < (len(self._history) - 1):
            self._history_pos += 1
            self._shapes = deepcopy(self._history[self._history_pos])
            self._recalculate = True
            self._redraw = True
            logger.debug("Undo: [%d/%d]", self._history_pos, len(self._history))

    def _redo(self):
        if self._history_pos > 0:
            self._history_pos -= 1
            self._shapes = deepcopy(self._history[self._history_pos])
            self._recalculate = True
            self._redraw = True
            logger.debug("Redo: [%d/%d]", self._history_pos, len(self._history))

    def _commit(self):
        self._history = self._history[self._history_pos:]
        self._history.insert(0, deepcopy(self._shapes))
        self._history = self._history[:MAX_HISTORY_SIZE]
        self._history_pos = 0
        self._recalculate = True
        self._redraw = True

    def _emit_points(self):
        region_info = []
        for shape in self._shapes:
            region_info.append("--region %s" % " ".join(f"{x} {y}" for x, y in shape))
        logger.info("Region data for CLI:\n%s", " ".join(region_info))

    def _draw(self):
        if self._recalculate:
            self._recalculate_data()
        if not self._redraw:
            return

        frame = self._original_frame.copy()
        for shape in self._shapes:
            points = np.array([shape], np.int32)
            thickness = edge_thickness(self._scale)
            thickness_active = edge_thickness(self._scale, 1)
            if self._scale > 1:
                points = points // self._scale

            if self._settings.mask_source:
                mask = cv2.fillPoly(
                    np.zeros_like(frame, dtype=np.uint8),
                    points,
                    color=(255, 255, 255),
                    lineType=cv2.LINE_4)
                frame = np.bitwise_and(frame, mask).astype(np.uint8)

            line_type = cv2.LINE_AA if self._settings.use_aa and self._scale <= MAX_DOWNSCALE_AA_LEVEL else cv2.LINE_4
            frame = cv2.polylines(
                frame,
                points,
                isClosed=True,
                color=self._settings.line_color,
                thickness=thickness,
                lineType=line_type)
        if not self._hover_point is None:
            first, mid, last = ((self._hover_point - 1) % len(self._shapes[0]), self._hover_point,
                                (self._hover_point + 1) % len(self._shapes[0]))
            points = np.array(
                [[self._shapes[0][first], self._shapes[0][mid], self._shapes[0][last]]], np.int32)
            if self._scale > 1:
                points = points // self._scale
            frame = cv2.polylines(
                frame,
                points,
                isClosed=False,
                color=self._settings.hover_color
                if not self._dragging else self._settings.hover_color_alt,
                thickness=thickness_active,
                lineType=line_type)
        elif not self._nearest_points is None and self._settings.highlight_insert:

            points = np.array([[
                self._shapes[0][self._nearest_points[0]], self._shapes[0][self._nearest_points[1]]
            ]], np.int32)
            if self._scale > 1:
                points = points // self._scale
            frame = cv2.polylines(
                frame,
                points,
                isClosed=False,
                color=self._settings.hover_color,
                thickness=thickness_active,
                lineType=line_type)

        radius = control_handle_radius(self._scale)
        for i, point in enumerate(self._shapes[0]):
            color = self._settings.line_color_alt
            if not self._hover_point is None:
                if self._hover_point == i:
                    color = self._settings.hover_color_alt if not self._dragging else self._settings.interact_color
            elif not self._nearest_points is None and i in self._nearest_points:
                color = self._settings.hover_color if self._dragging else self._settings.interact_color
            start, end = (
                Point((point.x // self._scale) - radius, (point.y // self._scale) - radius),
                Point((point.x // self._scale) + radius, (point.y // self._scale) + radius),
            )
            cv2.rectangle(
                frame,
                start,
                end,
                color,
                thickness=cv2.FILLED,
            )
        self._frame = frame
        cv2.imshow(WINDOW_NAME, self._frame)
        self._redraw = False

    def _find_nearest(self) -> ty.Tuple[int, int]:
        nearest_seg, nearest_dist, largest_cosine = 0, 2**31, math.pi
        for i in range(len(self._shapes[0])):
            # Create a triangle where side a's length is the mouse to closest point on the line,
            # side c is the length to the furthest point, and side b is the line segment length.
            next = (i + 1) % len(self._shapes[0])
            a_sq = min(self._mouse_dist[i], self._mouse_dist[next])
            c_sq = max(self._mouse_dist[i], self._mouse_dist[next])
            b_sq = self._segment_dist[i]
            # Calculate "angle" C (angle between line segment and closest line to mouse)
            a = math.sqrt(a_sq)
            b = math.sqrt(b_sq)
            cos_C = ((a_sq + b_sq) - c_sq) / (2.0 * a * b)
            # If cos_C is between [0,1] the triangle is acute. If it's not, just take the distance
            # of the closest point.
            dist = int(a_sq - (int(a * cos_C)**2)) if cos_C > 0 else a_sq
            if dist < nearest_dist or (dist == nearest_dist and cos_C > largest_cosine):
                nearest_seg, nearest_dist, largest_cosine = i, dist, cos_C
        last = self._settings.highlight_insert
        self._settings.highlight_insert = nearest_dist <= HOVER_DISPLAY_DISTANCE
        if last != self._settings.highlight_insert:
            self._redraw = True
        self._nearest_points = (nearest_seg, (nearest_seg + 1) % len(self._shapes[0]))

    def _hovering_over(self) -> ty.Optional[int]:
        min_i = 0
        for i in range(1, len(self._mouse_dist)):
            if self._mouse_dist[i] < self._mouse_dist[min_i]:
                min_i = i
        # If we've shrunk the image, we need to compensate for the size difference in the image.
        # The control handles remain the same size but the image is smaller
        return min_i if self._mouse_dist[min_i] <= (4 * control_handle_radius(self._scale) *
                                                    self._scale)**2 else None

    def _init_window(self):
        cv2.namedWindow(WINDOW_NAME, self._settings.window_mode)
        if self._settings.window_mode == cv2.WINDOW_AUTOSIZE:
            cv2.resizeWindow(WINDOW_NAME, width=self._frame_size.w, height=self._frame_size.h)
        cv2.imshow(WINDOW_NAME, mat=self._frame)
        cv2.setMouseCallback(WINDOW_NAME, on_mouse=self._handle_mouse_input)

    # TODO(v1.6): Need to return status if ROI selection succeeded or user hit escape/closed window.
    def run(self) -> bool:
        logger.debug("Creating window for frame (scale = %d)", self._scale)
        self._init_window()
        check_tkinter_support()
        set_icon(WINDOW_NAME, ICON_PATH)
        while True:
            if not cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE):
                logger.debug("Main window closed.")
                break
            self._draw()
            key = cv2.waitKey(
                MAX_UPDATE_RATE_NORMAL if not self._dragging else MAX_UPDATE_RATE_DRAGGING) & 0xFF
            # TODO: Map keybinds to callbacks rather than handle each case explicitly.
            if key == 27:
                break
            elif key in (ord(' '), 13):
                return True
            elif key == ord(KEYBIND_BREAKPOINT) and self._debug_mode:
                breakpoint()
            elif key == ord(KEYBIND_TOGGLE_AA):
                self._settings.use_aa = not self._settings.use_aa
                self._redraw = True
                logger.debug("AA: %s", "ON" if self._settings.use_aa else "OFF")
                if self._scale >= MAX_DOWNSCALE_AA_LEVEL:
                    logger.warning("AA is disabled due to current scale factor.")
            elif key == ord(KEYBIND_DOWNSCALE_INC):
                if self._scale < MAX_DOWNSCALE_FACTOR:
                    self._scale += 1
                    self._rescale()
            elif key == ord(KEYBIND_DOWNSCALE_DEC):
                if self._scale > 1:
                    self._scale = max(1, self._scale - 1)
                    self._rescale()
            elif key == ord(KEYBIND_UNDO):
                self._undo()
            elif key == ord(KEYBIND_REDO):
                self._redo()
            elif key == ord(KEYBIND_OUTPUT_LIST):
                self._emit_points()
            elif key == ord(KEYBIND_MASK):
                self._toggle_mask()
            elif key == ord(KEYBIND_WINDOW_MODE):
                cv2.destroyWindow(WINDOW_NAME)
                if self._settings.window_mode == cv2.WINDOW_KEEPRATIO:
                    self._settings.window_mode = cv2.WINDOW_AUTOSIZE
                else:
                    self._settings.window_mode = cv2.WINDOW_KEEPRATIO
                logger.debug(
                    "Window Mode: %s", "KEEPRATIO"
                    if self._settings.window_mode == cv2.WINDOW_KEEPRATIO else "AUTOSIZE")
                self._init_window()
            elif key == ord(KEYBIND_POINT_DELETE):
                self._delete_point()
            elif key == ord(KEYBIND_POINT_ADD):
                self._add_point()
            elif key == ord(KEYBIND_HELP):
                show_controls()
            elif key == ord('l'):
                self._load()
            elif key == ord('s'):
                self._save()
            elif key >= ord('1') and key <= ord('9'):
                scale = 1 + key - ord('1')
                if scale != self._scale:
                    self._scale = scale
                    self._rescale()
        return False

    def _save(self):
        if not HAS_TKINTER:
            logger.debug("Cannot show file dialog.")
            return
        save_path = None
        with temp_tk_window(ICON_PATH) as _:
            save_path = tkinter.filedialog.asksaveasfilename(
                title="DVR-Scan: Save Region",
                filetypes=[("Region File", "*.txt")],
                defaultextension=".txt",
                confirmoverwrite=True,
            )
        if save_path:
            with open(save_path, "wt") as region_file:
                regions = " ".join(f"{x} {y}" for x, y in self._shapes[0])
                region_file.write(f"{regions}\n")
            logger.info('Saved region to: %s', save_path)

    def _load(self):
        if not HAS_TKINTER:
            logger.debug("Cannot show file dialog.")
            return
        load_path = None
        with temp_tk_window(ICON_PATH) as _:
            load_path = tkinter.filedialog.askopenfilename(
                title="DVR-Scan: Load Region",
                filetypes=[("Region File", "*.txt")],
                defaultextension=".txt",
            )
        if not load_path:
            return
        if not os.path.exists(load_path):
            logger.error(f"File does not exist: {load_path}")
            return
        region_data = None
        with open(load_path, 'rt') as region_file:
            region_data = region_file.readlines()
        regions = None
        if region_data:
            try:
                regions = list(
                    RegionValue(region)
                    for region in filter(None, (region.strip() for region in region_data)))
            except ValueError as ex:
                reason = " ".join(str(arg) for arg in ex.args)
                if not reason:
                    reason = "Could not parse region file!"
                logger.error(f"Error loading region from {load_path}: {reason}")
        if regions:
            logger.debug("Loaded %d polygon%s from region file:\n%s", len(region_data),
                         's' if len(region_data) > 1 else '',
                         "\n".join(f"[{i}] = {points}" for i, points in enumerate(regions)))
            if len(regions) > 1:
                logger.error("Error: GUI does not support multiple regions.")
                return
            self._shapes[0] = [bound_point(point, self._source_size) for point in regions[0].value]
            self._commit()

    def _delete_point(self):
        if not self._hover_point is None:
            if len(self._shapes[0]) > MIN_NUM_POINTS:
                hover = self._hover_point
                x, y = self._shapes[0][hover]
                del self._shapes[0][hover]
                self._hover_point = None
                logger.debug("Del: [%d] = %s", hover, f'P({x},{y})')
                self._commit()
            else:
                logger.error("Cannot remove point, shape must have at least 3 points.")
            self._dragging = False

    def _toggle_mask(self):
        self._settings.mask_source = not self._settings.mask_source
        logger.debug("Masking: %s", "ON" if self._settings.mask_source else "OFF")
        self._redraw = True

    def _add_point(self) -> bool:
        if not self._nearest_points is None:
            insert_pos = (1 + self._nearest_points[0] if self._nearest_points[0]
                          < self._nearest_points[1] else self._nearest_points[1])
            insert_pos = insert_pos % len(self._shapes[0])
            self._shapes[0].insert(insert_pos, self._curr_mouse_pos)
            self._nearest_points = None
            self._hover_point = insert_pos
            self._dragging = True
            self._drag_start = self._curr_mouse_pos
            self._redraw = True
            return True
        return False

    def _recalculate_data(self):
        # TODO: Optimize further, only need to do a lot of work below if certain things changed
        # from the last calculation point.
        if self._curr_mouse_pos is None:
            return
        last_hover = self._hover_point
        last_nearest = self._nearest_points
        # Calculate distance from mouse cursor  to each point.
        self._mouse_dist = [
            squared_distance(self._curr_mouse_pos, point) for point in self._shapes[0]
        ]
        # Check if we're hovering over a point.
        self._hover_point = self._hovering_over()
        # Optimization: Only recalculate segment distances if we aren't hovering over a point.
        if self._hover_point is None:
            num_points = len(self._shapes[0])
            self._segment_dist = [
                squared_distance(self._shapes[0][i], self._shapes[0][(i + 1) % num_points])
                for i in range(num_points)
            ]
            self._find_nearest()
        if last_hover != self._hover_point or last_nearest != self._nearest_points:
            self._redraw = True
        self._recalculate = False

    def _handle_mouse_input(self, event, x, y, flags, param):
        # TODO: Map mouse events to callbacks rather than handling each event conditionally.
        drag_started = False
        bounded = bound_point(point=Point(x, y), size=self._frame_size)
        self._curr_mouse_pos = Point(bounded.x * self._scale, bounded.y * self._scale)

        if event == cv2.EVENT_LBUTTONDOWN:
            if not self._hover_point is None:
                self._dragging = True
                self._drag_start = self._curr_mouse_pos
                self._redraw = True
                drag_started = True
            else:
                drag_started = self._add_point()

        elif event == cv2.EVENT_MOUSEMOVE:
            if self._dragging:
                self._shapes[0][self._hover_point] = self._curr_mouse_pos
                self._redraw = True
            else:
                self._recalculate = True

        elif event == cv2.EVENT_LBUTTONUP:
            if self._dragging:
                assert not self._hover_point is None
                if (len(self._shapes[0]) != len(self._history[self._history_pos])
                        or self._curr_mouse_pos != self._drag_start):
                    self._shapes[0][self._hover_point] = self._curr_mouse_pos
                    x, y = self._shapes[0][self._hover_point]
                    logger.debug("Add: [%d] = %s", self._hover_point, f'P({x},{y})')
                    self._commit()
                self._redraw = True
            self._dragging = False

        elif event == cv2.EVENT_MBUTTONDOWN or IS_WINDOWS and event == cv2.EVENT_RBUTTONDOWN:
            self._delete_point()

        # Only draw again if we aren't dragging (too many events to draw on each one), or if
        # we just started dragging a point (so it changes colour quicker).
        if not self._dragging or drag_started:
            self._draw()
