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

import copy
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
from dvr_scan.app.scan_window import ScanWindow
from dvr_scan.config import CONFIG_MAP
from dvr_scan.shared import ScanSettings

WINDOW_TITLE = "DVR-Scan"

logger = getLogger("dvr_scan")

#
# TODO: This is ALL the controls that should be included in the initial release.
# Any additions or modifications can come in the future. Even overlay settings should
# be ignored for now and added later.
#
# Things that need unblocking for a beta release:
#
#   1. Map all existing UI controls to the DVR-Scan config types
#   2. Figure out how to run the scan in the background and report the process
#      and status back.
#   3. Handle the video input widget. (requires background task model already)
#      A lot of headaches can be solved if we take some time to validate the video,
#      and maybe generate some thumbnails or check other metadata, which could take
#      a few seconds when adding lots of videos. We can't block the UI for this long
#      so we already need to have a task model in place before this.
#
# At that point DVR-Scan should be ready for a beta release.
#


PADDING = 8

SETTING_INPUT_WIDTH = 12
PATH_INPUT_WIDTH = 32
MAX_KERNEL_SIZE = 21


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
        root.rowconfigure(3, pad=PADDING)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.columnconfigure(3, weight=1)
        root.columnconfigure(4, weight=1)

        self._videos = ttk.Treeview(root, columns=("duration", "path"))

        self._videos.heading("#0", text="Name")
        self._videos.heading("duration", text="Duration")
        self._videos.heading("path", text="Path")
        self._videos.grid(row=0, column=0, columnspan=5, sticky=tk.NSEW)

        ttk.Button(root, text="Add", command=lambda: logger.error("Not Implemented")).grid(
            row=1, column=0, sticky=tk.EW, padx=PADDING
        )
        ttk.Button(root, text="Remove", command=lambda: logger.error("Not Implemented")).grid(
            row=1, column=1, sticky=tk.EW, padx=PADDING
        )
        ttk.Button(root, text="Move Up", command=lambda: logger.error("Not Implemented")).grid(
            row=1, column=2, sticky=tk.EW, padx=PADDING
        )
        ttk.Button(root, text="Move Down", command=lambda: logger.error("Not Implemented")).grid(
            row=1, column=3, sticky=tk.EW, padx=PADDING
        )

        self._concatenate = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root, text="Concatenate", variable=self._concatenate, onvalue=True, offvalue=False
        ).grid(row=1, column=4, padx=PADDING, sticky=tk.EW)

        self._set_time = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root,
            text="Set Time",
            variable=self._set_time,
            onvalue=True,
            offvalue=False,
            command=self._on_set_time,
        ).grid(row=2, column=0, padx=PADDING, sticky=tk.W)
        self._start_time_label = tk.Label(root, text="Start Time", state=tk.DISABLED)
        self._start_time_label.grid(row=2, column=1, sticky=tk.EW)
        self._start_time = tk.StringVar()
        self._start_time_spinbox = ttk.Spinbox(
            root,
            from_=0.0,
            to=1.0,
            textvariable=self._start_time,
            width=SETTING_INPUT_WIDTH,
            state=tk.DISABLED,
        )
        self._start_time.set("00:00:00.000")
        self._start_time_spinbox.grid(row=2, column=2, padx=PADDING, sticky=tk.EW)

        self._end_time_label = tk.Label(root, text="End Time", state=tk.DISABLED)
        self._end_time_label.grid(row=2, column=3, sticky=tk.EW)
        self._end_time = tk.StringVar()
        self._end_time_spinbox = ttk.Spinbox(
            root,
            from_=0.0,
            to=1.0,
            textvariable=self._end_time,
            width=SETTING_INPUT_WIDTH,
            state=tk.DISABLED,
        )
        self._end_time.set(str("00:00:00.000"))
        self._end_time_spinbox.grid(row=2, column=4, padx=PADDING, sticky=tk.EW)

        self._use_region = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root,
            text="Use Regions",
            variable=self._use_region,
            onvalue=True,
            offvalue=False,
            command=self._on_use_regions,
        ).grid(row=3, column=0, padx=PADDING, sticky=tk.W)
        self._region_editor = ttk.Button(root, text="Region Editor", state=tk.DISABLED)
        self._region_editor.grid(row=3, column=1, padx=PADDING, sticky=tk.EW)
        self._load_region_file = ttk.Button(root, text="Load Region File", state=tk.DISABLED)
        self._load_region_file.grid(row=3, column=2, padx=PADDING, sticky=tk.EW)
        self._current_region = tk.StringVar(value="No Region(s) Specified")
        tk.Entry(
            root, width=PATH_INPUT_WIDTH, state=tk.DISABLED, textvariable=self._current_region
        ).grid(row=3, column=3, sticky=tk.EW, padx=PADDING, columnspan=2)

    def _on_set_time(self):
        state = tk.NORMAL if self._set_time.get() else tk.DISABLED
        self._start_time_label["state"] = state
        self._start_time_spinbox["state"] = state
        self._end_time_label["state"] = state
        self._end_time_spinbox["state"] = state

    def _on_use_regions(self):
        state = tk.NORMAL if self._use_region.get() else tk.DISABLED
        self._region_editor["state"] = state
        self._load_region_file["state"] = state


class SettingsArea:
    # TODO: make this less busy by making it a notebook widget that can also include the
    # output settings. Can also have an additional tab to load/save the various settings.
    def __init__(self, root: tk.Widget, settings: ScanSettings):
        self._root = root

        root.rowconfigure(0, pad=PADDING, weight=1)
        root.rowconfigure(1, pad=PADDING, weight=1)
        root.rowconfigure(2, pad=PADDING, weight=1)
        root.columnconfigure(0, pad=PADDING, weight=1)
        root.columnconfigure(1, pad=PADDING, weight=1)
        root.columnconfigure(2, pad=PADDING, weight=1)
        root.columnconfigure(3, pad=PADDING, weight=1)
        root.columnconfigure(4, pad=PADDING, weight=1)
        root.columnconfigure(5, pad=PADDING, weight=1)

        sticky = tk.EW

        # Detector

        tk.Label(root, text="Subtractor").grid(row=0, column=0, sticky=sticky)
        self._subtractor = tk.StringVar()
        combo = ttk.Combobox(root, textvariable=self._subtractor, width=SETTING_INPUT_WIDTH)
        combo["values"] = ("MOG2", "CNT")
        combo.state(["readonly"])
        self._subtractor.set("MOG2")
        combo.grid(row=0, column=1, sticky=sticky)

        tk.Label(root, text="Kernel Size").grid(row=1, column=0, sticky=sticky)

        self._kernel_size = ttk.Combobox(root, width=SETTING_INPUT_WIDTH, state="readonly")
        # 0: Auto
        # 1: Off
        # 2: 3x3
        # 3: 5x5
        # 4: 7x7
        # 5: 9x9...
        self._kernel_size["values"] = (
            "Off",
            "Auto",
            *tuple(f"{n}x{n}" for n in range(3, MAX_KERNEL_SIZE + 1, 2)),
        )
        self._kernel_size.grid(row=1, column=1, sticky=sticky)
        self._kernel_size.current(1)

        tk.Label(root, text="Threshold").grid(row=2, column=0, sticky=sticky)
        self._threshold = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._threshold, width=SETTING_INPUT_WIDTH
        )
        self._threshold.set(str(CONFIG_MAP["threshold"]))
        spinbox.grid(row=2, column=1, sticky=tk.E)

        # Events

        tk.Label(root, text="Min. Event Duration").grid(row=0, column=2, sticky=sticky)
        self._min_duration = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._min_duration, width=SETTING_INPUT_WIDTH
        )
        self._min_duration.set(str(CONFIG_MAP["min-event-length"]))
        spinbox.grid(row=0, column=3, sticky=sticky)

        tk.Label(root, text="Time Pre-Event").grid(row=1, column=2, sticky=sticky)
        self._pre_event = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._pre_event, width=SETTING_INPUT_WIDTH
        )
        self._pre_event.set(str(CONFIG_MAP["time-before-event"]))
        spinbox.grid(row=1, column=3, sticky=sticky)

        tk.Label(root, text="Time Post-Event").grid(row=2, column=2, sticky=sticky)
        self._post_event = tk.StringVar()
        spinbox = ttk.Spinbox(
            root, from_=0.0, to=1.0, textvariable=self._post_event, width=SETTING_INPUT_WIDTH
        )
        self._post_event.set(str(CONFIG_MAP["time-post-event"]))
        spinbox.grid(row=2, column=3, sticky=sticky)

        # Processing

        tk.Label(root, text="Downscale").grid(row=0, column=4, sticky=sticky)
        spinbox = ttk.Spinbox(root, from_=1.0, to=16.0, width=SETTING_INPUT_WIDTH)
        spinbox.grid(row=0, column=5, sticky=sticky)

        tk.Label(root, text="Frame Skip").grid(row=1, column=4, sticky=sticky)
        spinbox = ttk.Spinbox(root, from_=1.0, to=16.0, width=SETTING_INPUT_WIDTH)
        spinbox.grid(row=1, column=5, sticky=sticky)
        self._concatenate = tk.BooleanVar(root, value=False)

        # TODO: Add a config file option that hides this value.
        self._default = tk.BooleanVar(root, value=True)
        self._default_button = ttk.Checkbutton(
            root,
            text="Default",
            variable=self._default,
            onvalue=True,
            offvalue=False,
            command=self._update_default_state,
        )
        self._default_button.grid(row=2, column=5, sticky=tk.E)

        self._update_default_state()

    @property
    def use_default(self) -> bool:
        return self._default.get()

    def _update_default_state(self):
        use_default = self._default.get()
        for child in self._root.winfo_children():
            child.configure(state=tk.DISABLED if use_default else tk.NORMAL)
        self._default_button["state"] = tk.NORMAL
        self._kernel_size["state"] = tk.DISABLED if use_default else "readonly"

    @property
    def kernel_size(self) -> int:
        index = self._kernel_size.current()
        if index == 0:
            return 0
        elif index == 1:
            return -1
        else:
            assert index > 0
            return (index * 2) - 1

    @kernel_size.setter
    def kernel_size(self, size):
        # TODO: Handle this discrepency properly, we're clipping the user config right now.
        if size > MAX_KERNEL_SIZE:
            logger.warning("Kernel sizes above 21 are not supported yet, clipping to 21.")
        kernel_size = min(size, MAX_KERNEL_SIZE)
        auto_kernel = bool(kernel_size < 0)
        none_kernel = bool(kernel_size == 0)
        index = 0 if none_kernel else 1 if auto_kernel else (1 + (kernel_size // 2))
        self._kernel_size.current(index)


class OutputArea:
    def __init__(self, root: tk.Widget):
        root.columnconfigure(3, pad=PADDING, weight=1)
        root.columnconfigure(2, pad=PADDING, weight=1)
        root.columnconfigure(1, pad=PADDING, weight=6)
        root.columnconfigure(0, pad=PADDING, weight=2)

        self._output_directory_selected = False
        self._output_directory = tk.StringVar(root, value="")

        tk.Label(root, text="Override Output Directory:").grid(
            row=0,
            column=0,
            columnspan=3,
            sticky=tk.W,
            padx=PADDING,
        )
        ttk.Entry(
            root, width=PATH_INPUT_WIDTH, state=tk.DISABLED, textvariable=self._output_directory
        ).grid(
            row=1,
            column=0,
            sticky=tk.EW,
            columnspan=2,
            padx=PADDING,
        )

        ttk.Button(root, text="Select...").grid(row=1, column=2, sticky=tk.EW, padx=PADDING)
        ttk.Button(root, text="Clear", state=tk.DISABLED).grid(
            row=1, column=3, sticky=tk.EW, padx=PADDING
        )

        self._concatenate = tk.BooleanVar(root, value=False)
        (
            ttk.Checkbutton(
                root,
                text="Concatenate Events",
                variable=self._concatenate,
                onvalue=True,
                offvalue=False,
            ).grid(row=2, column=2, sticky=tk.W, padx=PADDING, pady=(PADDING, 0), columnspan=2),
        )

        self._mask = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root, text="Save Motion Mask", variable=self._mask, onvalue=True, offvalue=False
        ).grid(row=3, column=2, sticky=tk.W, padx=PADDING, columnspan=2)

        # TODO: Implement this in a future release.
        ttk.Button(
            root,
            text="Overlays...",
        ).grid(row=2, rowspan=2, column=0, sticky=tk.NSEW, padx=PADDING)


class ScanArea:
    def __init__(self, root: tk.Tk, frame: tk.Widget):
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)

        self._start_button = ttk.Button(
            frame, text="Start", command=lambda: root.event_generate("<<StartScan>>")
        )
        self._start_button.grid(
            row=0,
            column=0,
            sticky=tk.NSEW,
            ipady=PADDING,
            pady=(0, PADDING),
        )
        self._scan_only = tk.BooleanVar(frame, value=False)
        self._scan_only_button = ttk.Checkbutton(
            frame,
            text="Scan Only",
            variable=self._scan_only,
            onvalue=True,
            offvalue=False,
        )
        self._scan_only_button.grid(row=1, column=0, sticky=tk.W)

    def disable(self):
        self._start_button["text"] = "Scanning..."
        self._start_button["state"] = tk.DISABLED
        self._scan_only_button["state"] = tk.DISABLED

    def enable(self):
        self._start_button["text"] = "Start"
        self._start_button["state"] = tk.NORMAL
        self._scan_only_button["state"] = tk.NORMAL


class Application:
    def __init__(self, settings: ScanSettings):
        self._root = tk.Tk()
        self._root.withdraw()
        self._settings: ScanSettings = None

        self._root.option_add("*tearOff", False)
        self._root.title(WINDOW_TITLE)
        register_icon(self._root)
        self._root.resizable(True, True)
        self._root.minsize(width=128, height=128)
        self._root.columnconfigure(0, weight=1, pad=PADDING)
        self._root.rowconfigure(0, weight=1, pad=PADDING)
        self._root.rowconfigure(1, pad=PADDING)
        self._root.rowconfigure(2, pad=PADDING)
        self._root.rowconfigure(3, pad=PADDING)

        self._create_menubar()

        input_frame = ttk.Labelframe(self._root, text="Input", padding=PADDING)
        self._input = InputArea(input_frame)
        input_frame.grid(row=0, sticky=tk.NSEW, padx=PADDING, pady=(PADDING, 0))

        settings_frame = ttk.Labelframe(self._root, text="Motion", padding=PADDING)
        self._settings_area = SettingsArea(settings_frame, settings)
        settings_frame.grid(row=1, sticky=tk.EW, padx=PADDING, pady=(PADDING, 0))

        output_frame = ttk.Labelframe(self._root, text="Output", padding=PADDING)
        self._output_area = OutputArea(output_frame)
        output_frame.grid(row=2, sticky=tk.EW, padx=PADDING, pady=(PADDING, 0))

        scan_frame = ttk.Labelframe(self._root, text="Scan", padding=PADDING)
        self._scan_area = ScanArea(self._root, scan_frame)
        scan_frame.grid(row=3, sticky=tk.EW, padx=PADDING, pady=PADDING)

        self._scan_window: ty.Optional[ScanWindow] = None
        self._root.bind("<<StartScan>>", lambda _: self._start_new_scan())
        self._root.protocol("WM_DELETE_WINDOW", self._on_delete)

        self._set_from(settings)

    def _set_from(self, settings: ScanSettings):
        """Initialize UI from config file."""
        logger.debug("initializing UI state from settings")
        self._settings = settings

        # Scan Area
        self._settings_area.kernel_size = self._settings.get("kernel-size")

    def get_scan_settings(self) -> ScanSettings:
        """Get current UI state as a new ScanSettings."""
        settings = copy.deepcopy(self._settings)

        # Scan Area
        if not self._settings_area.use_default:
            settings.set("kernel-size", self._settings_area.kernel_size)

        # HACK: Prevent output files.
        settings.set("output-mode", "scan_only")
        return settings

    def _start_new_scan(self):
        assert self._scan_window is None

        settings = self.get_scan_settings()

        def on_scan_window_close():
            logger.debug("scan window closed, removing window and restoring focus")
            self._scan_window = None
            self._scan_area.enable()
            self._root.deiconify()
            self._root.grab_set()
            self._root.focus()

        self._scan_window = ScanWindow(self._root, settings, on_scan_window_close)
        self._scan_area.disable()
        self._root.grab_release()
        self._scan_window.show()

    def _create_menubar(self):
        root_menu = tk.Menu(self._root)
        self._root["menu"] = root_menu

        file_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=file_menu, label="File", underline=0)

        file_menu.add_command(
            label="Start Scan",
            underline=1,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Quit",
            command=self._on_delete,
        )

        settings_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=settings_menu, label="Settings", underline=0)
        settings_menu.add_command(
            label="Load...",
            underline=1,
        )
        settings_menu.add_command(
            label="Save...",
        )
        settings_menu.add_command(
            label="Save Current as Default",
        )
        settings_menu.add_command(
            label="Reset",
            underline=1,
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="Reset Default",
        )

        help_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=help_menu, label="Help", underline=0)
        help_menu.add_command(
            label="Online Manual",
            command=lambda: webbrowser.open_new_tab("www.dvr-scan.com/guide"),
            underline=0,
        )
        help_menu.add_command(label="Debug Log", underline=0)
        help_menu.add_separator()

        help_menu.add_command(
            label="About DVR-Scan",
            command=lambda: AboutWindow().show(root=self._root),
            underline=0,
        )

    def run(self):
        logger.debug("starting main loop")
        self._root.deiconify()
        self._root.focus()
        self._root.grab_release()
        self._root.mainloop()

    def _on_delete(self):
        logger.debug("shutting down")
        if self._scan_window is not None:
            # NOTE: We do not actually wait here,
            logger.debug("waiting for worker threads")
            # Signal all active worker threads to start shutting down.
            self._root.event_generate("<<Shutdown>>")
            # Make sure they actually have stopped.
            self._root.after(0, lambda: self._scan_window.stop())
        self._root.after(0, lambda: self._root.destroy())
        self._root.withdraw()