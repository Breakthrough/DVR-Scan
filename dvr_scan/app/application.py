#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2014-2024 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#

import tkinter as tk
import tkinter.messagebox
import tkinter.scrolledtext
import tkinter.ttk as ttk
import typing as ty
import webbrowser
from logging import getLogger
from pathlib import Path

from dvr_scan.app.about_window import AboutWindow
from dvr_scan.app.common import register_icon
from dvr_scan.config import CONFIG_MAP

WINDOW_TITLE = "DVR-Scan"

logger = getLogger("dvr_scan")


PADDING = 8

SETTING_INPUT_WIDTH = 12
PATH_INPUT_WIDTH = 32


class InputArea:
    @property
    def concatenate(self) -> bool:
        return self._concatenate.get()

    @property
    def videos(self) -> ty.List[Path]:
        raise NotImplementedError()

    def __init__(self, root: tk.Widget):
        root.rowconfigure(0, pad=PADDING, weight=1)
        root.rowconfigure(1, pad=PADDING)
        root.rowconfigure(2, pad=PADDING)

        self._videos = ttk.Treeview(root, columns=("duration", "path"))

        self._videos.heading("#0", text="Name")
        self._videos.heading("duration", text="Duration")
        self._videos.heading("path", text="Path")
        self._videos.grid(row=0, column=0, columnspan=5, sticky=tk.NSEW)

        ttk.Button(root, text="Add", command=lambda: logger.error("Not Implemented")).grid(
            row=1, column=0
        )
        ttk.Button(root, text="Remove", command=lambda: logger.error("Not Implemented")).grid(
            row=1, column=1
        )
        ttk.Button(root, text="Move Up", command=lambda: logger.error("Not Implemented")).grid(
            row=1, column=2
        )
        ttk.Button(root, text="Move Down", command=lambda: logger.error("Not Implemented")).grid(
            row=1, column=3
        )

        self._concatenate = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root, text="Concatenate", variable=self._concatenate, onvalue=True, offvalue=False
        ).grid(row=1, column=4)

        tk.Label(root, text="Start Time").grid(row=2, column=0, sticky=tk.E)
        self._start_time = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._start_time, width=SETTING_INPUT_WIDTH
        )
        self._start_time.set("00:00:00.000")
        spinbox.grid(row=2, column=1, sticky=tk.E)

        tk.Label(root, text="End Time").grid(row=2, column=2, sticky=tk.E)
        self._end_time = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._end_time, width=SETTING_INPUT_WIDTH
        )
        self._end_time.set(str("00:00:00.000"))
        spinbox.grid(row=2, column=3, sticky=tk.E)


class SettingsArea:
    # TODO: make this less busy by making it a notebook widget that can also include the
    # output settings. Can also have an additional tab to load/save the various settings.
    def __init__(self, root: tk.Widget):
        root.columnconfigure(0, pad=PADDING, weight=1)
        root.columnconfigure(1, pad=PADDING, weight=1)
        root.columnconfigure(2, pad=PADDING, weight=1)
        root.columnconfigure(3, pad=PADDING, weight=1)
        root.columnconfigure(4, pad=PADDING, weight=1)
        root.columnconfigure(5, pad=PADDING, weight=1)

        # Detector

        tk.Label(root, text="Subtractor").grid(row=0, column=0, sticky=tk.E)
        self._subtractor = tk.StringVar()
        combo = ttk.Combobox(root, textvariable=self._subtractor, width=SETTING_INPUT_WIDTH)
        combo["values"] = ("MOG2", "CNT")
        combo.state(["readonly"])
        self._subtractor.set("MOG2")
        combo.grid(row=0, column=1, sticky=tk.E)

        tk.Label(root, text="Kernel Size").grid(row=1, column=0, sticky=tk.E)
        self._kernel_size = tk.StringVar()
        combo = ttk.Combobox(root, textvariable=self._kernel_size, width=SETTING_INPUT_WIDTH)
        combo["values"] = ("Auto", "Off", "3x3", "5x5", "7x7", "9x9")
        combo.state(["readonly"])  # TODO: Custom kernel sizes.
        combo.grid(row=1, column=1, sticky=tk.E)

        tk.Label(root, text="Threshold").grid(row=2, column=0, sticky=tk.E)
        self._threshold = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._threshold, width=SETTING_INPUT_WIDTH
        )
        self._threshold.set(str(CONFIG_MAP["threshold"]))
        spinbox.grid(row=2, column=1, sticky=tk.E)

        # Events

        tk.Label(root, text="Min. Event Duration").grid(row=0, column=2, sticky=tk.E)
        self._min_duration = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._min_duration, width=SETTING_INPUT_WIDTH
        )
        self._min_duration.set(str(CONFIG_MAP["min-event-length"]))
        spinbox.grid(row=0, column=3, sticky=tk.E)

        tk.Label(root, text="Time Pre-Event").grid(row=1, column=2, sticky=tk.E)
        self._pre_event = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._pre_event, width=SETTING_INPUT_WIDTH
        )
        self._pre_event.set(str(CONFIG_MAP["time-before-event"]))
        spinbox.grid(row=1, column=3, sticky=tk.E)

        tk.Label(root, text="Time Post-Event").grid(row=2, column=2, sticky=tk.E)
        self._post_event = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._post_event, width=SETTING_INPUT_WIDTH
        )
        self._post_event.set(str(CONFIG_MAP["time-post-event"]))
        spinbox.grid(row=2, column=3, sticky=tk.E)

        # Processing

        tk.Label(root, text="Regions").grid(row=0, column=4, sticky=tk.E)
        ttk.Button(root, text="Open Region Editor").grid(row=0, column=5, sticky=tk.E)

        tk.Label(root, text="Downscale").grid(row=1, column=4, sticky=tk.E)
        spinbox = ttk.Spinbox(root, from_=1.0, to=16.0, width=SETTING_INPUT_WIDTH)
        spinbox.grid(row=1, column=5, sticky=tk.E)

        tk.Label(root, text="Frame Skip").grid(row=2, column=4, sticky=tk.E)
        spinbox = ttk.Spinbox(root, from_=1.0, to=16.0, width=SETTING_INPUT_WIDTH)
        spinbox.grid(row=2, column=5, sticky=tk.E)


class OutputArea:
    def __init__(self, root: tk.Widget):
        root.columnconfigure(0, pad=PADDING, weight=1)
        root.columnconfigure(1, pad=PADDING, weight=1)
        root.columnconfigure(2, pad=PADDING, weight=1)
        root.columnconfigure(3, pad=PADDING, weight=1)

        tk.Label(root, text="Output Directory:").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(root, width=PATH_INPUT_WIDTH, state=tk.DISABLED).grid(
            row=1, column=0, sticky=tk.EW
        )
        ttk.Button(root, text="Set Output Directory").grid(row=2, column=0, sticky=tk.W)

        self._mask = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root, text="Save Motion Mask", variable=self._mask, onvalue=True, offvalue=False
        ).grid(row=0, column=2, sticky=tk.W)

        self._mask = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root, text="Concatenate", variable=self._mask, onvalue=True, offvalue=False
        ).grid(row=1, column=2, sticky=tk.W)

        pass


class ScanArea:
    def __init__(self, root: tk.Widget):
        root.columnconfigure(0, pad=PADDING, weight=1)
        root.columnconfigure(1, pad=PADDING, weight=1)
        root.columnconfigure(2, pad=PADDING, weight=1)
        root.columnconfigure(3, pad=PADDING, weight=1)

        ttk.Button(root, text="Start").grid(row=0, column=0)
        self._scan_only = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root, text="Scan Only", variable=self._scan_only, onvalue=True, offvalue=False
        ).grid(row=0, column=1)


class Application:
    def __init__(self):
        self._root = tk.Tk()
        self._root.withdraw()

        self._root.option_add("*tearOff", False)
        self._root.title(WINDOW_TITLE)
        register_icon(self._root)
        self._root.resizable(True, True)
        self._root.minsize(width=320, height=240)
        self._root.columnconfigure(0, weight=1, pad=PADDING)
        self._root.rowconfigure(0, weight=1, pad=PADDING)
        self._root.rowconfigure(1, pad=PADDING)
        self._root.rowconfigure(2, pad=PADDING)
        self._root.rowconfigure(3, pad=PADDING)

        self._create_menubar()

        input_frame = ttk.Labelframe(self._root, text="Input", padding=PADDING)
        self._input = InputArea(input_frame)
        input_frame.grid(row=0, sticky=tk.NSEW)

        settings_frame = ttk.Labelframe(self._root, text="Settings", padding=PADDING)
        self._settings = SettingsArea(settings_frame)
        settings_frame.grid(row=1, sticky=tk.W)

        output_frame = ttk.Labelframe(self._root, text="Output", padding=PADDING)
        self._output = OutputArea(output_frame)
        output_frame.grid(row=2, sticky=tk.EW)

        scan_frame = ttk.Labelframe(self._root, text="Scan", padding=PADDING)
        self._scan = ScanArea(scan_frame)
        scan_frame.grid(row=3, sticky=tk.EW)

    def _create_menubar(self):
        root_menu = tk.Menu(self._root)
        file_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=file_menu, label="File", underline=0)
        file_menu.add_command(
            label="Start Scan",
            underline=1,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Quit",
        )
        help_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=help_menu, label="Help", underline=0)
        help_menu.add_command(
            label="Online Manual",
            command=lambda: webbrowser.open_new_tab("www.dvr-scan.com/guide"),
            underline=0,
        )
        help_menu.add_separator()
        help_menu.add_command(
            label="About DVR-Scan", command=lambda: AboutWindow().show(root=self._root), underline=0
        )
        self._root["menu"] = root_menu

    def run(self):
        logger.debug("starting main loop")
        self._root.deiconify()
        self._root.focus()
        self._root.grab_release()
        self._root.mainloop()
