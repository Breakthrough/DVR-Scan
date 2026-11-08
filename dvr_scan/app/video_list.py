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

"""Custom scrollable video list used by the Scan Wizard.

Unlike the classic `InputArea` (a `ttk.Treeview` with columns), each row here shows the
filmstrip preview on the left with the file's metadata stacked beside it:

    [     ][ Filename ]
    [ img ][ Duration   Date ]
    [     ][ Resolution   FPS ]

A Treeview renders one line of text per cell, so this layout requires laying out real
labels per row inside a scrollable canvas. A compact vertical icon toolbar (Add / Remove /
Up / Down / Sort) sits on the right so the up/down arrows point the way the selected row
moves. Sorting is also available via the wizard's File > Sort menu.

Rows support multi-selection like a standard list: click selects one row, Shift+click
extends a range from the last clicked row, and Ctrl+click (Command+click on macOS) toggles a
row. Clicking empty space clears the selection. Remove / Up / Down act on every selected row;
the wizard binds Ctrl+A (Select All) and Delete (Remove Selected) via `select_all` and
`remove_selected`.

The widget mirrors the subset of the `InputArea` API the wizard depends on (`videos`,
`add_video`, `update`, `sort_by`, `clear`) so it can be dropped in without changes to the
surrounding `ScanWizard` code."""

import dataclasses
import sys
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.ttk as ttk
import typing as ty
from logging import getLogger
from pathlib import Path

from dvr_scan.app.application import (
    PADDING,
    SORT_FIELDS,
    VideoInfo,
    probe_video,
    sample_video_frames,
)
from dvr_scan.app.thumbnails import (
    ThumbnailLoader,
    filmstrip_placeholder,
    to_photo,
)
from dvr_scan.shared import ScanSettings

logger = getLogger("dvr_scan")

# Toolbar button glyphs. Kept as `\N{...}` escapes so the source stays ASCII (see the
# project ASCII policy); all are BMP characters that render in the default Windows font.
ADD_GLYPH = "+"
REMOVE_GLYPH = "\N{MULTIPLICATION SIGN}"
UP_GLYPH = "\N{BLACK UP-POINTING TRIANGLE}"
DOWN_GLYPH = "\N{BLACK DOWN-POINTING TRIANGLE}"
SORT_GLYPH = "\N{UP DOWN ARROW}"

# Horizontal gap between the filmstrip and the stacked text, and vertical padding per row.
TEXT_PADX = 8
ROW_PADY = 2
# Width (in characters) of the square-ish icon toolbar buttons.
TOOLBAR_BUTTON_WIDTH = 3


@dataclasses.dataclass
class _Row:
    """One entry in the list: its metadata, the row frame, and the image label the
    thumbnail loader targets. `selectable` is every widget whose *background* tracks
    selection (frame + image + text); `text_labels` is the subset whose *foreground* also
    flips (the image label has no text), so the two lists overlap by design."""

    info: VideoInfo
    frame: tk.Frame
    image_label: tk.Label
    selectable: ty.List[tk.Widget]
    text_labels: ty.List[tk.Label]


class _Tooltip:
    """A minimal hover tooltip, used to label the icon-only toolbar buttons."""

    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text = text
        self._tip: ty.Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        # Tear down a visible tip if the button is destroyed while hovered.
        widget.bind("<Destroy>", self._hide, add="+")

    def _show(self, _event=None):
        if self._tip is not None or not self._widget.winfo_exists():
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 2
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._tip,
            text=self._text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            padx=4,
            pady=1,
        ).pack()

    def _hide(self, _event=None):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


class VideoList:
    """Scrollable list of input videos with stacked metadata rows and a vertical icon
    toolbar. Built into `root`, mirroring the `InputArea` API used by the Scan Wizard."""

    def __init__(self, root: tk.Widget):
        self._root = root
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        style = ttk.Style()
        self._bg = style.lookup("TFrame", "background") or "#f0f0f0"
        self._fg = style.lookup("TLabel", "foreground") or "black"
        self._select_bg = style.lookup("Treeview", "selectbackground") or "#0078d7"
        self._select_fg = style.lookup("Treeview", "selectforeground") or "#ffffff"

        # Scrollable region: a canvas hosting an inner frame that holds the row widgets.
        self._canvas = tk.Canvas(root, background=self._bg, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky=tk.NSEW)
        scroll = ttk.Scrollbar(root, orient=tk.VERTICAL, command=self._canvas.yview)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self._canvas.configure(yscrollcommand=scroll.set)

        self._rows_frame = tk.Frame(self._canvas, background=self._bg)
        self._window_id = self._canvas.create_window((0, 0), window=self._rows_frame, anchor=tk.NW)
        self._rows_frame.columnconfigure(0, weight=1)
        self._rows_frame.bind(
            "<Configure>",
            lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        # Keep the inner frame as wide as the canvas so rows fill the available width.
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfigure(self._window_id, width=e.width),
        )
        self._bind_mousewheel(self._canvas)
        self._bind_mousewheel(self._rows_frame)
        # Clicking empty space (not on a row) clears the selection. Row widgets are children
        # of the rows frame, but Tk delivers a click only to the widget under the pointer, so
        # these fire only for the uncovered area.
        self._canvas.bind("<Button-1>", self.clear_selection, add="+")
        self._rows_frame.bind("<Button-1>", self.clear_selection, add="+")

        # Vertical icon toolbar: Add / Remove / Up / Down then Sort, so the arrows point the
        # same direction the selected row moves.
        toolbar = ttk.Frame(root)
        toolbar.grid(row=0, column=2, sticky=tk.N, padx=(PADDING, 0))
        self._add_button = self._toolbar_button(toolbar, 0, ADD_GLYPH, "Add videos", self.add_video)
        self._remove_button = self._toolbar_button(
            toolbar, 1, REMOVE_GLYPH, "Remove selected (Del)", self.remove_selected
        )
        self._up_button = self._toolbar_button(toolbar, 2, UP_GLYPH, "Move up", self._on_move_up)
        self._down_button = self._toolbar_button(
            toolbar, 3, DOWN_GLYPH, "Move down", self._on_move_down
        )
        self._sort_button = self._toolbar_button(toolbar, 4, SORT_GLYPH, "Sort...", self._open_sort)
        self._sort_menu = self._build_sort_menu(toolbar)

        self._placeholder = to_photo(filmstrip_placeholder())
        self._thumbnails = ThumbnailLoader(self._canvas, apply_image=self._apply_thumbnail)
        self._rows: ty.Dict[str, _Row] = {}
        self._order: ty.List[str] = []
        # Selected row iids, and the anchor row (last plain-clicked or toggled) that Shift+click
        # extends a range from.
        self._selected: ty.Set[str] = set()
        self._anchor: ty.Optional[str] = None
        # Monotonic counter for unique row iids ("row-0", "row-1", ...). Never reset, even on
        # clear(), so a thumbnail job for a removed row can't collide with a reused iid.
        self._counter = 0
        self._refresh_button_state()

    def _toolbar_button(
        self, parent: tk.Widget, row: int, glyph: str, tip: str, command: ty.Callable[[], None]
    ) -> ttk.Button:
        button = ttk.Button(parent, text=glyph, width=TOOLBAR_BUTTON_WIDTH, command=command)
        button.grid(row=row, column=0, pady=(0, PADDING))
        _Tooltip(button, tip)
        return button

    def _bind_mousewheel(self, widget: tk.Widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    # --- Public API (mirrors the subset of InputArea used by the Scan Wizard) -------------

    @property
    def videos(self) -> ty.List[str]:
        return [self._rows[iid].info.path for iid in self._order]

    @property
    def selected_videos(self) -> ty.List[str]:
        """Paths of the selected videos, in display order."""
        return [self._rows[iid].info.path for iid in self._order if iid in self._selected]

    def select_all(self):
        """Select every row in the list."""
        self._selected = set(self._order)
        self._paint_selection()
        self._refresh_button_state()

    def clear_selection(self, _event=None):
        """Deselect all rows."""
        self._selected = set()
        self._paint_selection()
        self._refresh_button_state()

    def remove_selected(self):
        """Remove all selected rows, then select the row that fell into the top-most removed
        slot (if any) for quick repeated removal."""
        indices = self._selected_indices()
        if not indices:
            return
        lowest = indices[0]
        for iid in self._selected:
            self._rows.pop(iid).frame.destroy()
        self._order[:] = [iid for iid in self._order if iid not in self._selected]
        self._selected = set()
        self._anchor = None
        self._regrid()
        if self._order:
            # The auto-selected row also becomes the anchor so a following Shift+click
            # extends from it, as it would after a plain click.
            self._anchor = self._order[min(lowest, len(self._order) - 1)]
            self._selected = {self._anchor}
            self._paint_selection()
        self._refresh_button_state()

    def add_video(self, path: str = "", parent: ty.Optional[tk.Widget] = None):
        """Add a video to the list by path, or open a file dialog if no path is given.
        Called from the Add button, drag-and-drop, and the Scan Wizard."""
        if not path:
            dialog_options = {
                "title": "Open video(s)...",
                "filetypes": [("Video", "*.mp4"), ("Video", "*.avi"), ("Other", "*")],
                "multiple": True,
            }
            if parent is not None:
                dialog_options["parent"] = parent
            paths = tkinter.filedialog.askopenfilename(**dialog_options)
            if not paths:
                return
        else:
            paths = [path]
        failed_to_load = False
        for path in paths:
            if not Path(path).exists():
                logger.error(f"File does not exist: {path}")
                failed_to_load = True
                continue
            info = probe_video(path)
            if info is None:
                failed_to_load = True
                continue
            self._add_row(info)
        if failed_to_load:
            warning_options = {"parent": parent} if parent is not None else {}
            tkinter.messagebox.showwarning(
                "Video Open Failure", "Failed to open one or more videos.", **warning_options
            )
        self._refresh_button_state()

    def update(self, settings: ScanSettings) -> ty.Optional[ScanSettings]:
        videos = self.videos
        if not videos:
            return None
        settings.set("input", videos)
        return settings

    def sort_by(self, col: str, descending: bool):
        """Reorder the list by metadata field `col` (one of the SORT_FIELDS column ids:
        "#0" is the name, "date" is the creation date). Names sort case-insensitively;
        date strings (YYYY-MM-DD HH:MM:SS) sort lexicographically, which is chronological."""

        def key(iid: str) -> str:
            info = self._rows[iid].info
            if col == "#0":
                return info.name.casefold()
            if col == "date":
                return info.date
            raise ValueError(f"unknown sort column: {col!r}")

        self._order.sort(key=key, reverse=descending)
        self._regrid()

    def clear(self):
        """Remove all videos from the list."""
        for row in self._rows.values():
            row.frame.destroy()
        self._rows.clear()
        self._order.clear()
        self._selected = set()
        self._anchor = None
        # Drop pending thumbnail jobs so they don't target deleted rows, then start fresh.
        self._thumbnails.cancel()
        self._thumbnails = ThumbnailLoader(self._canvas, apply_image=self._apply_thumbnail)
        self._refresh_button_state()

    # --- Row construction and layout ------------------------------------------------------

    def _add_row(self, info: VideoInfo):
        iid = f"row-{self._counter}"
        self._counter += 1

        frame = tk.Frame(self._rows_frame, background=self._bg)
        frame.columnconfigure(1, weight=1)
        image_label = tk.Label(frame, image=self._placeholder, background=self._bg)
        image_label.grid(row=0, column=0, rowspan=3, sticky=tk.NW, padx=(0, TEXT_PADX))

        name_label = tk.Label(
            frame,
            text=info.name,
            background=self._bg,
            foreground=self._fg,
            anchor=tk.W,
            font=("TkDefaultFont", 9, "bold"),
        )
        detail_one = tk.Label(
            frame,
            text=f"{info.duration}    {info.date}",
            background=self._bg,
            foreground=self._fg,
            anchor=tk.W,
        )
        detail_two = tk.Label(
            frame,
            text=f"{info.resolution}    {info.framerate} FPS",
            background=self._bg,
            foreground=self._fg,
            anchor=tk.W,
        )
        name_label.grid(row=0, column=1, sticky=tk.EW)
        detail_one.grid(row=1, column=1, sticky=tk.EW)
        detail_two.grid(row=2, column=1, sticky=tk.EW)

        text_labels = [name_label, detail_one, detail_two]
        row = _Row(
            info=info,
            frame=frame,
            image_label=image_label,
            selectable=[frame, image_label, name_label, detail_one, detail_two],
            text_labels=text_labels,
        )
        for widget in row.selectable:
            widget.bind("<Button-1>", lambda _e, i=iid: self._on_click(i), add="+")
            widget.bind("<Shift-Button-1>", lambda _e, i=iid: self._on_shift_click(i), add="+")
            widget.bind("<Control-Button-1>", lambda _e, i=iid: self._on_toggle_click(i), add="+")
            if sys.platform == "darwin":
                widget.bind(
                    "<Command-Button-1>", lambda _e, i=iid: self._on_toggle_click(i), add="+"
                )
            self._bind_mousewheel(widget)

        self._rows[iid] = row
        self._order.append(iid)
        frame.grid(row=len(self._order) - 1, column=0, sticky=tk.EW, pady=ROW_PADY)
        self._thumbnails.submit(iid, lambda path=info.path: sample_video_frames(path))

    def _regrid(self):
        for index, iid in enumerate(self._order):
            self._rows[iid].frame.grid_configure(row=index)

    def _apply_thumbnail(self, iid: str, photo) -> bool:
        row = self._rows.get(iid)
        if row is None or not row.image_label.winfo_exists():
            return False
        row.image_label.configure(image=photo)
        return True

    # --- Selection and toolbar actions ----------------------------------------------------

    def _selected_indices(self) -> ty.List[int]:
        """Sorted display indices (into `_order`) of the selected rows."""
        return [index for index, iid in enumerate(self._order) if iid in self._selected]

    def _on_click(self, iid: str):
        """Plain click: select only this row and make it the range anchor."""
        self._selected = {iid}
        self._anchor = iid
        self._paint_selection()
        self._refresh_button_state()

    def _on_shift_click(self, iid: str):
        """Shift+click: select the inclusive range between the anchor and this row. The
        anchor is unchanged so the range can be adjusted with further Shift+clicks."""
        if self._anchor is None or self._anchor not in self._order:
            self._on_click(iid)
            return
        first, last = sorted((self._order.index(self._anchor), self._order.index(iid)))
        self._selected = set(self._order[first : last + 1])
        self._paint_selection()
        self._refresh_button_state()

    def _on_toggle_click(self, iid: str):
        """Ctrl+click (Command+click on macOS): toggle this row and make it the anchor."""
        if iid in self._selected:
            self._selected.discard(iid)
        else:
            self._selected.add(iid)
        self._anchor = iid
        self._paint_selection()
        self._refresh_button_state()

    def _paint_selection(self):
        """Recolor every row to reflect `_selected`."""
        for row_iid, row in self._rows.items():
            selected = row_iid in self._selected
            background = self._select_bg if selected else self._bg
            foreground = self._select_fg if selected else self._fg
            for widget in row.selectable:
                widget.configure(background=background)
            for label in row.text_labels:
                label.configure(foreground=foreground)

    def _on_move_up(self):
        """Move each selected row up one slot, preserving their relative order. No-op if
        the top-most selected row is already first."""
        indices = self._selected_indices()
        if not indices or indices[0] == 0:
            return
        # Ascending order: each row swaps into the slot just vacated (or held by an
        # unselected row), so contiguous blocks shift up together.
        for index in indices:
            self._order[index - 1], self._order[index] = (
                self._order[index],
                self._order[index - 1],
            )
        self._regrid()
        self._refresh_button_state()

    def _on_move_down(self):
        """Move each selected row down one slot, preserving their relative order. No-op if
        the bottom-most selected row is already last."""
        indices = self._selected_indices()
        if not indices or indices[-1] == len(self._order) - 1:
            return
        for index in reversed(indices):
            self._order[index + 1], self._order[index] = (
                self._order[index],
                self._order[index + 1],
            )
        self._regrid()
        self._refresh_button_state()

    def _open_sort(self):
        x = self._sort_button.winfo_rootx()
        y = self._sort_button.winfo_rooty() + self._sort_button.winfo_height()
        self._sort_menu.tk_popup(x, y)

    def _build_sort_menu(self, parent: tk.Widget) -> tk.Menu:
        """Build the Sort popup: a radio group of fields, then Ascending/Descending.
        Mirrors the wizard's File > Sort menu, reusing SORT_FIELDS."""
        self._sort_field = tk.StringVar(value=SORT_FIELDS[0][1])
        self._sort_descending = tk.BooleanVar(value=SORT_FIELDS[0][2])
        menu = tk.Menu(parent, tearoff=0)
        for label, column, _default in SORT_FIELDS:
            menu.add_radiobutton(
                label=label,
                variable=self._sort_field,
                value=column,
                command=lambda c=column: self._on_sort_field(c),
            )
        menu.add_separator()
        menu.add_radiobutton(
            label="Ascending",
            variable=self._sort_descending,
            value=False,
            command=self._apply_sort,
        )
        menu.add_radiobutton(
            label="Descending",
            variable=self._sort_descending,
            value=True,
            command=self._apply_sort,
        )
        return menu

    def _on_sort_field(self, column: str):
        # Switching field resets to that field's default direction (Name desc, Date asc).
        default_descending = next(desc for _label, col, desc in SORT_FIELDS if col == column)
        self._sort_descending.set(default_descending)
        self._apply_sort()

    def _apply_sort(self):
        self.sort_by(self._sort_field.get(), self._sort_descending.get())

    def _refresh_button_state(self):
        indices = self._selected_indices()
        self._remove_button["state"] = tk.NORMAL if indices else tk.DISABLED
        # Up/Down are only meaningful when there is somewhere to move the whole selection.
        can_move_up = bool(indices) and indices[0] > 0
        self._up_button["state"] = tk.NORMAL if can_move_up else tk.DISABLED
        can_move_down = bool(indices) and indices[-1] < len(self._order) - 1
        self._down_button["state"] = tk.NORMAL if can_move_down else tk.DISABLED
        self._sort_button["state"] = tk.NORMAL if self._order else tk.DISABLED
