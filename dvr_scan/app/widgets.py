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
import tkinter.filedialog
import tkinter.ttk as ttk
import typing as ty

from scenedetect import FrameTimecode

SETTING_INPUT_WIDTH = 12
LONG_SETTING_INPUT_WIDTH = 72
MAX_DURATION = 120.0
DURATION_INCREMENT = 0.1
DURATION_FORMAT = "%.1fs"
MIN_WINDOW_WIDTH = 128
MIN_WINDOW_HEIGHT = 128
LARGE_BUTTON_WIDTH = 40
MAX_THRESHOLD = 255.0


class TimecodeEntry:
    def __init__(
        self,
        root: tk.Widget,
        value: str,
        width: int = SETTING_INPUT_WIDTH,
    ):
        value = str(value)
        self._value = tk.StringVar(value=value)
        self._last_valid = value
        self._last_focus = value
        self._entry = ttk.Entry(
            root,
            textvariable=self._value,
            width=width,
            validate="all",
            validatecommand=(root.register(self._validate), "%P", "%V"),
        )
        self._entry.bind("<Return>", lambda _: self._refresh(clear_selection=True))
        self._entry.bind("<Escape>", lambda _: self._cancel())

        # Expose grid method from underlying widget
        self.grid = self._entry.grid

    def __setitem__(self, key, item):
        self._entry[key] = item

    def __getitem__(self, key):
        return self._entry[key]

    @property
    def value(self) -> str:
        return self._value.get()

    @value.setter
    def value(self, newval: str):
        self._value.set(newval)
        self._refresh(clear_selection=True)

    def _refresh(self, clear_selection=False):
        try:
            newval = self._value.get()

            if newval.isdigit():
                newval = float(newval)
            validated = FrameTimecode(newval, 1000.0).get_timecode()
            self._value.set(validated)
            self._last_valid = validated
            self._last_focus = validated
        except (TypeError, ValueError):
            self._value.set(self._last_valid)
        if clear_selection:
            self._entry.selection_clear()
            self._entry.icursor(0)

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


class Spinbox:
    def __init__(
        self,
        root: tk.Widget,
        value: str,
        from_: float = 0.0,
        to: float = MAX_DURATION,
        increment: float = DURATION_INCREMENT,
        width: int = SETTING_INPUT_WIDTH,
        format: str = "%g",
        suffix: ty.Optional[str] = None,
        convert: ty.Callable[[str], ty.Any] = float,
        **kwargs,
    ):
        self._value = tk.StringVar(value=value)
        self._format = format
        self._suffix = suffix
        if self._suffix:
            self._format += self._suffix
        self._last_valid = value
        self._last_focus = value
        self._from = from_
        self._to = to
        self._spinbox = ttk.Spinbox(
            root,
            from_=from_,
            to=to,
            increment=increment,
            textvariable=self._value,
            width=width,
            format=self._format,
            validate="all",
            validatecommand=(root.register(self._validate), "%P", "%V"),
            **kwargs,
        )
        self._spinbox.bind("<Return>", lambda _: self._refresh(clear_selection=True))
        self._spinbox.bind("<Escape>", lambda _: self._cancel())
        self._convert = convert

        # Expose grid method from underlying widget
        self.grid = self._spinbox.grid

    def __setitem__(self, key, item):
        self._spinbox[key] = item

    def __getitem__(self, key):
        return self._spinbox[key]

    def set(self, newval: str):
        self.value = newval

    def get(self) -> str:
        return self.value

    @property
    def value(self) -> str:
        return self._value.get()

    @value.setter
    def value(self, newval: str):
        self._value.set(newval)
        self._refresh(clear_selection=True)

    def _refresh(self, clear_selection=False):
        try:
            newval = self._value.get()
            if self._suffix:
                newval = newval.removesuffix(self._suffix)
            newval = max(self._from, min(self._to, self._convert(newval)))
            newval = self._format % newval
            self._value.set(newval)
            self._last_valid = newval
            self._last_focus = newval
        except ValueError:
            self._value.set(self._last_valid)
        if clear_selection:
            self._spinbox.selection_clear()
            self._spinbox.icursor(0)

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
