#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2024 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#

import math
import os
import os.path
import sys
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.scrolledtext
import tkinter.ttk as ttk
import typing as ty
import webbrowser
from copy import deepcopy
from dataclasses import dataclass
from logging import getLogger

import cv2
import numpy as np
import PIL
import PIL.Image
import PIL.ImageTk

import dvr_scan
from dvr_scan.app.about_window import AboutWindow
from dvr_scan.app.common import register_icon
from dvr_scan.region import Point, Size, bound_point, load_regions

WINDOW_TITLE = "DVR-Scan Region Editor"
OWNED_WINDOW_TITLE = "Region Editor"
PROMPT_TITLE = "DVR-Scan"
PROMPT_MESSAGE = "You have unsaved region changes.\nDo you want to save them?"
SAVE_TITLE = "Save Region File"
LOAD_TITLE = "Load Region File"
SAVE_REGIONS = "Save Regions"
SAVE_REGIONS_PROMPT = "Save Regions..."
ABOUT_WINDOW_COPYRIGHT = (
    f"DVR-Scan {dvr_scan.__version__}\n\nCopyright © Brandon Castellano.\nAll rights reserved."
)

# TODO: Need to figure out DPI scaling for *everything*. Lots of magic numbers for sizes right now.
MIN_SIZE = 16
"""Minimum height/width for a ROI created using the mouse."""

logger = getLogger("dvr_scan")


@dataclass
class Snapshot:
    regions: ty.List[ty.List[Point]]
    active_shape: ty.Optional[int]


# TODO: Allow controlling some of these settings in the config file.
@dataclass
class EditorSettings:
    video_path: str
    """The first input video path specified by -i/--input."""
    save_path: ty.Optional[str] = False
    """The path specified by the -s/--save-regions option if set."""
    use_aa: bool = True
    mask_source: bool = False
    line_color: ty.Tuple[int, int, int] = (255, 0, 0)
    line_color_alt: ty.Tuple[int, int, int] = (255, 153, 51)
    line_color_inactive: ty.Tuple[int, int, int] = (172, 80, 24)
    hover_color: ty.Tuple[int, int, int] = (0, 127, 255)
    hover_color_alt: ty.Tuple[int, int, int] = (0, 0, 255)
    interact_color: ty.Tuple[int, int, int] = (0, 255, 255)


class AutoHideScrollbar(tk.Scrollbar):
    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
            tk.Scrollbar.set(self, lo, hi)


MIN_NUM_POINTS = 3
MAX_HISTORY_SIZE = 1024
MIN_DOWNSCALE_FACTOR = 1
MAX_DOWNSCALE_FACTOR = 10
MAX_UPDATE_RATE_NORMAL = 20
MAX_UPDATE_RATE_DRAGGING = 5
HOVER_DISPLAY_DISTANCE = 260**2
MAX_DOWNSCALE_AA_LEVEL = 4

ACCELERATOR_KEY = "Command" if sys.platform == "darwin" else "Ctrl"
KEYBIND_POINT_ADD = "+"
KEYBIND_POINT_ADD_ALT1 = "="
KEYBIND_POINT_ADD_ALT2 = "KP_Add"
KEYBIND_POINT_DELETE = "-"
KEYBIND_POINT_DELETE_ALT1 = "_"
KEYBIND_POINT_DELETE_ALT2 = "KP_Minus"
KEYBIND_REGION_ADD = f"{ACCELERATOR_KEY}+N"
KEYBIND_REGION_DELETE = f"{ACCELERATOR_KEY}+D"
KEYBIND_REGION_NEXT = "Tab"
KEYBIND_REGION_PREVIOUS = "Shift+Tab"
KEYBIND_TOGGLE_AA = f"{ACCELERATOR_KEY}+A"
KEYBIND_DOWNSCALE_INC = f"{ACCELERATOR_KEY}+(+)"
KEYBIND_DOWNSCALE_DEC = f"{ACCELERATOR_KEY}+(-)"
KEYBIND_BREAKPOINT = f"{ACCELERATOR_KEY}+B"
KEYBIND_MASK = f"{ACCELERATOR_KEY}+M"

KEYBIND_LOAD = f"{ACCELERATOR_KEY}+O"
KEYBIND_SAVE = f"{ACCELERATOR_KEY}+S"
KEYBIND_COPY_COMMAND = f"{ACCELERATOR_KEY}+C"
KEYBIND_HELP = f"{ACCELERATOR_KEY}+H"
KEYBIND_QUIT = f"{ACCELERATOR_KEY}+Q"
KEYBIND_START_SCAN = f"{ACCELERATOR_KEY}+Space"

KEYBIND_UNDO = "Ctrl+Z" if os.name == "nt" else f"{ACCELERATOR_KEY}+Z"
KEYBIND_REDO = "Ctrl+Y" if os.name == "nt" else f"{ACCELERATOR_KEY}+Shift+Z"


def control_handle_radius(scale: int):
    """Get size of point control handles based on scale factor."""
    # TODO: This should be based on the video resolution in addition to scale factor.
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
    # TODO: This should be based on the video resolution in addition to scale factor.
    if scale < 2:
        return 4 + ext
    elif scale < 5:
        return 3 + ext
    elif scale <= 10:
        return 2 + ext
    return 1 + ext if scale <= 20 else 0


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


def squared_distance(a: Point, b: Point) -> int:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


# TODO: Allow translating polygons using middle mouse button.
class RegionEditor:
    def __init__(
        self,
        frame: np.ndarray,
        initial_shapes: ty.Optional[ty.List[ty.List[Point]]],
        initial_scale: ty.Optional[int],
        debug_mode: bool,
        video_path: str,
        save_path: ty.Optional[str],
        on_close: ty.Optional[ty.Callable[[], None]] = None,
    ):
        self._settings = EditorSettings(video_path=video_path, save_path=save_path)
        self._source_frame: np.ndarray = frame.copy()  # Frame before downscaling
        self._source_size: Size = Size(w=frame.shape[1], h=frame.shape[0])
        self._frame: np.ndarray = frame.copy()  # Workspace
        self._frame_size: Size = Size(w=frame.shape[1], h=frame.shape[0])
        self._original_frame: np.ndarray = frame.copy()  # Copy to redraw on
        self._regions: ty.List[ty.List[Point]] = (
            initial_shapes if initial_shapes else [initial_point_list(self._frame_size)]
        )
        self._active_shape: int = len(self._regions) - 1
        self._history: ty.List[Snapshot] = []
        self._history_pos: int = 0

        self._curr_mouse_pos: Point = None
        self._hover_point: ty.Optional[int] = None
        self._nearest_points: ty.Optional[ty.Tuple[int, int]] = None

        self._redraw: bool = True
        self._recalculate: bool = True
        self._dragging: bool = False
        self._drag_start: ty.Optional[Point] = None
        self._debug_mode: bool = debug_mode
        self._segment_dist: ty.List[int] = []  # Square distance of segment from point i to i+1
        self._mouse_dist: ty.List[int] = []  # Square distance of mouse to point i
        self._scale: int = 1 if initial_scale is None else initial_scale
        self._persisted: bool = True  # Indicates if we've saved outstanding changes to disk.
        self._persisted_path: str = ""  # Path we've saved changes to, if any.

        self._launched_from_app: bool = False
        self._on_close: ty.Optional[ty.Callable[[], None]] = on_close
        self._root: ty.Union[tk.Tk, tk.Toplevel] = None
        self._edit_menu: tk.Menu = None
        self._editor_window: tk.Toplevel = None
        self._editor_canvas: tk.Canvas = None
        self._editor_scroll: ty.Tuple[tk.Scrollbar, tk.Scrollbar] = None
        self._should_scan: bool = False
        self._scale_widget: ttk.Scale = None
        self._pan_enabled: bool = False
        self._panning: bool = False
        self._controls_window: tk.Toplevel = None
        self._region_selector: ttk.Combobox = None

        self._context_menu: tk.Menu = None
        # Clones of the normal state variables since sometimes we can still interact with the main
        # window after the context menu is posted.
        self._context_curr_mouse_pos: Point = None
        self._context_hover_point: ty.Optional[int] = None
        self._context_nearest_points: ty.Optional[ty.Tuple[int, int]] = None

        self._log_stats = False
        self._redraws = 0
        self._recalculates = 0

        self._commit(persisted=True)  # Add initial history for undo.

    @property
    def shapes(self) -> ty.Iterable[ty.Iterable[Point]]:
        return self._regions

    @property
    def active_region(self) -> ty.Optional[ty.List[Point]]:
        return (
            self._regions[self._active_shape]
            if (self._active_shape is not None and bool(self._regions))
            else None
        )

    @property
    def persisted(self) -> bool:
        return self._persisted

    @property
    def persisted_path(self) -> str:
        return self._persisted_path

    def _rescale(self, draw=True, allow_resize=True):
        assert self._scale > 0
        logger.info(f"Downscale factor: {self._scale}")
        self._original_frame = self._source_frame[:: self._scale, :: self._scale, :].copy()
        self._frame = self._original_frame.copy()
        self._frame_size = Size(w=self._frame.shape[1], h=self._frame.shape[0])
        self._redraw = True
        self._editor_canvas["scrollregion"] = (0, 0, self._frame.shape[1], self._frame.shape[0])
        if allow_resize:
            max_width_auto = int(self._root.winfo_screenwidth() * 0.8)
            max_height_auto = int(self._root.winfo_screenheight() * 0.8)
            self._editor_canvas["width"] = min(max_width_auto, self._frame.shape[1])
            self._editor_canvas["height"] = min(max_height_auto, self._frame.shape[0])
        else:
            old_geom = self._root.geometry()
            self._editor_canvas["width"] = self._frame.shape[1]
            self._editor_canvas["height"] = self._frame.shape[0]
            self._root.geometry(old_geom)

        if draw:
            self._draw()
        logger.debug(
            "Resize: scale = 1/%d%s, res = %d x %d",
            self._scale,
            " (off)" if self._scale == 1 else "",
            self._frame_size.w,
            self._frame_size.h,
        )

    def _undo(self):
        if self._history_pos < (len(self._history) - 1):
            self._history_pos += 1
            snapshot = deepcopy(self._history[self._history_pos])
            self._regions = snapshot.regions
            self._active_shape = snapshot.active_shape
            self._recalculate = True
            self._redraw = True
            self._draw()
            logger.debug("Undo: [%d/%d]", self._history_pos, len(self._history) - 1)
        self._update_ui_state()

    def _redo(self):
        if self._history_pos > 0:
            self._history_pos -= 1
            snapshot = deepcopy(self._history[self._history_pos])
            self._regions = snapshot.regions
            self._active_shape = snapshot.active_shape
            self._recalculate = True
            self._redraw = True
            self._draw()
            logger.debug("Redo: [%d/%d]", self._history_pos, len(self._history) - 1)
        self._update_ui_state()

    def _commit(self, persisted=False):
        # Take a copy of the current state and put it in the history buffer.
        snapshot = deepcopy(Snapshot(regions=self._regions, active_shape=self._active_shape))
        self._history = self._history[self._history_pos :]
        self._history.insert(0, snapshot)
        self._history = self._history[:MAX_HISTORY_SIZE]
        self._history_pos = 0
        # Update state.
        self._recalculate = True
        self._redraw = True
        self._persisted = persisted
        self._update_ui_state()

    def _update_ui_state(self):
        if self._root is None:
            return
        can_undo = self._history_pos < (len(self._history) - 1)
        self._edit_menu.entryconfigure("Undo", state=tk.ACTIVE if can_undo else tk.DISABLED)
        can_redo = self._history_pos > 0
        self._edit_menu.entryconfigure("Redo", state=tk.ACTIVE if can_redo else tk.DISABLED)
        if self._regions:
            self._region_selector["values"] = tuple(
                f"Shape {i + 1}" for i in range(len(self._regions))
            )
            assert self._active_shape is not None
            self._region_selector.current(self._active_shape)
            self._region_selector.config(state="readonly")
        else:
            self._region_selector["values"] = ("",)
            assert self._active_shape is not None
            self._region_selector.current(self._active_shape)
            self._region_selector.config(state="disabled")
        self._region_selector.selection_clear()

    def _copy_scan_command_to_clipboard(self):
        region_info = []
        for shape in self._regions:
            region_info.append("-a %s" % " ".join(f"{x} {y}" for x, y in shape))
        data = " ".join(region_info)
        scan_command = f"dvr-scan -i {self._settings.video_path} {data}"
        self._root.clipboard_append(scan_command)
        logger.info(
            f"Region data copied to clipboard. To scan via command-line, run:\n{scan_command}"
        )

    def _set_cursor(self):
        if self._pan_enabled or self._panning:
            self._editor_canvas.config(cursor="fleur")
        elif self._hover_point is None:
            self._editor_canvas.config(cursor="crosshair")
        else:
            self._editor_canvas.config(cursor="hand2")

    def _draw(self):
        self._set_cursor()
        if self._recalculate:
            self._recalculate_data()
        if not self._redraw:
            return
        if self._log_stats:
            self._redraws += 1
            logger.debug(f"redraw {self._redraws}")

        curr_aa = (
            cv2.LINE_AA
            if self._settings.use_aa and self._scale <= MAX_DOWNSCALE_AA_LEVEL
            else cv2.LINE_4
        )

        frame = self._original_frame.copy()

        # Mask pixels outside of the defined region if we're in mask mode.
        if self._settings.mask_source:
            mask = np.zeros_like(frame, dtype=np.uint8)
            for shape in self._regions:
                points = np.array([shape], np.int32)
                if self._scale > 1:
                    points = points // self._scale
                mask = cv2.fillPoly(mask, points, color=(255, 255, 255), lineType=curr_aa)
            frame = np.bitwise_and(frame, mask).astype(np.uint8)

        thickness = edge_thickness(self._scale)
        thickness_active = edge_thickness(self._scale, 1)
        for shape_index, shape in enumerate(self._regions):
            points = np.array([shape], np.int32)
            if self._scale > 1:
                points = points // self._scale
            #
            if not self._settings.mask_source:
                frame = cv2.polylines(
                    frame,
                    points,
                    isClosed=True,
                    color=self._settings.line_color
                    if shape_index == self._active_shape
                    else self._settings.line_color_inactive,
                    thickness=thickness,
                    lineType=curr_aa,
                )
        if self._hover_point is not None and not self._settings.mask_source:
            first, mid, last = (
                (self._hover_point - 1) % len(self.active_region),
                self._hover_point,
                (self._hover_point + 1) % len(self.active_region),
            )
            points = np.array(
                [
                    [
                        self.active_region[first],
                        self.active_region[mid],
                        self.active_region[last],
                    ]
                ],
                np.int32,
            )
            if self._scale > 1:
                points = points // self._scale
            frame = cv2.polylines(
                frame,
                points,
                isClosed=False,
                color=self._settings.hover_color
                if not self._dragging
                else self._settings.hover_color_alt,
                thickness=thickness_active,
                lineType=curr_aa,
            )
        elif self._nearest_points is not None and not self._settings.mask_source:
            points = np.array(
                [
                    [
                        self.active_region[self._nearest_points[0]],
                        self.active_region[self._nearest_points[1]],
                    ]
                ],
                np.int32,
            )
            if self._scale > 1:
                points = points // self._scale
            frame = cv2.polylines(
                frame,
                points,
                isClosed=False,
                color=self._settings.hover_color,
                thickness=thickness_active,
                lineType=curr_aa,
            )

        if self.active_region is not None:
            radius = control_handle_radius(self._scale)
            for i, point in enumerate(self.active_region):
                color = self._settings.line_color_alt
                if self._hover_point is not None:
                    if self._hover_point == i:
                        color = (
                            self._settings.hover_color_alt
                            if not self._dragging
                            else self._settings.interact_color
                        )
                elif self._nearest_points is not None and i in self._nearest_points:
                    color = (
                        self._settings.hover_color
                        if self._dragging
                        else self._settings.interact_color
                    )
                start, end = (
                    Point(
                        (point.x // self._scale) - radius,
                        (point.y // self._scale) - radius,
                    ),
                    Point(
                        (point.x // self._scale) + radius,
                        (point.y // self._scale) + radius,
                    ),
                )
                cv2.rectangle(
                    frame,
                    start,
                    end,
                    color,
                    thickness=cv2.FILLED,
                )

        self._frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._image = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(self._frame))
        self._editor_canvas.create_image(0, 0, anchor=tk.NW, image=self._image)
        self._redraw = False

    def _find_nearest_segment(self) -> ty.Tuple[int, int]:
        nearest_seg, nearest_dist, largest_cosine = 0, 2**31, math.pi
        for i in range(len(self.active_region)):
            # Create a triangle where side a's length is the mouse to closest point on the line,
            # side c is the length to the furthest point, and side b is the line segment length.
            next = (i + 1) % len(self.active_region)
            a_sq = min(self._mouse_dist[i], self._mouse_dist[next])
            c_sq = max(self._mouse_dist[i], self._mouse_dist[next])
            b_sq = self._segment_dist[i]
            assert a_sq > 0  # Should never hit this since we check _hovering_over first.
            if b_sq == 0:
                # Two adjacent points are overlapping, just skip this one.
                continue
            a, b = math.sqrt(a_sq), math.sqrt(b_sq)
            cos_C = ((a_sq + b_sq) - c_sq) / (2.0 * a * b)
            # If cos_C is between [0,1] the triangle is acute. If it's not, just take the distance
            # of the closest point.
            dist = int(a_sq - (int(a * cos_C) ** 2)) if cos_C > 0 else a_sq
            if dist < nearest_dist or (dist == nearest_dist and cos_C > largest_cosine):
                nearest_seg, nearest_dist, largest_cosine = i, dist, cos_C
        self._nearest_points = (
            nearest_seg,
            (nearest_seg + 1) % len(self.active_region),
        )

    def _find_hover_point(self) -> ty.Optional[int]:
        min_i = 0
        for i in range(1, len(self._mouse_dist)):
            if self._mouse_dist[i] < self._mouse_dist[min_i]:
                min_i = i
        # If we've shrunk the image, we need to compensate for the size difference in the image.
        # The control handles remain the same size but the image is smaller
        return (
            min_i
            if self._mouse_dist[min_i]
            <= (4 * control_handle_radius(self._scale) * self._scale) ** 2
            else None
        )

    def _breakpoint(self):
        if self._debug_mode:
            breakpoint()

    def _bind_keyboard(self) -> ty.Dict[int, ty.Callable]:
        for key, fn in {
            KEYBIND_BREAKPOINT: lambda _: self._breakpoint(),
            KEYBIND_POINT_ADD: lambda _: self._add_point(),
            KEYBIND_POINT_ADD_ALT1: lambda _: self._add_point(),
            KEYBIND_POINT_ADD_ALT2: lambda _: self._add_point(),
            KEYBIND_POINT_DELETE: lambda _: self._delete_point(),
            KEYBIND_POINT_DELETE_ALT1: lambda _: self._delete_point(),
            KEYBIND_POINT_DELETE_ALT2: lambda _: self._delete_point(),
        }.items():
            self._root.bind(key.lower(), fn)
        self._root.bind("<<Undo>>", lambda _: self._undo())
        self._root.bind("<<Redo>>", lambda _: self._redo())
        self._root.bind("<<Copy>>", lambda _: self._copy_scan_command_to_clipboard())

        self._root.bind("<Left>", lambda _: self._prev_region())
        self._root.bind("<Right>", lambda _: self._next_region())
        self._root.bind("<Tab>", lambda _: self._next_region())
        self._root.bind("<Shift-Tab>", lambda _: self._prev_region())

        self._root.bind("<Control-s>", lambda _: self._prompt_save())
        self._root.bind("<Control-o>", lambda _: self._prompt_load())
        self._root.bind("<Control-n>", lambda _: self._add_region())
        self._root.bind("<Control-h>", lambda _: self._show_help())
        self._root.bind("<Control-d>", lambda _: self._delete_region())
        self._root.bind("<Control-a>", lambda _: self._toggle_antialiasing())
        self._root.bind("<Control-m>", lambda _: self._toggle_mask())
        # +
        self._root.bind("<Control-plus>", lambda _: self._adjust_downscale(-1))
        self._root.bind("<Control-equal>", lambda _: self._adjust_downscale(-1))
        self._root.bind("<Control-KP_Add>", lambda _: self._adjust_downscale(-1))
        # -
        self._root.bind("<Control-minus>", lambda _: self._adjust_downscale(1))
        self._root.bind("<Control-underscore>", lambda _: self._adjust_downscale(1))
        self._root.bind("<Control-KP_Subtract>", lambda _: self._adjust_downscale(1))

        self._root.bind("<Escape>", lambda _: self._cancel_active_action())

        def quit():
            self._close(False)

        self._root.bind("<Control-q>", lambda _: quit())
        self._root.bind("<Control-Return>", lambda _: self._close(True))
        self._root.bind("<Control-space>", lambda _: self._close(True))

        def set_pan_mode(mode: bool):
            if self._dragging:
                self._pan_enabled = False
            else:
                self._pan_enabled = mode
            self._set_cursor()

        self._root.bind("<KeyPress-Control_L>", lambda _: set_pan_mode(True))
        self._root.bind("<KeyPress-Control_R>", lambda _: set_pan_mode(True))
        self._root.bind("<KeyRelease-Control_L>", lambda _: set_pan_mode(False))
        self._root.bind("<KeyRelease-Control_R>", lambda _: set_pan_mode(False))

        self._root.protocol("WM_DELETE_WINDOW", lambda: self._close(False))
        self._root.bind("<FocusOut>", lambda _: self._cancel_active_action())

        for i in range(9):

            def select_region(index):
                return lambda _: self._select_region(index)

            self._root.bind(f"{i + 1}", select_region(i))

        # TODO: If Shift is held down, allow translating current shape
        # by left-click and drag.

    def _close(self, should_scan: bool):
        if self._launched_from_app:
            self._root.destroy()
            self._on_close()
            return

        self._should_scan = should_scan
        if self.prompt_save_on_scan():
            self._root.destroy()

    def run(
        self,
        root: ty.Optional[tk.Tk] = None,
    ) -> ty.Optional[bool]:
        """Run the region editor. Returns True if the video should be scanned, False otherwise."""
        logger.debug("Creating window for frame (scale = %d)", self._scale)

        if root:
            self._root = tk.Toplevel(master=root)
            self._launched_from_app = True
        else:
            self._root = tk.Tk()

        if not self._regions:
            self._regions = [initial_point_list(self._frame_size)]

        # Withdraw root window until we're done adding everything to avoid visual flicker.
        self._root.withdraw()
        self._root.option_add("*tearOff", False)
        self._root.title(OWNED_WINDOW_TITLE if self._launched_from_app else WINDOW_TITLE)
        register_icon(self._root)
        self._root.resizable(True, True)
        self._root.minsize(width=320, height=240)
        self._editor_canvas = tk.Canvas(
            self._root,
        )
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        self._editor_canvas.grid(row=0, column=0, sticky="nsew")
        self._editor_scroll = (
            AutoHideScrollbar(self._root, command=self._editor_canvas.xview, orient=tk.HORIZONTAL),
            AutoHideScrollbar(self._root, command=self._editor_canvas.yview, orient=tk.VERTICAL),
        )
        self._editor_canvas["xscrollcommand"] = self._editor_scroll[0].set
        self._editor_canvas["yscrollcommand"] = self._editor_scroll[1].set
        self._editor_scroll[0].grid(row=1, column=0, sticky="ew")
        self._editor_scroll[1].grid(row=0, column=1, sticky="ns")

        ttk.Separator(self._root).grid(row=2, column=0, columnspan=2, sticky="ew")

        def set_scale(val: str):
            new_val = round(float(val))
            if self._scale != new_val:
                self._scale = new_val
                # Disable resize since we are probably using the mouse to control this widget.
                self._rescale(allow_resize=False)

        frame = tk.Frame(self._root)
        frame.grid(row=3, column=0, sticky="ew", columnspan=2)
        frame.columnconfigure(4, weight=1)
        frame.rowconfigure(0, weight=1)
        self._scale_widget = ttk.Scale(
            frame,
            orient=tk.HORIZONTAL,
            length=200,
            from_=MAX_DOWNSCALE_FACTOR,
            to=MIN_DOWNSCALE_FACTOR,
            command=set_scale,
            value=self._scale,
        )
        tk.Label(frame, text="Active Region", anchor=tk.W).grid(
            row=0, column=0, sticky=tk.W, padx=8.0
        )
        self._region_selector = ttk.Combobox(
            frame,
            values=list(f"Shape {i + 1}" for i in range(len(self._regions))),
            width=12,
            justify=tk.CENTER,
        )
        self._region_selector.state(["readonly"])
        self._region_selector.grid(row=0, column=1, sticky="w")
        self._region_selector.current(0)
        self._region_selector.bind("<<ComboboxSelected>>", lambda _: self._on_shape_select())
        # Looks weird when the widget takes focus, but still seems to work when we redirect focus to
        # the root.
        self._region_selector.bind("<FocusIn>", lambda _: self._root.focus())
        ttk.Button(frame, text="Toggle Mask", command=self._toggle_mask).grid(
            row=0, column=10, padx=8.0
        )
        self._scale_widget.grid(row=0, column=9, sticky="e", padx=8.0)
        tk.Label(frame, text="Zoom", anchor=tk.E).grid(row=0, column=8, sticky=tk.E, padx=(0, 8.0))

        self._bind_mouse()
        self._bind_keyboard()
        self._create_menubar()
        self._rescale(draw=False)
        self._redraw = True
        self._draw()

        self._root.deiconify()
        logger.info(f"Region editor active. Press {KEYBIND_HELP} to show controls.")

        self._root.focus()
        self._root.grab_release()
        if not self._launched_from_app:
            self._root.mainloop()
            return self._should_scan

    def _create_menubar(self):
        root_menu = tk.Menu(self._root)
        file_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=file_menu, label="File", underline=0)
        if not self._launched_from_app:
            file_menu.add_command(
                label="Start Scan",
                command=lambda: self._close(True),
                accelerator=KEYBIND_START_SCAN,
                underline=1,
            )
            file_menu.add_separator()
        file_menu.add_command(
            label="Open Regions...",
            command=self._prompt_load,
            accelerator=KEYBIND_LOAD,
            underline=0,
        )
        file_menu.add_command(
            label=SAVE_REGIONS if self._settings.save_path else SAVE_REGIONS_PROMPT,
            command=self._prompt_save,
            accelerator=KEYBIND_SAVE,
            underline=0,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Close" if self._launched_from_app else "Quit",
            command=lambda: self._close(False),
            accelerator=KEYBIND_QUIT,
        )

        edit_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=edit_menu, label="Edit", underline=0)
        edit_menu.add_command(
            label="Undo", command=self._undo, accelerator=KEYBIND_UNDO, underline=0
        )
        edit_menu.add_command(
            label="Redo", command=self._redo, accelerator=KEYBIND_REDO, underline=0
        )

        view_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=view_menu, label="View", underline=0)
        view_menu.add_command(
            label="Mask Mode", command=self._toggle_mask, accelerator=KEYBIND_MASK, underline=0
        )
        view_menu.add_command(
            label="Antialiasing",
            command=self._toggle_antialiasing,
            accelerator=KEYBIND_TOGGLE_AA,
            underline=0,
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Zoom In",
            command=lambda: self._adjust_downscale(-1),
            accelerator=KEYBIND_DOWNSCALE_DEC,
            underline=0,
        )
        view_menu.add_command(
            label="Zoom Out",
            command=lambda: self._adjust_downscale(1),
            accelerator=KEYBIND_DOWNSCALE_INC,
            underline=3,
        )

        help_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=help_menu, label="Help", underline=0)

        help_menu.add_command(
            label="Show Controls", command=self._show_help, accelerator=KEYBIND_HELP, underline=5
        )
        # TODO: Link to local copy of documentation included with distributions instead where
        # possible. This isn't always possible with how Python manages package resources, so we
        # might need to probe the directory the application was run from.
        help_menu.add_command(
            label="Online Manual",
            command=lambda: webbrowser.open_new_tab("www.dvr-scan.com/guide"),
            underline=0,
        )
        help_menu.add_command(
            label="Join Discord Chat",
            command=lambda: webbrowser.open_new_tab("https://discord.gg/69kf6f2Exb"),
            underline=5,
        )
        help_menu.add_separator()

        help_menu.add_command(
            label="About DVR-Scan", command=lambda: AboutWindow().show(root=self._root), underline=0
        )

        self._edit_menu = edit_menu
        self._root["menu"] = root_menu
        self._update_ui_state()

    def _show_help(self):
        if self._controls_window is None:
            self._controls_window = tk.Toplevel(master=self._root)
            self._controls_window.withdraw()
            self._controls_window.title("Controls")
            self._controls_window.resizable(True, True)
            self._controls_window.transient(self._root)

            def dismiss():
                self._controls_window.destroy()
                self._controls_window = None
                self._root.focus()

            self._controls_window.protocol("WM_DELETE_WINDOW", dismiss)
            self._controls_window.attributes("-topmost", True)
            self._controls_window.bind("<Destroy>", lambda _: dismiss())
            self._controls_window.bind("<FocusIn>", lambda _: self._root.focus())

            def handle_escape(_: tk.Event):
                self._controls_window.destroy()
                self._controls_window = None

            self._controls_window.bind("<Escape>", handle_escape)

            regions = ttk.Labelframe(self._controls_window, text="Regions", padding=8.0)
            regions.columnconfigure(0, weight=1)
            regions.columnconfigure(1, weight=1)

            ttk.Label(regions, text="Add Point").grid(row=0, column=0, sticky="w")
            ttk.Label(regions, text="Left Click\nKeyboard: +", justify=tk.RIGHT).grid(
                row=0, column=1, sticky="e"
            )

            ttk.Label(regions, text="Remove Point").grid(row=1, column=0, sticky="w")
            ttk.Label(regions, text="Right Click\nKeyboard: -", justify=tk.RIGHT).grid(
                row=1, column=1, sticky="e"
            )

            ttk.Label(regions, text="Move Point").grid(row=2, column=0, sticky="w")
            ttk.Label(regions, text="Left Click + Drag").grid(row=2, column=1, sticky="e")

            ttk.Label(regions, text="").grid(row=4, column=0, sticky="w")

            ttk.Label(regions, text="Add/Remove Shape").grid(row=5, column=0, sticky="w")
            ttk.Label(
                regions,
                text=f"Mouse: Right Click\nKeyboard: {KEYBIND_REGION_ADD}",
                justify=tk.RIGHT,
            ).grid(row=5, column=1, sticky="e")

            ttk.Label(regions, text="Active Shape").grid(row=6, column=0, sticky="w")
            ttk.Label(
                regions,
                text="Mouse: Right Click\nKeyboard: "
                f"{KEYBIND_REGION_NEXT}/{KEYBIND_REGION_PREVIOUS}",
                justify=tk.RIGHT,
            ).grid(row=6, column=1, sticky="e")

            viewport = ttk.Labelframe(self._controls_window, text="Viewport", padding=8.0)
            viewport.columnconfigure(0, weight=1)
            viewport.columnconfigure(1, weight=1)

            ttk.Label(viewport, text="Zoom").grid(row=0, column=0, sticky="w")
            ttk.Label(
                viewport,
                text=f"Mouse: {ACCELERATOR_KEY} + Scroll\nKeyboard: "
                f"{KEYBIND_DOWNSCALE_INC}/{KEYBIND_DOWNSCALE_DEC}",
                justify=tk.RIGHT,
            ).grid(row=0, column=1, sticky="e")

            ttk.Label(viewport, text="Move/Pan").grid(row=3, column=0, sticky="w")
            ttk.Label(viewport, text=f"{ACCELERATOR_KEY} + Left Click").grid(
                row=3, column=1, sticky="e"
            )

            ttk.Label(viewport, text="").grid(row=4, column=0, sticky="w")

            ttk.Label(viewport, text="Toggle Mask Mode").grid(row=5, column=0, sticky="w")
            ttk.Label(viewport, text=f"Keyboard: {KEYBIND_MASK}").grid(row=5, column=1, sticky="e")

            ttk.Label(viewport, text="Toggle Antialiasing").grid(row=6, column=0, sticky="w")
            ttk.Label(viewport, text=f"Keyboard: {KEYBIND_TOGGLE_AA}").grid(
                row=6, column=1, sticky="e"
            )

            general = ttk.Labelframe(self._controls_window, text="General", padding=8.0)
            general.columnconfigure(0, weight=1)
            general.columnconfigure(1, weight=1)

            ttk.Label(general, text="Start Scan").grid(row=0, column=0, sticky="w")
            ttk.Label(general, text=f"Keyboard: {KEYBIND_START_SCAN}").grid(
                row=0, column=1, sticky="e"
            )

            ttk.Label(general, text="Quit").grid(row=1, column=0, sticky="w")
            ttk.Label(general, text=f"Keyboard: {KEYBIND_QUIT}").grid(row=1, column=1, sticky="e")

            ttk.Label(general, text="Show Help").grid(row=2, column=0, sticky="w")
            ttk.Label(general, text=f"Keyboard: {KEYBIND_HELP}").grid(row=2, column=1, sticky="e")

            ttk.Label(general, text="Copy Scan Command").grid(row=3, column=0, sticky="w")
            ttk.Label(general, text=f"Keyboard: {KEYBIND_COPY_COMMAND}").grid(
                row=3, column=1, sticky="e"
            )

            regions.grid(row=0, sticky="nsew", padx=8.0, pady=8.0)
            viewport.grid(row=1, sticky="nsew", padx=8.0, pady=8.0)
            general.grid(row=2, sticky="nsew", padx=8.0, pady=8.0)

            self._controls_window.columnconfigure(0, weight=1)
            self._controls_window.rowconfigure(0, weight=1)
            self._controls_window.rowconfigure(1, weight=1)
            self._controls_window.rowconfigure(2, weight=1)
            self._controls_window.update()

        self._controls_window.deiconify()
        self._root.focus()

    def _adjust_downscale(self, amount: int, allow_resize=True):
        # scale is clamped to MIN_DOWNSCALE_FACTOR/MAX_DOWNSCALE_FACTOR.
        scale = self._scale + amount
        self._scale = min(MAX_DOWNSCALE_FACTOR, max(MIN_DOWNSCALE_FACTOR, scale))
        self._scale_widget.set(self._scale)
        self._rescale(allow_resize=allow_resize)

    def _prompt_save(self):
        """Save region data, prompting the user if a save path wasn't specified by command line."""
        if self._save():
            return
        save_path = tkinter.filedialog.asksaveasfilename(
            title=SAVE_TITLE,
            filetypes=[("Region File", "*.txt")],
            defaultextension=".txt",
            confirmoverwrite=True,
            parent=self._root,
        )
        if save_path:
            self._save(save_path)

    def prompt_save_on_scan(self, root: ty.Optional[tk.Widget] = None):
        """Saves any changes that weren't persisted, prompting the user if a path wasn't specified.
        Returns True if we should quit the program, False if we should not quit."""
        # Don't prompt user if changes are already saved.
        if self._persisted:
            return True
        # Don't prompt the user if they lanched the region editor from the CLI and already specified
        # a path to save the region data to.
        if self._save():
            return True
        should_save = tkinter.messagebox.askyesnocancel(
            title=PROMPT_TITLE,
            message=PROMPT_MESSAGE,
            icon=tkinter.messagebox.WARNING,
            parent=root if root else self._root,
        )
        if should_save is None:
            return False
        if should_save and not self._save():
            save_path = tkinter.filedialog.asksaveasfilename(
                title=SAVE_TITLE,
                filetypes=[("Region File", "*.txt")],
                defaultextension=".txt",
                confirmoverwrite=True,
                parent=root if root else self._root,
            )
            if not save_path:
                return False
            self._save(save_path)
        else:
            logger.debug("Continuing with unsaved changes.")
        return True

    def _save(self, path=None):
        if path is None:
            if not self._settings.save_path:
                return False
            path = self._settings.save_path
        with open(path, "w") as region_file:
            for shape in self._regions:
                region_file.write(" ".join(f"{x} {y}" for x, y in shape))
                region_file.write("\n")
        logger.info("Saved region data to: %s", path)
        self._persisted = True
        self._persisted_path = path
        return True

    def _prompt_load(self):
        # TODO: Rename this function.
        if not self.prompt_save_on_scan():
            return
        load_path = tkinter.filedialog.askopenfilename(
            title=LOAD_TITLE,
            filetypes=[("Region File", "*.txt")],
            defaultextension=".txt",
            parent=self._root,
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
            logger.debug(
                "Loaded %d region%s from region file:\n%s",
                len(regions),
                "s" if len(regions) > 1 else "",
                "\n".join(f"[{i}] = {points}" for i, points in enumerate(regions)),
            )

            self._regions = [
                [bound_point(point, self._source_size) for point in shape] for shape in regions
            ]
            self._commit()
            self._persisted = True
            self._active_shape = 0 if len(self._regions) > 0 else None

    def _delete_point(self):
        if self._dragging or self._pan_enabled:
            logger.debug("Cannot remove point while dragging or panning.")
            return
        if self._hover_point is not None:
            if len(self.active_region) > MIN_NUM_POINTS:
                hover = self._hover_point
                x, y = self.active_region[hover]
                del self.active_region[hover]
                self._hover_point = None
                logger.debug("Del: [%d] = %s", hover, f"P({x},{y})")
                self._commit()
                self._draw()
            else:
                logger.debug("Region cannot have less than 3 points, removing shape.")
                self._delete_region()

    def _toggle_antialiasing(self):
        self._settings.use_aa = not self._settings.use_aa
        self._redraw = True
        logger.debug("AA: %s", "ON" if self._settings.use_aa else "OFF")
        if self._scale >= MAX_DOWNSCALE_AA_LEVEL:
            logger.warning("AA is disabled due to current scale factor.")
        self._draw()

    def _toggle_mask(self):
        self._settings.mask_source = not self._settings.mask_source
        logger.debug("Masking: %s", "ON" if self._settings.mask_source else "OFF")
        self._redraw = True
        self._draw()

    def _on_shape_select(self):
        if self._regions:
            self._select_region(self._region_selector.current())
        self._region_selector.selection_clear()

    def _add_point(self, drag: bool = False) -> bool:
        if self._nearest_points is not None:
            insert_pos = (
                1 + self._nearest_points[0]
                if self._nearest_points[0] < self._nearest_points[1]
                else self._nearest_points[1]
            )
            insert_pos = insert_pos % len(self.active_region)
            self.active_region.insert(insert_pos, self._curr_mouse_pos)
            logger.debug(
                f"Add: [{insert_pos}] = P({self._curr_mouse_pos.x},{self._curr_mouse_pos.y})"
            )
            self._nearest_points = None
            self._hover_point = insert_pos
            if drag:
                self._dragging = True
                self._drag_start = self._curr_mouse_pos
            self._redraw = True
            self._draw()
            return True
        return False

    def _recalculate_data(self):
        if self._log_stats:
            self._recalculates += 1
            logger.debug(f"recalculation {self._recalculates}")
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
        self._hover_point = self._find_hover_point()
        # Optimization: Only recalculate segment distances if we aren't hovering over a point.
        if self._hover_point is None:
            num_points = len(self.active_region)
            self._segment_dist = [
                squared_distance(self.active_region[i], self.active_region[(i + 1) % num_points])
                for i in range(num_points)
            ]
            self._find_nearest_segment()
        if last_hover != self._hover_point or last_nearest != self._nearest_points:
            self._redraw = True
        self._recalculate = False

    def _to_canvas_coordinates(self, point: Point) -> ty.Tuple[Point, bool]:
        """Adjust mouse coordinates to be relative to the editor canvas.

        Returns bounded point as well as a boolean if the cursor is in or outside of the canvas."""
        # TODO: We should disallow adding new points when the mouse is outside
        # of the canvas.
        x = int(self._editor_canvas.canvasx(point.x))
        y = int(self._editor_canvas.canvasy(point.y))
        inside_canvas = x >= 0 and y >= 0 and x <= self._frame_size.w and y <= self._frame_size.h
        bounded = bound_point(point=Point(x, y), size=self._frame_size)
        return Point(bounded.x * self._scale, bounded.y * self._scale), inside_canvas

    def _handle_mouse_input(self, event, point: Point):
        # TODO: Map mouse events to callbacks rather than handling each event conditionally.
        # TODO: Store `inside_canvas` so we can avoid highlighting/calculating when not necessary.
        self._curr_mouse_pos, inside_canvas = self._to_canvas_coordinates(point)
        if event == cv2.EVENT_LBUTTONDOWN:
            if self._pan_enabled:
                self._editor_canvas.scan_mark(point.x, point.y)
                self._panning = True
                self._drag_start = self._curr_mouse_pos
                # We can just return without redrawing, we only have to draw once the canvas moves.
                return
            if not inside_canvas:
                return

            if not self._regions:
                logger.info("No regions to edit, add a new one by right clicking.")
            if self._hover_point is not None:
                self._dragging = True
                self._drag_start = self._curr_mouse_pos
            else:
                self._add_point(drag=True)

        elif event == cv2.EVENT_MOUSEMOVE:
            if self._dragging:
                self.active_region[self._hover_point] = self._curr_mouse_pos
                self._recalculate = False
                self._redraw = True
            elif self._pan_enabled or self._panning:
                if self._panning:
                    self._editor_canvas.scan_dragto(point.x, point.y, gain=1)
            elif inside_canvas:
                # Need to recalculate to see what points are closest to current mouse pos.
                self._recalculate = True
            else:
                self._curr_mouse_pos = None
                self._hover_point = None
                self._nearest_points = None
                self._recalculate = True
                self._redraw = True

        elif event == cv2.EVENT_LBUTTONUP:
            if self._dragging:
                assert self._hover_point is not None
                if (
                    len(self.active_region) != len(self._history[self._history_pos].regions)
                    or self._curr_mouse_pos != self._drag_start
                ):
                    self.active_region[self._hover_point] = self._curr_mouse_pos
                    x, y = self.active_region[self._hover_point]
                    if self._curr_mouse_pos != self._drag_start:
                        logger.debug("Move: [%d] = %s", self._hover_point, f"P({x},{y})")
                    self._commit()
                self._redraw = True
            self._dragging = False
            self._panning = False
            self._set_cursor()  # Pan mode could have changed.

        self._draw()

    def _on_mouse_leave(self):
        logger.debug("mouse left window")
        if not (self._dragging or self._panning):
            self._curr_mouse_pos = None
            self._hover_point = None
            self._nearest_points = None
            self._redraw = True
            self._draw()

    def _cancel_active_action(self) -> bool:
        logger.debug("cancelling active action")
        if self._dragging:
            assert self._hover_point is not None
            snapshot = self._history[self._history_pos]
            self._regions[self._active_shape] = snapshot.regions[self._active_shape].copy()
            self._hover_point = None
            self._redraw = True

        self._dragging = False
        self._panning = False
        self._pan_enabled = False

        self._set_cursor()
        self._draw()

    def _bind_mouse(self):
        def on_mouse_move(e: tk.Event):
            self._handle_mouse_input(cv2.EVENT_MOUSEMOVE, Point(e.x, e.y))

        def on_left_mouse_down(e: tk.Event):
            if self._context_curr_mouse_pos is not None:
                self._context_curr_mouse_pos = None
                self._context_hover_point = None
                self._context_nearest_points = None
                self._context_menu.unpost()
                return
            self._handle_mouse_input(cv2.EVENT_LBUTTONDOWN, Point(e.x, e.y))

        def on_left_mouse_up(e: tk.Event):
            self._handle_mouse_input(cv2.EVENT_LBUTTONUP, Point(e.x, e.y))

        def on_zoom(e: tk.Event):
            increment = -1 if (e.num == 5 or e.delta > 0) else 1
            self._adjust_downscale(increment, allow_resize=False)

        self._context_menu = tk.Menu(self._root)

        self._context_menu.add_command(
            label="New Point",
            accelerator=KEYBIND_POINT_ADD,
            command=self._invoke_with_stashed_context(self._add_point),
        )
        self._context_menu.add_command(
            label="Delete Point",
            accelerator=KEYBIND_POINT_DELETE,
            command=self._invoke_with_stashed_context(self._delete_point),
        )
        self._context_menu.add_separator()
        self._context_menu.add_command(
            label="Next Region", accelerator=KEYBIND_REGION_NEXT, command=self._next_region
        )
        self._context_menu.add_command(
            label="Previous Region", accelerator=KEYBIND_REGION_PREVIOUS, command=self._prev_region
        )
        self._context_menu.add_separator()
        self._context_menu.add_command(
            label="New Region",
            accelerator=KEYBIND_REGION_ADD,
            command=self._invoke_with_stashed_context(self._add_region),
        )
        self._context_menu.add_command(
            label="Delete Region",
            accelerator=KEYBIND_REGION_DELETE,
            command=self._invoke_with_stashed_context(self._delete_region),
        )
        # TODO: Allow configuring mouse buttons.
        self._editor_canvas.bind("<Button-1>", on_left_mouse_down)
        self._editor_canvas.bind("<ButtonRelease-1>", on_left_mouse_up)
        # OSX uses mouse 2 but Windows/Linux use Mouse3.
        context_menu_button = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"
        self._editor_canvas.bind(context_menu_button, self._activate_context_menu)
        self._editor_canvas.bind("<Motion>", on_mouse_move)
        # Windows
        self._editor_canvas.bind("<Control-MouseWheel>", on_zoom)

        # Linux: Testing on Ubuntu shows scroll up/down as button clicks 4/5.
        # This will also capture these buttons on Windows.
        def on_scroll(up: bool):
            def scroll_handler(_: tk.Event):
                # On Linux we must have control held to scroll.
                if os.name != "nt" and not self._pan_enabled:
                    return
                self._adjust_downscale(-1 if up else 1, allow_resize=False)

            return scroll_handler

        self._editor_canvas.bind("<Button-4>", on_scroll(True))
        self._editor_canvas.bind("<Button-5>", on_scroll(False))

    def _invoke_with_stashed_context(self, f):
        def _invoke():
            self._curr_mouse_pos = self._context_curr_mouse_pos
            self._hover_point = self._context_hover_point
            self._nearest_points = self._context_nearest_points
            return f()

        return _invoke

    def _activate_context_menu(self, e: tk.Event):
        self._curr_mouse_pos, inside_canvas = self._to_canvas_coordinates(Point(e.x, e.y))
        if not inside_canvas:
            return
        self._recalculate_data()

        # Stash the state since sometimes we can interact with the canvas while the menu is posted.
        self._context_curr_mouse_pos = self._curr_mouse_pos
        self._context_hover_point = self._hover_point
        self._context_nearest_points = self._nearest_points

        # Update the menu state before posting.
        can_add_point = self._hover_point is None and self._nearest_points is not None
        self._context_menu.entryconfigure(
            "New Point", state=tk.ACTIVE if can_add_point else tk.DISABLED
        )
        can_delete_point = self._hover_point is not None
        self._context_menu.entryconfigure(
            "Delete Point", state=tk.ACTIVE if can_delete_point else tk.DISABLED
        )
        has_multiple_regions = len(self._regions) > 1
        self._context_menu.entryconfigure(
            "Next Region", state=tk.ACTIVE if has_multiple_regions else tk.DISABLED
        )
        self._context_menu.entryconfigure(
            "Previous Region", state=tk.ACTIVE if has_multiple_regions else tk.DISABLED
        )
        can_delete_region = len(self._regions) > 0
        self._context_menu.entryconfigure(
            "Delete Region", state=tk.ACTIVE if can_delete_region else tk.DISABLED
        )
        self._context_menu.post(e.x_root, e.y_root)

    def _on_pan(self):
        shift_x, shift_y = (
            (self._curr_mouse_pos.x - self._drag_start.x) / float(self._frame.shape[1]),
            (self._curr_mouse_pos.y - self._drag_start.y) / float(self._frame.shape[0]),
        )
        self._editor_canvas.xview_moveto(shift_x / self._scale)
        self._editor_canvas.yview_moveto(shift_y / self._scale)

    def _add_region(self):
        if self._dragging:
            return

        # Add a box around the current mouse position that's roughly 20% of the frame.
        width, height = (
            max(1, self._source_size.w // 10),
            max(1, self._source_size.h // 10),
        )

        top_left = Point(x=self._curr_mouse_pos.x - width, y=self._curr_mouse_pos.y - height)
        points = [
            top_left,
            Point(x=top_left.x + 2 * width, y=top_left.y),
            Point(x=top_left.x + 2 * width, y=top_left.y + 2 * height),
            Point(x=top_left.x, y=top_left.y + 2 * height),
        ]

        self._regions.append([bound_point(point, self._source_size) for point in points])
        self._active_shape = len(self._regions) - 1
        self._commit()
        self._recalculate = True
        self._redraw = True
        self._draw()

    def _delete_region(self):
        if self._dragging:
            return
        if self._regions:
            del self._regions[self._active_shape]
            self._active_shape = max(0, self._active_shape - 1)
            self._commit()
            self._recalculate = True
            self._redraw = True
            self._draw()

    def _select_region(self, index: int):
        logger.debug(f"selecting region {index}")
        if self._dragging:
            return
        assert index >= 0
        if self._regions and index < len(self._regions):
            self._active_shape = index
            self._region_selector.current(self._active_shape)
            self._recalculate = True
            self._redraw = True
            self._draw()

    def _next_region(self):
        if self._dragging:
            return
        if self._regions:
            self._active_shape = (self._active_shape + 1) % len(self._regions)
            self._region_selector.current(self._active_shape)
            self._recalculate = True
            self._redraw = True
            self._draw()

    def _prev_region(self):
        if self._dragging:
            return
        if self._regions:
            self._active_shape = (self._active_shape - 1) % len(self._regions)
            self._region_selector.current(self._active_shape)
            self._recalculate = True
            self._redraw = True
            self._draw()
