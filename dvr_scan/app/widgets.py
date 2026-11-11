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

import tkinter as tk
import tkinter.colorchooser
import tkinter.ttk as ttk
import typing as ty

from scenedetect import FrameTimecode

from dvr_scan.app.common import PADDING, SETTING_INPUT_WIDTH
from dvr_scan.config import RGBValue


class ColorPicker:
    def __init__(
        self, root: tk.Widget, initial_color: str = "#FF0000", padding=PADDING, sticky=tk.EW
    ):
        self._frame = tk.Frame(root)
        self._frame.columnconfigure(0, weight=1)
        self._frame.columnconfigure(1, weight=1)
        self._frame.rowconfigure(0, weight=1)
        self._color = tk.Label(self._frame, bg=initial_color, width=2)
        self._color.grid(row=0, column=0, sticky=sticky, padx=(0, padding))

        def set_color():
            color = tkinter.colorchooser.askcolor(self._color["bg"])
            if color and color[1]:
                self._color["bg"] = color[1]

        self._set_button = tk.Button(self._frame, text="Set Color", command=set_color)
        self._set_button.grid(row=0, column=1, sticky=sticky, padx=(padding, 0))

        self.grid = self._frame.grid

    def __setitem__(self, key, item):
        self._set_button[key] = item

    def __getitem__(self, key):
        return self._set_button[key]

    def get(self) -> ty.Tuple[int, int, int]:
        return RGBValue(f"0x{self._color['bg'][1:]}").value

    def set(self, newval: ty.Tuple[int, int, int]):
        color_code = (newval[0] << 16) + (newval[1] << 8) + newval[2]
        self._color["bg"] = f"#{str(RGBValue(color_code))[2:]}"


class _ValidatedEntry:
    """Base for entry-like widgets whose text is normalized when Enter is pressed or focus
    leaves, and reverted to the value at focus-in on Escape. Subclasses create the Tk
    widget bound to `variable` (with `_validate` as its validatecommand) and implement
    `_normalize`, raising ValueError for text that cannot be normalized."""

    def __init__(self, widget: ttk.Widget, variable: tk.StringVar, value: str):
        self._widget = widget
        self._value = variable
        self._last_valid = value
        self._last_focus = value
        widget.bind("<Return>", lambda _: self._refresh(clear_selection=True))
        widget.bind("<Escape>", lambda _: self._cancel())
        # Expose grid method from underlying widget
        self.grid = widget.grid

    def _normalize(self, text: str) -> str:
        raise NotImplementedError

    def __setitem__(self, key, item):
        self._widget[key] = item

    def __getitem__(self, key):
        return self._widget[key]

    def get(self) -> str:
        self._refresh()
        return self._value.get()

    def set(self, newval: str):
        self._value.set(str(newval))
        self._refresh(clear_selection=True)

    def _refresh(self, clear_selection=False):
        try:
            validated = self._normalize(self._value.get())
            self._value.set(validated)
            self._last_valid = validated
            self._last_focus = validated
        except (TypeError, ValueError):
            self._value.set(self._last_valid)
        if clear_selection:
            self._widget.selection_clear()
            self._widget.icursor(0)

    def _cancel(self):
        self._value.set(self._last_focus)
        self._refresh(clear_selection=True)

    def _validate(self, newval: str, event: str):
        if event == "focusin":
            self._last_valid = newval
            self._last_focus = newval
        elif event == "focusout":
            self._refresh()
        return True


class TimecodeEntry(_ValidatedEntry):
    def __init__(
        self,
        root: tk.Widget,
        value: str,
        width: int = SETTING_INPUT_WIDTH,
    ):
        value = str(value)
        variable = tk.StringVar(value=value)
        entry = ttk.Entry(
            root,
            textvariable=variable,
            width=width,
            validate="all",
            validatecommand=(root.register(self._validate), "%P", "%V"),
        )
        super().__init__(entry, variable, value)
        self.grid_remove = entry.grid_remove

    def _normalize(self, text: str) -> str:
        value = float(text) if text.isdigit() else text
        # TODO: There's a bug here in PySceneDetect when there are more than 3 :'s.
        if isinstance(value, str) and value.count(":") >= 3:
            raise ValueError()
        return FrameTimecode(value, 1000.0).get_timecode()


class Spinbox(_ValidatedEntry):
    def __init__(
        self,
        root: tk.Widget,
        value: str,
        from_: float,
        to: float,
        increment: float,
        width: int = SETTING_INPUT_WIDTH,
        format: str = "%g",
        suffix: ty.Optional[str] = None,
        convert: ty.Callable[[str], ty.Any] = float,
        **kwargs,
    ):
        self._format = format
        self._suffix = suffix
        if self._suffix:
            self._format += self._suffix
        self._from = from_
        self._to = to
        self._convert = convert
        variable = tk.StringVar(value=value)
        spinbox = ttk.Spinbox(
            root,
            from_=from_,
            to=to,
            increment=increment,
            textvariable=variable,
            width=width,
            format=self._format,
            validate="all",
            validatecommand=(root.register(self._validate), "%P", "%V"),
            **kwargs,
        )
        super().__init__(spinbox, variable, value)

    def _normalize(self, text: str) -> str:
        if self._suffix:
            text = text.removesuffix(self._suffix)
        value = max(self._from, min(self._to, self._convert(text)))
        return self._format % value
