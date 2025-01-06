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
import tkinter.colorchooser as colorchooser
import tkinter.filedialog
import tkinter.ttk as ttk
import typing as ty
import webbrowser
from logging import getLogger
from pathlib import Path

from scenedetect import FrameTimecode

from dvr_scan.app.about_window import AboutWindow
from dvr_scan.app.common import register_icon
from dvr_scan.app.scan_window import ScanWindow
from dvr_scan.app.widgets import Spinbox, TimecodeEntry
from dvr_scan.config import CHOICE_MAP, CONFIG_MAP, RGBValue
from dvr_scan.scanner import DetectorType, OutputMode
from dvr_scan.shared import ScanSettings

WINDOW_TITLE = "DVR-Scan"
PADDING = 8
SETTING_INPUT_WIDTH = 12
LONG_SETTING_INPUT_WIDTH = 72
PATH_INPUT_WIDTH = 32
MAX_KERNEL_SIZE = 21
MAX_DURATION = 120.0
DURATION_INCREMENT = 0.1
DURATION_FORMAT = "%.1fs"
MIN_WINDOW_WIDTH = 128
MIN_WINDOW_HEIGHT = 128
LARGE_BUTTON_WIDTH = 40
MAX_THRESHOLD = 255.0
MAX_DOWNSCALE_FACTOR = 128

# TODO: Remove this and use the "debug" setting instead.
SUPPRESS_EXCEPTIONS = False

logger = getLogger("dvr_scan")

#
# TODO: This is ALL the controls that should be included in the initial release.
# Any additions or modifications can come in the future. Even overlay settings should
# be ignored for now and added later.
#
# Things that need unblocking for a beta release:
#
#   1. Map all existing UI controls to the DVR-Scan config types (in progress)
#   2. Figure out how to run the scan in the background and report the process
#      and status back. (done)
#   3. Handle the video input widget. (requires background task model already)
#      A lot of headaches can be solved if we take some time to validate the video,
#      and maybe generate some thumbnails or check other metadata, which could take
#      a few seconds when adding lots of videos. We can't block the UI for this long
#      so we already need to have a task model in place before this. (todo)
#
# At that point DVR-Scan should be ready for a beta release.
#


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
        root.columnconfigure(5, weight=12, minsize=0)

        self._videos = ttk.Treeview(root, columns=("duration", "path"))

        self._videos.heading("#0", text="Name")
        self._videos.heading("duration", text="Duration")
        self._videos.heading("path", text="Path")
        self._videos.grid(row=0, column=0, columnspan=6, sticky=tk.NSEW)

        ttk.Button(root, text="Add", state=tk.DISABLED).grid(
            row=1, column=0, sticky=tk.EW, padx=PADDING
        )
        ttk.Button(root, text="Remove", state=tk.DISABLED).grid(
            row=1, column=1, sticky=tk.EW, padx=PADDING
        )
        ttk.Button(root, text="Move Up", state=tk.DISABLED).grid(
            row=1, column=2, sticky=tk.EW, padx=PADDING
        )
        ttk.Button(root, text="Move Down", state=tk.DISABLED).grid(
            row=1, column=3, sticky=tk.EW, padx=PADDING
        )

        self._concatenate = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root,
            text="Concatenate",
            variable=self._concatenate,
            onvalue=True,
            offvalue=False,
            state=tk.DISABLED,
        ).grid(row=1, column=4, padx=PADDING, sticky=tk.EW)

        # TODO: Change default to value=False. Time is set by default for now for development.
        # TODO: Need to prevent start_time >= end_time.
        self._set_time = tk.BooleanVar(root, value=True)
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
        self._start_time = TimecodeEntry(root, value="00:00:00.000")
        self._start_time.grid(row=2, column=2, padx=PADDING, sticky=tk.EW)

        # HACK: Default set to 10 seconds for development. Also need to add some kind of hint that
        # a value of 0 means no end time is set.
        self._end_time_label = tk.Label(root, text="End Time", state=tk.DISABLED)
        self._end_time_label.grid(row=2, column=3, sticky=tk.EW)
        self._end_time = TimecodeEntry(root, "00:00:10.000")
        self._end_time.grid(row=2, column=4, padx=PADDING, sticky=tk.EW)

        self._use_region = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root,
            text="Use Regions",
            variable=self._use_region,
            onvalue=True,
            offvalue=False,
            command=self._on_use_regions,
            state=tk.DISABLED,
        ).grid(row=3, column=0, padx=PADDING, sticky=tk.W)
        self._region_editor = ttk.Button(root, text="Region Editor", state=tk.DISABLED)
        self._region_editor.grid(row=3, column=1, padx=PADDING, sticky=tk.EW)
        self._load_region_file = ttk.Button(root, text="Load Region File", state=tk.DISABLED)
        self._load_region_file.grid(row=3, column=2, padx=PADDING, sticky=tk.EW)
        self._current_region = tk.StringVar(value="No Region(s) Specified")
        tk.Entry(
            root, width=PATH_INPUT_WIDTH, state=tk.DISABLED, textvariable=self._current_region
        ).grid(row=3, column=3, sticky=tk.EW, padx=PADDING, columnspan=2)

        # Update internal state
        self._on_set_time()
        self._on_use_regions()

    def _on_set_time(self):
        state = tk.NORMAL if self._set_time.get() else tk.DISABLED
        self._start_time_label["state"] = state
        self._start_time["state"] = state
        self._end_time_label["state"] = state
        self._end_time["state"] = state

    def _on_use_regions(self):
        state = tk.NORMAL if self._use_region.get() else tk.DISABLED
        self._region_editor["state"] = state
        self._load_region_file["state"] = state

    @property
    def start_end_time(self) -> ty.Optional[ty.Tuple[str, str]]:
        if not self._set_time.get():
            return None
        return self._start_time.value, self._end_time.value


class SettingsArea:
    # TODO: make this less busy by making it a notebook widget that can also include the
    # output settings. Can also have an additional tab to load/save the various settings.
    def __init__(self, root: tk.Widget):
        self._root = root
        self._advanced = tk.Toplevel(master=root)
        self._advanced.withdraw()

        root.rowconfigure(0, pad=PADDING, weight=1)
        root.rowconfigure(1, pad=PADDING, weight=1)
        root.rowconfigure(2, pad=PADDING, weight=1)
        root.columnconfigure(0, pad=PADDING, weight=1)
        root.columnconfigure(1, pad=PADDING, weight=1)
        root.columnconfigure(2, pad=PADDING, weight=2)
        root.columnconfigure(3, pad=PADDING, weight=1)
        root.columnconfigure(4, pad=PADDING, weight=1)
        root.columnconfigure(5, pad=PADDING, weight=1)
        root.columnconfigure(6, pad=PADDING, weight=12, minsize=0)

        STICKY = tk.EW

        # Detector

        tk.Label(root, text="Subtractor").grid(row=0, column=0, sticky=STICKY)
        self._subtractor = tk.StringVar()
        combo = ttk.Combobox(root, textvariable=self._subtractor, width=SETTING_INPUT_WIDTH)
        combo["values"] = ("MOG2", "CNT")
        combo.state(["readonly"])
        self._subtractor.set("MOG2")
        combo.grid(row=0, column=1, sticky=STICKY)

        tk.Label(root, text="Kernel Size").grid(row=1, column=0, sticky=STICKY)

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
        self._kernel_size.grid(row=1, column=1, sticky=STICKY)
        self._kernel_size.current(1)

        tk.Label(root, text="Threshold").grid(row=2, column=0, sticky=STICKY)
        self._threshold = Spinbox(
            root,
            value=str(CONFIG_MAP["threshold"]),
            from_=0.0,
            to=255.0,
            width=SETTING_INPUT_WIDTH,
            increment=0.01,
            format="%g",
        )
        self._threshold.grid(row=2, column=1, sticky=STICKY)

        # Events

        tk.Label(root, text="Min. Event Length").grid(row=0, column=3, sticky=STICKY)
        self._min_event_len = Spinbox(root, value=str(CONFIG_MAP["min-event-length"]), suffix="s")
        self._min_event_len.grid(row=0, column=4, sticky=STICKY)

        tk.Label(root, text="Time Pre-Event").grid(row=1, column=3, sticky=STICKY)
        self._pre_event = Spinbox(root, value=str(CONFIG_MAP["time-before-event"]), suffix="s")
        self._pre_event.grid(row=1, column=4, sticky=STICKY)

        tk.Label(root, text="Time Post-Event").grid(row=2, column=3, sticky=STICKY)
        self._post_event = Spinbox(root, value=str(CONFIG_MAP["time-post-event"]), suffix="s")
        self._post_event.grid(row=2, column=4, sticky=STICKY)

        self._mask_output = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            root,
            text="Save Motion Mask",
            variable=self._mask_output,
            onvalue=True,
            offvalue=False,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=PADDING, pady=PADDING)

        # Processing

        self._advanced_button = ttk.Button(
            root, text="Advanced...", command=self._show_advanced, width=SETTING_INPUT_WIDTH
        )
        self._advanced_button.grid(
            row=3, column=3, columnspan=2, sticky=tk.EW, pady=PADDING, padx=PADDING
        )

        #
        #
        # Advanced Window
        #
        #
        self._advanced.minsize(width=MIN_WINDOW_WIDTH, height=MIN_WINDOW_HEIGHT)
        self._advanced.title("Motion Settings")
        self._advanced.resizable(True, True)
        self._advanced.protocol("WM_DELETE_WINDOW", self._dismiss_advanced)
        self._advanced.rowconfigure(0, weight=1)
        self._advanced.columnconfigure(0, weight=1)
        frame = ttk.LabelFrame(self._advanced, text="Advanced", padding=PADDING)
        frame.grid(row=0, sticky=tk.NSEW, padx=PADDING, pady=PADDING)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=2)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(4, weight=1)
        frame.columnconfigure(5, weight=2)
        frame.columnconfigure(6, weight=12)

        self._downscale = tk.StringVar(value=1)
        tk.Label(frame, text="Downscale Factor").grid(
            row=0, column=0, sticky=STICKY, padx=PADDING, pady=PADDING
        )
        self._downscale = Spinbox(
            frame,
            value=1,
            from_=1.0,
            to=float(MAX_DOWNSCALE_FACTOR),
            width=SETTING_INPUT_WIDTH,
            increment=1.0,
            format="%g",
            convert=lambda val: round(float(val)),
        )
        self._downscale.grid(row=0, column=1, sticky=STICKY, padx=PADDING, pady=PADDING)

        self._learning_rate_auto = tk.BooleanVar(value=True)
        tk.Label(frame, text="Learning Rate").grid(row=0, column=3, padx=PADDING, sticky=STICKY)
        self._learning_rate = Spinbox(
            frame,
            value=0.5,
            from_=0.0,
            to=1.0,
            width=SETTING_INPUT_WIDTH,
            increment=0.01,
            state=tk.DISABLED,
        )
        self._learning_rate.grid(row=0, column=4, padx=PADDING, sticky=STICKY, pady=PADDING)
        ttk.Checkbutton(
            frame,
            text="Auto",
            variable=self._learning_rate_auto,
            onvalue=True,
            offvalue=False,
            command=self._on_auto_learning_rate,
        ).grid(row=0, column=5, padx=PADDING, sticky=STICKY, pady=PADDING)

        tk.Label(frame, text="Max Threshold").grid(
            row=1, column=0, padx=PADDING, sticky=STICKY, pady=PADDING
        )
        self._max_threshold = Spinbox(
            frame,
            value=str(CONFIG_MAP["max-threshold"]),
            from_=0.0,
            to=MAX_THRESHOLD,
            width=SETTING_INPUT_WIDTH,
            increment=1.0,
        )
        self._max_threshold.grid(row=1, column=1, padx=PADDING, sticky=STICKY, pady=PADDING)

        tk.Label(frame, text="Variance Threshold").grid(
            row=1, column=3, padx=PADDING, sticky=STICKY, pady=PADDING
        )
        self._variance_threshold = Spinbox(
            frame,
            value=str(CONFIG_MAP["threshold"]),
            from_=0.0,
            to=255.0,
            width=SETTING_INPUT_WIDTH,
            increment=0.01,
        )
        self._variance_threshold.grid(row=1, column=4, padx=PADDING, sticky=STICKY, pady=PADDING)

        self._use_pts = tk.BooleanVar()
        ttk.Checkbutton(
            frame,
            text="Use Presentation Time\n(PTS) for Timestamps",
            variable=self._use_pts,
            onvalue=True,
            offvalue=False,
        ).grid(row=2, column=0, columnspan=2, padx=PADDING, sticky=STICKY, pady=PADDING)

        tk.Button(self._advanced, text="Close", command=self._dismiss_advanced).grid(
            row=1, column=0, sticky=tk.E, padx=PADDING, pady=PADDING
        )

        tk.Label(frame, text="Frame Skip").grid(
            row=2, column=3, padx=PADDING, sticky=tk.N + STICKY, pady=PADDING
        )
        self._frame_skip = Spinbox(
            frame,
            value=str(CONFIG_MAP["frame-skip"]),
            from_=0.0,
            to=1000.0,
            width=SETTING_INPUT_WIDTH,
            increment=1.0,
            format="%g",
        )
        self._frame_skip.grid(row=2, column=4, padx=PADDING, sticky=tk.N + STICKY, pady=PADDING)

    def _on_auto_learning_rate(self):
        self._learning_rate["state"] = tk.DISABLED if self._learning_rate_auto.get() else tk.NORMAL

    def _show_advanced(self):
        logger.debug("showing advanced settings window")
        self._advanced.transient(self._root)
        self._advanced.deiconify()
        self._advanced.focus()
        self._advanced.grab_set()
        self._advanced.wait_window()

    def _dismiss_advanced(self):
        logger.debug("closing advanced settings window")
        self._advanced.withdraw()
        self._advanced.grab_release()
        self._advanced_button.focus()

    @property
    def bg_subtractor(self) -> DetectorType:
        return self._subtractor.get()

    @bg_subtractor.setter
    def bg_subtractor(self, newval: str):
        self._subtractor.set(newval)

    @property
    def min_event_length(self) -> str:
        return self._min_event_len.value

    @min_event_length.setter
    def min_event_length(self, newval: str):
        self._min_event_len.value = newval

    @property
    def time_before_event(self) -> str:
        return self._pre_event.value

    @time_before_event.setter
    def time_before_event(self, newval: str):
        self._pre_event.value = newval

    @property
    def time_post_event(self) -> str:
        return self._post_event.value

    @time_post_event.setter
    def time_post_event(self, newval: str):
        self._post_event.value = newval

    @property
    def threshold(self) -> float:
        return float(self._threshold.value)

    @threshold.setter
    def threshold(self, newval: float):
        self._threshold.value = str(newval)

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
            logger.warning("Kernel sizes above 21 are not supported by the UI, clipping to 21.")
        kernel_size = min(size, MAX_KERNEL_SIZE)
        auto_kernel = bool(kernel_size < 0)
        none_kernel = bool(kernel_size == 0)
        index = 0 if none_kernel else 1 if auto_kernel else (1 + (kernel_size // 2))
        self._kernel_size.current(index)

    @property
    def mask_output(self) -> bool:
        return self._mask_output.get()

    @property
    def use_pts(self) -> bool:
        return self._use_pts.get()

    @use_pts.setter
    def use_pts(self, newval: bool):
        self._use_pts.set(newval)


class OutputArea:
    def __init__(self, root: tk.Widget):
        self._root = root
        self._last_value: ty.Optional[str] = None
        self._options_window = tk.Toplevel(master=root)
        self._options_window.withdraw()

        root.columnconfigure(0, pad=PADDING, weight=1)
        root.columnconfigure(1, pad=PADDING, weight=1)
        root.columnconfigure(2, pad=PADDING, weight=1)
        root.columnconfigure(3, pad=PADDING, weight=12)

        tk.Label(root, text="Mode").grid(
            row=0, column=0, sticky=tk.EW, padx=PADDING, pady=(0, PADDING)
        )
        self._mode_combo = ttk.Combobox(root, width=SETTING_INPUT_WIDTH, state="readonly")
        self._mode_combo.grid(row=0, column=1, sticky=tk.EW, padx=PADDING, pady=(0, PADDING))
        self._mode_combo.bind("<<ComboboxSelected>>", lambda _: self._on_mode_combo_selected())

        self._options_button = ttk.Button(
            root, text="Options...", command=self._show_options, width=SETTING_INPUT_WIDTH
        )
        self._options_button.grid(row=0, column=2, sticky=tk.EW, pady=(0, PADDING))

        self._mode_combo["values"] = (
            "OpenCV (.avi)",
            "ffmpeg",
            "ffmpeg (copy)",
        )
        self._mode_combo.current(1)

        self._output_dir = False
        self._output_dir_label = tk.StringVar(root, value="Ask Me")

        tk.Label(root, text="Directory").grid(
            row=1,
            column=0,
            sticky=tk.EW,
            pady=(PADDING, 0),
        )
        ttk.Entry(
            root, width=PATH_INPUT_WIDTH, state=tk.DISABLED, textvariable=self._output_dir_label
        ).grid(
            row=1,
            column=1,
            sticky=tk.EW,
            columnspan=3,
            pady=(PADDING, 0),
            padx=PADDING,
        )

        self._select_button = ttk.Button(root, text="Select...", command=self._on_select)
        self._select_button.grid(row=2, column=2, sticky=tk.EW, pady=(PADDING, 0))
        self._clear_button = ttk.Button(
            root, text="Clear", state=tk.DISABLED, command=self.clear_output_directory
        )
        self._clear_button.grid(row=2, column=1, sticky=tk.EW, padx=PADDING, pady=(PADDING, 0))

        STICKY = tk.EW

        #
        #
        # Advanced Window
        #
        #
        self._options_window.minsize(width=MIN_WINDOW_WIDTH, height=MIN_WINDOW_HEIGHT)
        self._options_window.title("Output Options")
        self._options_window.resizable(True, True)
        self._options_window.protocol("WM_DELETE_WINDOW", self._dismiss_options)
        self._options_window.rowconfigure(0, weight=1)
        self._options_window.rowconfigure(1, weight=1)
        self._options_window.columnconfigure(0, weight=1)

        self._ffmpeg_options = ttk.LabelFrame(
            self._options_window, text="ffmpeg Options", padding=PADDING
        )

        self._ffmpeg_options.columnconfigure(0, weight=2)
        self._ffmpeg_options.columnconfigure(1, weight=8)
        self._ffmpeg_options.columnconfigure(2, weight=1)

        self._ffmpeg_input_label = tk.Label(self._ffmpeg_options, text="ffmpeg\nInput Args")
        self._ffmpeg_input_label.grid(row=0, column=0, sticky=STICKY, padx=PADDING, pady=PADDING)
        self._ffmpeg_input = tk.StringVar(value=CONFIG_MAP["ffmpeg-input-args"])
        self._ffmpeg_input_entry = ttk.Entry(
            self._ffmpeg_options,
            textvariable=self._ffmpeg_input,
            width=LONG_SETTING_INPUT_WIDTH,
        )
        self._ffmpeg_input_entry.grid(row=0, column=1, sticky=STICKY, padx=PADDING, pady=PADDING)

        self._ffmpeg_output_label = tk.Label(self._ffmpeg_options, text="ffmpeg\nOutput Args")
        self._ffmpeg_output_label.grid(row=1, column=0, sticky=STICKY, padx=PADDING, pady=PADDING)
        self._ffmpeg_output = tk.StringVar(value=CONFIG_MAP["ffmpeg-output-args"])
        self._ffmpeg_output_entry = ttk.Entry(
            self._ffmpeg_options,
            textvariable=self._ffmpeg_output,
            width=LONG_SETTING_INPUT_WIDTH,
        )
        self._ffmpeg_output_entry.grid(row=1, column=1, sticky=STICKY, padx=PADDING, pady=PADDING)

        tk.Button(self._options_window, text="Close", command=self._dismiss_options).grid(
            row=2, column=0, sticky=tk.E, padx=PADDING, pady=PADDING
        )

        self._opencv_options = ttk.LabelFrame(
            self._options_window, text="OpenCV Options", padding=PADDING
        )

        self._opencv_options.columnconfigure(0, weight=1)
        self._opencv_options.columnconfigure(1, weight=1)
        self._opencv_options.columnconfigure(2, weight=1)
        self._opencv_options.columnconfigure(3, weight=1)
        self._opencv_options.columnconfigure(4, weight=1)
        self._opencv_options.columnconfigure(5, weight=12)

        self._opencv_codec_label = tk.Label(self._opencv_options, text="Codec")
        self._opencv_codec_label.grid(row=0, column=0, sticky=STICKY, padx=PADDING, pady=PADDING)
        self._opencv_codec = tk.StringVar(value=CONFIG_MAP["opencv-codec"])
        self._opencv_codec_combo = ttk.Combobox(
            self._opencv_options,
            width=SETTING_INPUT_WIDTH,
            state="readonly",
            textvariable=self._opencv_codec,
        )
        self._opencv_codec_combo["values"] = CHOICE_MAP["opencv-codec"]
        self._opencv_codec_combo.grid(row=0, column=1, sticky=tk.W, padx=PADDING, pady=PADDING)

        self._timecode = tk.BooleanVar(value=False)
        self._timecode_checkbutton = ttk.Checkbutton(
            self._opencv_options,
            text="Timecode",
            variable=self._timecode,
            onvalue=True,
            offvalue=False,
            command=self._on_text_overlay,
        )
        self._timecode_checkbutton.grid(
            row=1, column=0, columnspan=2, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )

        self._frame_metrics = tk.BooleanVar(value=False)
        self._frame_metrics_checkbutton = ttk.Checkbutton(
            self._opencv_options,
            text="Frame Metrics",
            variable=self._frame_metrics,
            onvalue=True,
            offvalue=False,
            command=self._on_text_overlay,
        )
        self._frame_metrics_checkbutton.grid(
            row=1, column=1, sticky=tk.W, padx=PADDING, pady=(PADDING, 0)
        )

        tk.Label(self._opencv_options, text="Font Scale").grid(
            row=2, column=0, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._text_font_scale = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["text-font-scale"]),
            from_=0.0,
            to=1000.0,
            width=SETTING_INPUT_WIDTH,
            increment=0.1,
            format="%g",
        )
        self._text_font_scale.grid(row=2, column=1, sticky=STICKY, padx=PADDING, pady=(PADDING, 0))

        tk.Label(self._opencv_options, text="Font Weight").grid(
            row=2, column=2, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._text_font_thickness = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["text-font-thickness"]),
            from_=0.0,
            to=1000.0,
            width=SETTING_INPUT_WIDTH,
            increment=1.0,
            format="%g",
            convert=lambda val: round(float(val)),
        )
        self._text_font_thickness.grid(
            row=2, column=3, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )

        tk.Label(self._opencv_options, text="Text Border").grid(row=3, column=0, sticky=STICKY)
        # TODO: Constrain to be <= text margin
        self._text_border = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["text-border"]),
            from_=0.0,
            to=1000.0,
            width=SETTING_INPUT_WIDTH,
            increment=1.0,
            format="%g",
            convert=lambda val: round(float(val)),
        )
        self._text_border.grid(row=3, column=1, sticky=STICKY, padx=PADDING, pady=PADDING)

        tk.Label(self._opencv_options, text="Text Margin").grid(
            row=3, column=2, sticky=STICKY, padx=PADDING, pady=PADDING
        )
        self._text_margin = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["text-margin"]),
            from_=0.0,
            to=1000.0,
            width=SETTING_INPUT_WIDTH,
            increment=1.0,
            format="%g",
            convert=lambda val: round(float(val)),
        )
        self._text_margin.grid(row=3, column=3, sticky=STICKY, padx=PADDING, pady=PADDING)

        self._bounding_box = tk.BooleanVar(value=False)
        self._bounding_box_button = ttk.Checkbutton(
            self._opencv_options,
            text="Bounding Box",
            variable=self._bounding_box,
            onvalue=True,
            offvalue=False,
            command=self._on_bounding_box,
        )
        self._bounding_box_button.grid(
            row=4, column=0, columnspan=2, sticky=STICKY, padx=PADDING, pady=(2 * PADDING, 0)
        )

        tk.Label(self._opencv_options, text="Line Color").grid(
            row=5, column=0, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        frame = tk.Frame(self._opencv_options)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)
        self._color_label = tk.Label(frame, bg="#FF0000", width=2)
        self._color_label.grid(row=0, column=0, sticky=STICKY, padx=PADDING, pady=(PADDING, 0))

        def on_color():
            color = colorchooser.askcolor()
            if color and color[1]:
                self._color_label["bg"] = color[1]

        self._color_button = tk.Button(frame, text="Set Color", command=on_color)
        self._color_button.grid(row=0, column=1, sticky=STICKY, padx=PADDING, pady=(PADDING, 0))
        frame.grid(row=5, column=1, sticky=tk.NSEW)

        tk.Label(self._opencv_options, text="Line Thickness").grid(
            row=5, column=2, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._bounding_box_thickness = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["bounding-box-thickness"]),
            from_=0.0,
            to=1.0,
            width=SETTING_INPUT_WIDTH,
            increment=0.001,
            format="%g",
        )
        self._bounding_box_thickness.grid(
            row=5, column=3, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )

        tk.Label(self._opencv_options, text="Smooth Time").grid(
            row=6, column=0, sticky=STICKY, padx=PADDING, pady=PADDING
        )
        self._bounding_box_smooth_time = Spinbox(
            self._opencv_options, str(CONFIG_MAP["bounding-box-smooth-time"]), suffix="s"
        )
        self._bounding_box_smooth_time.grid(
            row=6, column=1, sticky=STICKY, padx=PADDING, pady=PADDING
        )

        tk.Label(self._opencv_options, text="Min. Box Size").grid(
            row=6, column=2, sticky=STICKY, padx=PADDING, pady=PADDING
        )
        self._bounding_box_min_size = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["bounding-box-min-size"]),
            from_=0.0,
            to=1.0,
            width=SETTING_INPUT_WIDTH,
            increment=0.001,
            format="%g",
        )
        self._bounding_box_min_size.grid(row=6, column=3, sticky=STICKY, padx=PADDING, pady=PADDING)

        self._on_text_overlay()
        self._on_bounding_box()
        self._on_mode_combo_selected()

    def _on_duration_focus_in(self, var: tk.StringVar):
        def callback(_: tk.Event):
            self._last_value = var.get()

        return callback

    def _validate_duration(self, var: tk.StringVar):
        def callback(_: tk.Event):
            validated = 0.0
            try:
                validated = float(var.get().removesuffix("s"))
            except ValueError:
                try:
                    validated = float(self._last_value.removesuffix("s"))
                except ValueError:
                    validated = 0.0
            var.set(DURATION_FORMAT % validated)
            self._on_duration_focus_in(var)(None)

        return callback

    def _show_options(self):
        if self.output_mode == OutputMode.OPENCV:
            self._opencv_options.grid(row=0, column=0, sticky=tk.NSEW, padx=PADDING, pady=PADDING)
            self._ffmpeg_options.grid_remove()
        else:
            self._ffmpeg_options.grid(row=0, sticky=tk.NSEW, padx=PADDING, pady=PADDING)
            self._opencv_options.grid_remove()

        self._on_text_overlay()
        self._on_bounding_box()
        self._options_window.transient(self._root)
        self._options_window.deiconify()
        self._options_window.focus()
        self._options_window.grab_set()
        self._options_window.wait_window()

    def _dismiss_options(self):
        self._options_window.withdraw()
        self._options_window.grab_release()
        self._options_button.focus()

    def _on_select(self):
        output_path = tkinter.filedialog.askdirectory(title="Set Output Directory", mustexist=True)
        if output_path:
            self._output_dir_label.set(output_path)
            self._output_dir = True
            self._clear_button["state"] = tk.NORMAL

    def clear_output_directory(self):
        self._output_dir_label.set("Ask Me")
        self._output_dir = ""
        self._clear_button["state"] = tk.DISABLED

    def _on_text_overlay(self):
        if self.output_mode != OutputMode.OPENCV:
            self._timecode_checkbutton["state"] = tk.DISABLED
            self._frame_metrics_checkbutton["state"] = tk.DISABLED
            self._text_border["state"] = tk.DISABLED
            self._text_font_scale["state"] = tk.DISABLED
            self._text_font_thickness["state"] = tk.DISABLED
            self._text_margin["state"] = tk.DISABLED
        else:
            self._timecode_checkbutton["state"] = tk.NORMAL
            self._frame_metrics_checkbutton["state"] = tk.NORMAL
            state = (
                tk.NORMAL if (self._frame_metrics.get() or self._timecode.get()) else tk.DISABLED
            )
            self._text_border["state"] = state
            self._text_font_scale["state"] = state
            self._text_font_thickness["state"] = state
            self._text_margin["state"] = state

    def _on_bounding_box(self):
        if self.output_mode != OutputMode.OPENCV:
            self._bounding_box_button["state"] = tk.DISABLED
            self._color_button["state"] = tk.DISABLED
            self._bounding_box_thickness["state"] = tk.DISABLED
            self._bounding_box_smooth_time["state"] = tk.DISABLED
            self._bounding_box_min_size["state"] = tk.DISABLED
        else:
            self._bounding_box_button["state"] = tk.NORMAL
            state = tk.NORMAL if self._bounding_box.get() else tk.DISABLED
            self._color_button["state"] = state
            self._bounding_box_thickness["state"] = state
            self._bounding_box_smooth_time["state"] = state
            self._bounding_box_min_size["state"] = state

    def _on_mode_combo_selected(self):
        self._options_button["state"] = (
            tk.DISABLED if self.output_mode == OutputMode.COPY else tk.NORMAL
        )

    @property
    def output_mode(self) -> OutputMode:
        index = self._mode_combo.current()
        if index == 0:
            return OutputMode.OPENCV
        elif index == 1:
            return OutputMode.FFMPEG
        else:
            return OutputMode.COPY

    @output_mode.setter
    def output_mode(self, newval: OutputMode):
        assert newval != OutputMode.SCAN_ONLY  # Scan only is a separate checkbox in the UI.
        if newval == OutputMode.OPENCV:
            self._mode_combo.current(0)
        elif newval == OutputMode.FFMPEG:
            self._mode_combo.current(1)
        elif newval == OutputMode.COPY:
            self._mode_combo.current(2)

    @property
    def output_dir(self) -> str:
        return self._output_dir

    @output_dir.setter
    def output_dir(self, newval: str):
        if newval:
            self._output_dir = newval
            self._output_dir_label.set(newval)
            self._clear_button["state"] = tk.NORMAL
        else:
            self.clear_output_directory()

    @property
    def ffmpeg_input_args(self) -> ty.Optional[str]:
        return self._ffmpeg_input.get()

    @ffmpeg_input_args.setter
    def ffmpeg_input_args(self, newval: ty.Optional[str]):
        self._ffmpeg_input.set(newval)

    @property
    def ffmpeg_output_args(self) -> str:
        return self._ffmpeg_output.get()

    @ffmpeg_output_args.setter
    def ffmpeg_output_args(self, newval: ty.Optional[str]):
        self._ffmpeg_output.set(newval)

    @property
    def opencv_codec(self) -> str:
        return self._opencv_codec.get()

    @opencv_codec.setter
    def opencv_codec(self, newval):
        self._opencv_codec.set(newval)

    @property
    def timecode(self) -> bool:
        return self._timecode.get()

    @timecode.setter
    def timecode(self, newval: bool):
        self._timecode.set(newval)

    @property
    def frame_metrics(self) -> bool:
        return self._frame_metrics.get()

    @frame_metrics.setter
    def frame_metrics(self, newval: bool):
        self._frame_metrics.set(newval)

    @property
    def bounding_box(self) -> bool:
        return self._bounding_box.get()

    @bounding_box.setter
    def bounding_box(self, newval: bool):
        self._bounding_box.set(newval)

    @property
    def bounding_box_smooth_time(self) -> str:
        val = self._bounding_box_smooth_time.value
        if not val.endswith("s"):
            val += "s"
        return val

    @bounding_box_smooth_time.setter
    def bounding_box_smooth_time(self, newval: str):
        self._bounding_box_smooth_time.value = newval

    @property
    def bounding_box_color(self) -> str:
        return self._color_label["bg"]

    @bounding_box_color.setter
    def bounding_box_color(self, newval: ty.Tuple[int, int, int]) -> str:
        color_code = (newval[0] << 16) + (newval[1] << 8) + newval[2]
        self._color_label["bg"] = f"#{str(RGBValue(color_code))[2:]}"


class ScanArea:
    def __init__(self, root: tk.Tk, frame: tk.Widget):
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)

        self._start_button = ttk.Button(
            frame,
            text="Start",
            command=lambda: root.event_generate("<<StartScan>>"),
            width=LARGE_BUTTON_WIDTH,
        )
        self._start_button.grid(
            row=0,
            column=0,
            sticky=tk.NSEW,
            ipady=PADDING,
            pady=(0, PADDING),
        )
        # TODO: Change default to value=False. Scan only is defaulted for testing.
        self._scan_only = tk.BooleanVar(frame, value=True)
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

    @property
    def scan_only(self) -> bool:
        return self._scan_only.get()

    @scan_only.setter
    def scan_only(self, newval: bool):
        self._scan_only.set(newval)


class Application:
    def run(self):
        logger.debug("starting main loop")
        self._root.deiconify()
        self._root.focus()
        self._root.mainloop()

    def __init__(self, settings: ScanSettings):
        self._root = tk.Tk()
        self._root.withdraw()
        self._settings: ScanSettings = None

        self._root.option_add("*tearOff", False)
        self._root.title(WINDOW_TITLE)
        register_icon(self._root)
        self._root.resizable(True, True)
        self._root.minsize(width=MIN_WINDOW_WIDTH, height=MIN_WINDOW_HEIGHT)
        self._root.columnconfigure(0, weight=1, pad=PADDING)
        self._root.rowconfigure(0, weight=1)

        self._create_menubar()

        input_frame = ttk.Labelframe(self._root, text="Input", padding=PADDING)
        self._input = InputArea(input_frame)
        input_frame.grid(row=0, sticky=tk.NSEW, padx=PADDING, pady=(PADDING, 0))

        settings_frame = ttk.Labelframe(self._root, text="Motion", padding=PADDING)
        self._settings_area = SettingsArea(settings_frame)
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

        if not SUPPRESS_EXCEPTIONS:

            def error_handler(*args):
                raise

            self._root.report_callback_exception = error_handler

        # Initialize UI state from config.
        self._set_from(settings)

    def _create_menubar(self):
        root_menu = tk.Menu(self._root)
        self._root["menu"] = root_menu

        file_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=file_menu, label="File", underline=0)

        file_menu.add_command(
            label="Start Scan",
            underline=1,
            command=lambda: self._root.event_generate("<<StartScan>>"),
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Quit",
            command=self._on_delete,
        )

        settings_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=settings_menu, label="Settings", underline=0, state=tk.DISABLED)
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
        help_menu.add_command(label="Debug Log", underline=0, state=tk.DISABLED)
        help_menu.add_separator()

        help_menu.add_command(
            label="About DVR-Scan",
            command=lambda: AboutWindow().show(root=self._root),
            underline=0,
        )

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

    def _start_new_scan(self):
        assert self._scan_window is None
        settings = self._get_scan_settings()
        if not settings:
            return

        logger.debug(f"ui settings:\n{settings.app_settings}")

        def on_scan_window_close():
            logger.debug("scan window closed, restoring focus")
            self._scan_window = None
            self._scan_area.enable()
            self._root.deiconify()
            self._root.focus()

        self._scan_window = ScanWindow(self._root, settings, on_scan_window_close, PADDING)
        self._scan_area.disable()
        self._scan_window.show()

    def _set_from(self, settings: ScanSettings):
        """Initialize UI from config file."""
        logger.debug("initializing UI state from settings")
        self._settings = settings

        # Scan Settings
        self._settings_area.kernel_size = self._settings.get("kernel-size")
        self._settings_area.bg_subtractor = self._settings.get("bg-subtractor")
        self._settings_area.threshold = self._settings.get("threshold")
        self._settings_area.min_event_length = self._settings.get("min-event-length")
        self._settings_area.time_before_event = self._settings.get("time-before-event")
        self._settings_area.time_post_event = self._settings.get("time-post-event")
        self._settings_area.use_pts = self._settings.get("use-pts")

        # Output Settings
        output_mode = OutputMode[self._settings.get("output-mode").upper()]
        if output_mode == OutputMode.SCAN_ONLY:
            self._scan_area.scan_only = True
        else:
            self._output_area.output_mode = output_mode
        output_dir = self._settings.get("output-dir")
        if output_dir:
            self._output_area.output_dir = output_dir
        self._output_area.ffmpeg_input_args = self._settings.get("ffmpeg-input-args")
        self._output_area.ffmpeg_output_args = self._settings.get("ffmpeg-output-args")
        self._output_area.opencv_codec = self._settings.get("opencv-codec")

        self._output_area.bounding_box = self._settings.get("bounding-box")
        self._output_area.timecode = self._settings.get("time-code")
        self._output_area.frame_metrics = self._settings.get("frame-metrics")
        self._output_area.bounding_box_smooth_time = self._settings.get("bounding-box-smooth-time")
        self._output_area.bounding_box_color = self._settings.get("bounding-box-color")

    def _get_scan_settings(self) -> ty.Optional[ScanSettings]:
        """Get current UI state as a new ScanSettings."""
        settings = copy.deepcopy(self._settings)

        # Input Area
        if self._input.start_end_time:
            (start, end) = self._input.start_end_time
            if start != "00:00:00.000":
                settings.set("start-time", start)
            if end != "00:00:00.000":
                settings.set("end-time", end)
            start_frame = FrameTimecode(start, 1000.0).get_frames()
            end_frame = FrameTimecode(end, 1000.0).get_frames()
            if end_frame and end_frame <= start_frame:
                # TODO: This should be validated by the input widget.
                logger.error("No frames to process (start time must be less than than end time)")
                return None

        # Settings Area
        settings.set("kernel-size", self._settings_area.kernel_size)
        settings.set("bg-subtractor", self._settings_area.bg_subtractor)
        settings.set("threshold", self._settings_area.threshold)
        settings.set("min-event-length", self._settings_area.min_event_length)
        settings.set("time-before-event", self._settings_area.time_before_event)
        settings.set("time-post-event", self._settings_area.time_post_event)
        settings.set("use-pts", self._settings_area.use_pts)

        # Output Area
        scan_only = self._scan_area.scan_only
        output_mode = self._output_area.output_mode
        settings.set("scan-only", scan_only)
        settings.set("output-mode", output_mode)

        if self._output_area.output_dir:
            settings.set("output-dir", self._output_area.output_dir)
        elif not scan_only or self._settings_area.mask_output:
            # We will create files, prompt the user for an output folder.
            output_dir = tkinter.filedialog.askdirectory(
                title="Set Output Directory", mustexist=True
            )
            if output_dir:
                settings.set("output-dir", output_dir)
            else:
                return None

        if output_mode == OutputMode.FFMPEG:
            settings.set("ffmpeg-input-args", self._output_area.ffmpeg_input_args)
            settings.set("ffmpeg-output-args", self._output_area.ffmpeg_output_args)
        elif output_mode == OutputMode.OPENCV:
            settings.set("opencv-codec", self._output_area.opencv_codec)
            settings.set("bounding-box", self._output_area.bounding_box)
            settings.set("time-code", self._output_area.timecode)
            settings.set("frame-metrics", self._output_area.frame_metrics)
            settings.set("bounding-box-smooth-time", self._output_area.bounding_box_smooth_time)
            settings.set("bounding-box-color", self._output_area.bounding_box_color)

        if self._settings_area.mask_output:
            logger.error("ERROR - TODO: Set output path for the output mask based on video name.")
            return None

        return settings
