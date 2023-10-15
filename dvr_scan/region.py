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
"""DVR-Scan Region Editor handles detection region input and processing.

Regions are represented as a set of closed polygons defined by lists of points.
"""

from collections import namedtuple
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

# TODO(v1.6): Update screenshots to reflect release title.
_WINDOW_NAME = "DVR-Scan Region Editor"
"""Title given to the ROI selection window."""

KEYCODE_ESCAPE = ord('\x1b')
KEYCODE_RETURN = ord('\r')
KEYCODE_SPACE = ord(' ')
KEYCODE_WINDOWS_UNDO = 26
KEYCODE_WINDOWS_REDO = 25

DEFAULT_WINDOW_MODE = (cv2.WINDOW_AUTOSIZE if IS_WINDOWS else cv2.WINDOW_KEEPRATIO)
"""Minimum height/width for a ROI created using the mouse."""

MIN_SIZE = 16
"""Minimum height/width for a ROI created using the mouse."""

logger = getLogger('dvr_scan')
Point = namedtuple("Point", ['x', 'y'])
Size = namedtuple("Size", ['w', 'h'])
InputRectangle = ty.Tuple[Point, Point]


@dataclass
class Snapshot:
    regions: ty.List[ty.List[Point]]
    active_shape: ty.Optional[int]


def check_tkinter_support(warn_if_notkinter: bool):
    if warn_if_notkinter and not HAS_TKINTER:
        logger.warning(
            "Warning: Tkinter is not installed. To save the region to disk, use "
            "-s/--save-region [FILE], or install python3-tk (e.g. `sudo apt install python3-tk`).")


class RegionValidator:
    """Validator for a set of points representing a closed polygon."""

    _IGNORE_CHARS = [',', '/', '(', ')', '[', ']']
    """Characters to ignore."""

    def __init__(self, value: str):
        translation_table = str.maketrans({char: ' ' for char in RegionValidator._IGNORE_CHARS})
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


# TODO(v1.7): Allow controlling some of these settings in the config file.
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


# TODO(v1.7): Move more of these to SelectionWindowSettings.
MIN_NUM_POINTS = 3
MAX_HISTORY_SIZE = 1024
MIN_DOWNSCALE_FACTOR = 1
MAX_DOWNSCALE_FACTOR = 50
MAX_UPDATE_RATE_NORMAL = 20
MAX_UPDATE_RATE_DRAGGING = 5
HOVER_DISPLAY_DISTANCE = 260**2
MAX_DOWNSCALE_AA_LEVEL = 4

KEYBIND_BREAKPOINT = 'b'
KEYBIND_DOWNSCALE_INC = 'w'
KEYBIND_DOWNSCALE_DEC = 'e'
KEYBIND_HELP = 'h'
KEYBIND_LOAD = 'o'
KEYBIND_MASK = 'm'
KEYBIND_OUTPUT_LIST = 'c'
KEYBIND_POINT_ADD = 'a'
KEYBIND_POINT_DELETE = 'x'
KEYBIND_REGION_ADD = 't'
KEYBIND_REGION_DELETE = 'g'
KEYBIND_REGION_NEXT = 'l'
KEYBIND_REGION_PREVIOUS = 'k'
KEYBIND_REDO = 'y'
KEYBIND_TOGGLE_AA = 'q'
KEYBIND_SAVE = 's'
KEYBIND_UNDO = 'z'
KEYBIND_WINDOW_MODE = 'r'


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

Editor:
  Mask On/Off         Key: {str(KEYBIND_MASK).upper()}
  Start Scan          Key: Space, Enter
  Quit                Key: Escape
  Save                Key: {str(KEYBIND_SAVE).upper()}
  Load                Key: {str(KEYBIND_LOAD).upper()}
  Undo                Key: {str(KEYBIND_UNDO).upper()}
  Redo                Key: {str(KEYBIND_REDO).upper()}
  Print Points        Key: {str(KEYBIND_OUTPUT_LIST).upper()}

Regions:
  Add Point           Key: {str(KEYBIND_POINT_ADD).upper()},  Mouse: Left
  Delete Point        Key: {str(KEYBIND_POINT_DELETE).upper()},  Mouse: {_WINDOWS_ONLY}Middle
  Add Region          Key: Shift + {str(KEYBIND_REGION_ADD).upper()}
  Delete Region       Key: Shift + {str(KEYBIND_REGION_DELETE).upper()}
  Select Region       Key: 1 - 9
  Next Region         Key: {str(KEYBIND_REGION_NEXT).upper()}
  Previous Region     Key: {str(KEYBIND_REGION_PREVIOUS).upper()}

Display:
  Downscale +/-       Key: {str(KEYBIND_DOWNSCALE_INC).upper()}(+), {str(KEYBIND_DOWNSCALE_DEC).upper()} (-)
  Antialiasing        Key: {str(KEYBIND_TOGGLE_AA).upper()}
  Window Mode         Key: {str(KEYBIND_WINDOW_MODE).upper()}
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


def load_regions(path: ty.AnyStr) -> ty.Iterable[RegionValidator]:
    region_data = None
    with open(path, 'rt') as file:
        region_data = file.readlines()
    if region_data:
        return list(
            RegionValidator(region).value
            for region in filter(None, (region.strip() for region in region_data)))
    return []


# TODO(v1.7): Allow multiple polygons by adding new ones using keyboard.
# TODO(v1.7): Allow shifting polygons by using middle mouse button.
class SelectionWindow:

    def __init__(self, frame: np.ndarray, initial_shapes: ty.Optional[ty.List[ty.List[Point]]],
                 initial_scale: ty.Optional[int], debug_mode: bool):
        self._source_frame = frame.copy()   # Frame before downscaling
        self._source_size = Size(w=frame.shape[1], h=frame.shape[0])
        self._scale: int = 1 if initial_scale is None else initial_scale
        self._frame = frame.copy()          # Workspace
        self._frame_size = Size(w=frame.shape[1], h=frame.shape[0])
        self._original_frame = frame.copy() # Copy to redraw on
        if initial_shapes:
            self._regions = initial_shapes
        else:
            self._regions = [initial_point_list(self._frame_size)]
        self._active_shape = len(self._regions) - 1
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
        return self._regions

    @property
    def active_region(self) -> ty.Optional[ty.List[Point]]:
        return self._regions[self._active_shape] if (not self._active_shape is None
                                                     and bool(self._regions)) else None

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
            snapshot = deepcopy(self._history[self._history_pos])
            self._regions = snapshot.regions
            self._active_shape = snapshot.active_shape
            self._recalculate = True
            self._redraw = True
            logger.debug("Undo: [%d/%d]", self._history_pos, len(self._history) - 1)

    def _redo(self):
        if self._history_pos > 0:
            self._history_pos -= 1
            snapshot = deepcopy(self._history[self._history_pos])
            self._regions = snapshot.regions
            self._active_shape = snapshot.active_shape
            self._recalculate = True
            self._redraw = True
            logger.debug("Redo: [%d/%d]", self._history_pos, len(self._history) - 1)

    def _commit(self):
        snapshot = deepcopy(Snapshot(regions=self._regions, active_shape=self._active_shape))
        self._history = self._history[self._history_pos:]
        self._history.insert(0, snapshot)
        self._history = self._history[:MAX_HISTORY_SIZE]
        self._history_pos = 0
        self._recalculate = True
        self._redraw = True

    def _emit_points(self):
        region_info = []
        for shape in self._regions:
            region_info.append("--region %s" % " ".join(f"{x} {y}" for x, y in shape))
        logger.info("Region data for CLI:\n%s", " ".join(region_info))

    def _draw(self):
        if self._recalculate:
            self._recalculate_data()
        if not self._redraw:
            return

        frame = self._original_frame.copy()
        # Mask pixels outside of the defined region if we're in mask mode.
        if self._settings.mask_source:
            mask = np.zeros_like(frame, dtype=np.uint8)
            for shape in self._regions:
                points = np.array([shape], np.int32)
                if self._scale > 1:
                    points = points // self._scale
                mask = cv2.fillPoly(mask, points, color=(255, 255, 255), lineType=cv2.LINE_4)
            # TODO: We can pre-calculate a masked version of the frame and just swap both out.
            frame = np.bitwise_and(frame, mask).astype(np.uint8)

        thickness = edge_thickness(self._scale)
        thickness_active = edge_thickness(self._scale, 1)
        for shape in self._regions:
            points = np.array([shape], np.int32)
            if self._scale > 1:
                points = points // self._scale
            line_type = cv2.LINE_AA if self._settings.use_aa and self._scale <= MAX_DOWNSCALE_AA_LEVEL else cv2.LINE_4
            #
            if not self._settings.mask_source:
                frame = cv2.polylines(
                    frame,
                    points,
                    isClosed=True,
                    color=self._settings.line_color,
                    thickness=thickness,
                    lineType=line_type)
        if not self._hover_point is None and not self._settings.mask_source:
            first, mid, last = ((self._hover_point - 1) % len(self.active_region),
                                self._hover_point,
                                (self._hover_point + 1) % len(self.active_region))
            points = np.array(
                [[self.active_region[first], self.active_region[mid], self.active_region[last]]],
                np.int32)
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
        elif not self._nearest_points is None and self._settings.highlight_insert and not self._settings.mask_source:

            points = np.array([[
                self.active_region[self._nearest_points[0]],
                self.active_region[self._nearest_points[1]]
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

        if not self.active_region is None:
            radius = control_handle_radius(self._scale)
            for i, point in enumerate(self.active_region):
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
        cv2.imshow(_WINDOW_NAME, self._frame)
        self._redraw = False

    def _find_nearest(self) -> ty.Tuple[int, int]:
        nearest_seg, nearest_dist, largest_cosine = 0, 2**31, math.pi
        for i in range(len(self.active_region)):
            # Create a triangle where side a's length is the mouse to closest point on the line,
            # side c is the length to the furthest point, and side b is the line segment length.
            next = (i + 1) % len(self.active_region)
            a_sq = min(self._mouse_dist[i], self._mouse_dist[next])
            c_sq = max(self._mouse_dist[i], self._mouse_dist[next])
            b_sq = self._segment_dist[i]
            assert a_sq > 0 # Should never hit this since we check _hovering_over first.
            if b_sq == 0:
                            # Two adjacent points are overlapping, just skip this one.
                continue
            a, b = math.sqrt(a_sq), math.sqrt(b_sq)
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
        self._nearest_points = (nearest_seg, (nearest_seg + 1) % len(self.active_region))

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
        cv2.namedWindow(_WINDOW_NAME, self._settings.window_mode)
        if self._settings.window_mode == cv2.WINDOW_AUTOSIZE:
            cv2.resizeWindow(_WINDOW_NAME, width=self._frame_size.w, height=self._frame_size.h)
        cv2.imshow(_WINDOW_NAME, mat=self._frame)
        cv2.setMouseCallback(_WINDOW_NAME, on_mouse=self._handle_mouse_input)

    def _breakpoint(self):
        if self._debug_mode:
            breakpoint()

    def _create_keymap(self) -> ty.Dict[int, ty.Callable]:
        return {
            KEYBIND_BREAKPOINT: lambda: self._breakpoint,
            KEYBIND_DOWNSCALE_INC: lambda: self._adjust_downscale(1),
            KEYBIND_DOWNSCALE_DEC: lambda: self._adjust_downscale(-1),
            KEYBIND_HELP: lambda: show_controls(),
            KEYBIND_LOAD: lambda: self._load(),
            KEYBIND_MASK: lambda: self._toggle_mask(),
            KEYBIND_OUTPUT_LIST: lambda: self._emit_points(),
            KEYBIND_POINT_ADD: lambda: self._add_point(),
            KEYBIND_POINT_DELETE: lambda: self._delete_point(),
            KEYBIND_REGION_ADD: lambda: self._add_region(),
            KEYBIND_REGION_DELETE: lambda: self._delete_region(),
            KEYBIND_REGION_NEXT: lambda: self._next_region(),
            KEYBIND_REGION_PREVIOUS: lambda: self._prev_region(),
            KEYBIND_REDO: lambda: self._redo(),
            KEYBIND_TOGGLE_AA: lambda: self._toggle_antialiasing(),
            KEYBIND_SAVE: lambda: self._save(),
            KEYBIND_UNDO: lambda: self._undo(),
            KEYBIND_WINDOW_MODE: lambda: self._toggle_window_mode(),
            chr(KEYCODE_WINDOWS_REDO): lambda: self._redo(),
            chr(KEYCODE_WINDOWS_UNDO): lambda: self._undo(),
        }

    def run(self, warn_if_notkinter: bool) -> bool:
        try:
            logger.debug("Creating window for frame (scale = %d)", self._scale)
            self._init_window()
            check_tkinter_support(warn_if_notkinter)
            set_icon(_WINDOW_NAME)
            regions_valid = False
            logger.info(f"Region editor active. Press {KEYBIND_HELP} to show controls.")
            keyboard_callbacks = self._create_keymap()
            while True:
                if not cv2.getWindowProperty(_WINDOW_NAME, cv2.WND_PROP_VISIBLE):
                    logger.debug("Main window closed.")
                    break
                self._draw()
                key = cv2.waitKey(MAX_UPDATE_RATE_NORMAL
                                  if not self._dragging else MAX_UPDATE_RATE_DRAGGING) & 0xFF
                if key == KEYCODE_ESCAPE:
                    break
                elif key in (KEYCODE_SPACE, KEYCODE_RETURN):
                    regions_valid = True
                    break
                elif key >= ord('0') and key <= ord('9'):
                    self._select_region((key - ord('1')) % 10)
                elif chr(key) in keyboard_callbacks:
                    keyboard_callbacks[chr(key)]()
                elif key != 0xFF and self._debug_mode:
                    logger.debug("Unhandled key: %s", str(key))
            return regions_valid

        finally:
            cv2.destroyAllWindows()

    def _adjust_downscale(self, amount: int):
        # scale is clamped to MIN_DOWNSCALE_FACTOR/MAX_DOWNSCALE_FACTOR.
        scale = self._scale + amount
        self._scale = (
            MIN_DOWNSCALE_FACTOR if scale < MIN_DOWNSCALE_FACTOR else
            scale if scale < MAX_DOWNSCALE_FACTOR else MAX_DOWNSCALE_FACTOR)
        self._rescale()

    def _save(self):
        if not HAS_TKINTER:
            logger.debug("Cannot show file dialog.")
            return
        save_path = None
        with temp_tk_window() as _:
            save_path = tkinter.filedialog.asksaveasfilename(
                title="DVR-Scan: Save Region",
                filetypes=[("Region File", "*.txt")],
                defaultextension=".txt",
                confirmoverwrite=True,
            )
        if save_path:
            with open(save_path, "wt") as region_file:
                for shape in self._regions:
                    region_file.write(" ".join(f"{x} {y}" for x, y in shape))
                    region_file.write("\n")
            logger.info('Saved region to: %s', save_path)

    def _load(self):
        if not HAS_TKINTER:
            logger.debug("Cannot show file dialog.")
            return
        load_path = None
        with temp_tk_window() as _:
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
        regions = []
        try:
            logger.debug(f"Loading regions from file: {load_path}")
            regions = load_regions(load_path)
        except ValueError as ex:
            reason = " ".join(str(arg) for arg in ex.args)
            if not reason:
                reason = "Could not parse region file!"
            logger.error(f"Error loading region from {load_path}: {reason}")
        else:
            logger.debug("Loaded %d region%s from region file:\n%s", len(regions),
                         's' if len(regions) > 1 else '',
                         "\n".join(f"[{i}] = {points}" for i, points in enumerate(regions)))

            self._regions = [
                [bound_point(point, self._source_size) for point in shape] for shape in regions
            ]
            self._commit()
            self._active_shape = 0 if len(self._regions) > 0 else None

    def _delete_point(self):
        if not self._hover_point is None and not self._dragging:
            if len(self.active_region) > MIN_NUM_POINTS:
                hover = self._hover_point
                x, y = self.active_region[hover]
                del self.active_region[hover]
                self._hover_point = None
                logger.debug("Del: [%d] = %s", hover, f'P({x},{y})')
                self._commit()
            else:
                logger.error("Cannot remove point, shape must have at least 3 points.")
            self._dragging = False

    def _toggle_antialiasing(self):
        self._settings.use_aa = not self._settings.use_aa
        self._redraw = True
        logger.debug("AA: %s", "ON" if self._settings.use_aa else "OFF")
        if self._scale >= MAX_DOWNSCALE_AA_LEVEL:
            logger.warning("AA is disabled due to current scale factor.")

    def _toggle_mask(self):
        self._settings.mask_source = not self._settings.mask_source
        logger.debug("Masking: %s", "ON" if self._settings.mask_source else "OFF")
        self._redraw = True

    def _toggle_window_mode(self):
        cv2.destroyWindow(_WINDOW_NAME)
        if self._settings.window_mode == cv2.WINDOW_KEEPRATIO:
            self._settings.window_mode = cv2.WINDOW_AUTOSIZE
        else:
            self._settings.window_mode = cv2.WINDOW_KEEPRATIO
        logger.debug(
            "Window Mode: %s",
            "KEEPRATIO" if self._settings.window_mode == cv2.WINDOW_KEEPRATIO else "AUTOSIZE")
        self._init_window()

    def _add_point(self) -> bool:
        if not self._nearest_points is None:
            insert_pos = (1 + self._nearest_points[0] if self._nearest_points[0]
                          < self._nearest_points[1] else self._nearest_points[1])
            insert_pos = insert_pos % len(self.active_region)
            self.active_region.insert(insert_pos, self._curr_mouse_pos)
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
        if not self._regions or self.active_region is None:
            self._hover_point = None
            self._nearest_points = None
            return
        last_hover = self._hover_point
        last_nearest = self._nearest_points
        # Calculate distance from mouse cursor to each point.
        self._mouse_dist = [
            squared_distance(self._curr_mouse_pos, point) for point in self.active_region
        ]
        # Check if we're hovering over a point.
        self._hover_point = self._hovering_over()
        # Optimization: Only recalculate segment distances if we aren't hovering over a point.
        if self._hover_point is None:
            num_points = len(self.active_region)
            self._segment_dist = [
                squared_distance(self.active_region[i], self.active_region[(i + 1) % num_points])
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
            if not self._regions:
                logger.info(f"No regions to edit, add a new one by pressing {KEYBIND_REGION_ADD}.")
            if not self._hover_point is None:
                self._dragging = True
                self._drag_start = self._curr_mouse_pos
                self._redraw = True
                drag_started = True
            else:
                drag_started = self._add_point()

        elif event == cv2.EVENT_MOUSEMOVE:
            if self._dragging:
                self.active_region[self._hover_point] = self._curr_mouse_pos
                self._redraw = True
            else:
                self._recalculate = True

        elif event == cv2.EVENT_LBUTTONUP:
            if self._dragging:
                assert not self._hover_point is None
                if (len(self.active_region) != len(self._history[self._history_pos].regions)
                        or self._curr_mouse_pos != self._drag_start):
                    self.active_region[self._hover_point] = self._curr_mouse_pos
                    x, y = self.active_region[self._hover_point]
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

    def _add_region(self):
        if self._dragging:
            return

        # Add a box around the current mouse position that's roughly 20% of the frame.
        width, height = max(1, self._source_size.w // 10), max(1, self._source_size.h // 10)

        top_left = Point(x=self._curr_mouse_pos.x - width, y=self._curr_mouse_pos.y - height)
        points = [
            top_left,
            Point(x=top_left.x + 2 * width, y=top_left.y),
            Point(x=top_left.x + 2 * width, y=top_left.y + 2 * height),
            Point(x=top_left.x, y=top_left.y + 2 * height),
        ]

        self._regions.append([bound_point(point, self._source_size) for point in points])
        self._commit()
        self._active_shape = len(self._regions) - 1
        self._recalculate = True
        self._redraw = True

    def _delete_region(self):
        if self._dragging:
            return
        if self._regions:
            del self._regions[self._active_shape]
            self._commit()
            if not self._regions:
                self._active_shape = None
            else:
                self._active_shape = (self._active_shape - 1) % len(self._regions)
            self._recalculate = True
            self._redraw = True

    def _select_region(self, index: int):
        if self._dragging:
            return
        assert index >= 0
        if self._regions and index < len(self._regions):
            self._active_shape = index
            self._recalculate = True
            self._redraw = True

    def _next_region(self):
        if self._dragging:
            return
        if self._regions:
            self._active_shape = (self._active_shape + 1) % len(self._regions)
            self._recalculate = True
            self._redraw = True

    def _prev_region(self):
        if self._dragging:
            return
        if self._regions:
            self._active_shape = (self._active_shape - 1) % len(self._regions)
            self._recalculate = True
            self._redraw = True
