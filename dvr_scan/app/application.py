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
import tkinter.filedialog
import tkinter.messagebox
import tkinter.ttk as ttk
import typing as ty
import webbrowser
from logging import getLogger
from pathlib import Path

from scenedetect import FrameTimecode, open_video

from dvr_scan.app.about_window import AboutWindow
from dvr_scan.app.common import register_icon
from dvr_scan.app.region_editor import RegionEditor
from dvr_scan.app.scan_window import ScanWindow
from dvr_scan.app.widgets import ColorPicker, Spinbox, TimecodeEntry
from dvr_scan.config import CHOICE_MAP, CONFIG_MAP, ConfigLoadFailure, ConfigRegistry
from dvr_scan.scanner import OutputMode, Point
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
NO_REGIONS_SPECIFIED_TEXT = "No Region(s) Specified"

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


# TODO: Allow this to be sorted by columns.
# TODO: Should we have a default sort method when bulk adding videos?
class InputArea:
    def __init__(self, root: tk.Widget):
        self._root = root
        self._region_editor: ty.Optional[RegionEditor] = None
        root.rowconfigure(0, pad=PADDING, weight=1)
        root.rowconfigure(1, pad=PADDING)
        root.rowconfigure(2, pad=PADDING)
        root.rowconfigure(3, pad=PADDING)
        root.rowconfigure(4, pad=PADDING)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.columnconfigure(3, weight=1)
        root.columnconfigure(4, weight=1)
        root.columnconfigure(5, weight=1)
        root.columnconfigure(6, weight=12, minsize=0)

        frame = tk.Frame(root)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self._videos = ttk.Treeview(
            frame,
            columns=("duration", "framerate", "resolution", "path"),
        )

        scroll_horizontal = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self._videos.xview)
        scroll_vertical = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._videos.yview)
        scroll_horizontal.grid(row=1, column=0, columnspan=6, sticky="NEW")
        scroll_vertical.grid(row=0, column=6, rowspan=6, sticky="NSW")
        self._videos.configure(
            xscrollcommand=scroll_horizontal.set, yscrollcommand=scroll_vertical.set
        )

        self._videos.grid(row=0, column=0, sticky=tk.NSEW)
        frame.grid(row=0, column=0, rowspan=2, columnspan=6, sticky=tk.NSEW)

        self._videos.heading("#0", text="Name")
        self._videos.column("#0", width=180, minwidth=80, stretch=False)
        self._videos.heading("duration", text="Duration")
        self._videos.column("duration", width=80, minwidth=80, stretch=False)
        self._videos.heading("framerate", text="Framerate")
        self._videos.column("framerate", width=80, minwidth=80, stretch=False)
        self._videos.heading("resolution", text="Resolution")
        self._videos.column("resolution", width=80, minwidth=80, stretch=False)
        self._videos.heading("path", text="Path")
        self._videos.column("path", width=80, minwidth=80, stretch=False)

        self._videos.grid(row=0, column=0, columnspan=6, sticky=tk.NSEW)

        ttk.Button(root, text="Add", command=self._add_video).grid(
            row=2, column=0, sticky=tk.EW, padx=PADDING
        )
        self._remove_button = ttk.Button(
            root, text="Remove", state=tk.DISABLED, command=self._on_remove
        )
        self._remove_button.grid(row=2, column=1, sticky=tk.EW, padx=PADDING)
        ttk.Button(
            root,
            text="Move Up",
            command=self._on_move_up,
        ).grid(row=2, column=2, sticky=tk.EW, padx=PADDING)
        ttk.Button(
            root,
            text="Move Down",
            command=self._on_move_down,
        ).grid(row=2, column=3, sticky=tk.EW, padx=PADDING)

        self._concatenate = tk.BooleanVar(root, value=True)
        ttk.Checkbutton(
            root,
            text="Concatenate",
            variable=self._concatenate,
            onvalue=True,
            offvalue=False,
            command=self._on_set_time,
            state=tk.DISABLED,  # TODO: Enable when implemented.
        ).grid(row=2, column=4, padx=PADDING, sticky=tk.EW)

        # TODO: Need to prevent start_time >= end_time.
        self._set_time = tk.BooleanVar(root, value=False)
        self._set_time_button = ttk.Checkbutton(
            root,
            text="Set Time",
            variable=self._set_time,
            onvalue=True,
            offvalue=False,
            command=self._on_set_time,
        )
        self._set_time_button.grid(row=3, column=0, padx=PADDING, sticky=tk.W)
        self._start_time_label = tk.Label(root, text="Start Time", state=tk.DISABLED)
        self._start_time = TimecodeEntry(root, value="00:00:00.000")

        self._end_time_label = tk.Label(root, text="End Time", state=tk.DISABLED)
        self._end_time = TimecodeEntry(root, "00:00:00.000")

        self._set_region = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(
            root,
            text="Set Regions",
            variable=self._set_region,
            onvalue=True,
            offvalue=False,
            command=self._on_use_regions,
        ).grid(row=4, column=0, padx=PADDING, sticky=tk.W)
        self._region_editor_button = ttk.Button(
            root, text="Region Editor", state=tk.DISABLED, command=self._on_edit_regions
        )
        self._current_region = tk.StringVar(value=NO_REGIONS_SPECIFIED_TEXT)
        self._current_region_label = tk.Entry(
            root, width=PATH_INPUT_WIDTH, state=tk.DISABLED, textvariable=self._current_region
        )
        self._region_editor_button.grid(row=4, column=1, padx=PADDING, sticky=tk.EW)
        self._regions: ty.List[ty.List[Point]] = []
        self._current_region_label.grid(row=4, column=3, sticky=tk.EW, padx=PADDING, columnspan=2)

        # Update internal state
        self._on_set_time()
        self._on_use_regions()

    @property
    def videos(self) -> ty.List[str]:
        videos = []
        for item in self._videos.get_children():
            # TODO: File bug against PySceneDetect as we can't seem to use Path objects here.
            videos.append(self._videos.item(item)["values"][3])
        return videos

    def update(self, settings: ScanSettings) -> ty.Optional[ScanSettings]:
        videos = self.videos
        if not videos:
            return None
        settings.set("input", videos)
        if self.start_end_time:
            (start, end) = self.start_end_time
            if start != "00:00:00.000":
                settings.set("start-time", start)
            if end != "00:00:00.000":
                settings.set("end-time", end)
            start_frame = FrameTimecode(start, 1000.0).get_frames()
            end_frame = FrameTimecode(end, 1000.0).get_frames()
            if end_frame and end_frame <= start_frame:
                logger.error("No frames to process (start time must be less than than end time)")
                return None
        if self._set_region.get() and self._region_editor and self._region_editor.shapes:
            settings.set("regions", self._region_editor.shapes)
        return settings

    def _add_video(self, path: str = ""):
        if not path:
            paths = tkinter.filedialog.askopenfilename(
                title="Open video(s)...",
                # TODO: More extensions.
                filetypes=[("Video", "*.mp4"), ("Video", "*.avi"), ("Other", "*")],
                multiple=True,
            )
            if not paths:
                return
            for path in paths:
                if not Path(path).exists():
                    logger.error(f"File does not exist: {path}")
                    return
                # TODO: error handling
                video = open_video(path, backend="opencv")
                duration = video.duration.get_timecode()
                framerate = f"{video.frame_rate:g}"
                resolution = f"{video.frame_size[0]} x {video.frame_size[1]}"
                path = Path(video.path).absolute()
                self._videos.insert(
                    "",
                    tk.END,
                    text=video.name,
                    values=(duration, framerate, resolution, path),
                )
        self._remove_button["state"] = tk.NORMAL

    @property
    def concatenate(self) -> bool:
        return self._concatenate.get()

    def _on_remove(self):
        for selection in self._videos.selection():
            self._videos.delete(selection)

    def _on_move_up(self):
        for selection in self._videos.selection():
            index = self._videos.index(selection)
            if index > 0:
                self._videos.move(selection, "", index - 1)
            else:
                break

    def _on_move_down(self):
        for selection in self._videos.selection()[::-1]:
            index = self._videos.index(selection)
            next = self._videos.next(selection)
            if next:
                self._videos.move(next, "", index)
            else:
                break

    def _on_set_time(self):
        # TODO: When disabled, set start time 0 and end time duration of video.
        state = tk.NORMAL if self._set_time.get() else tk.DISABLED
        self._set_time_button["state"] = tk.NORMAL if self.concatenate else tk.DISABLED
        self._start_time_label["state"] = state
        self._start_time["state"] = state
        self._end_time_label["state"] = state
        self._end_time["state"] = state
        if state == tk.NORMAL and self.concatenate:
            self._start_time_label.grid(row=3, column=1, sticky=tk.EW)
            self._start_time.grid(row=3, column=2, padx=PADDING, sticky=tk.EW)
            self._end_time.grid(row=3, column=4, padx=PADDING, sticky=tk.EW)
            self._end_time_label.grid(row=3, column=3, sticky=tk.EW)
        else:
            self._start_time_label.grid_remove()
            self._start_time.grid_remove()
            self._end_time.grid_remove()
            self._end_time_label.grid_remove()

    def _on_use_regions(self):
        state = tk.NORMAL if self._set_region.get() else tk.DISABLED
        self._region_editor_button["state"] = state
        # self._load_region_file["state"] = tk.DISABLED #state

    def _on_edit_regions(self):
        videos = self.videos
        if videos:
            frame = open_video(videos[0], backend="opencv").read()
            if self._region_editor is None:
                self._region_editor = RegionEditor(
                    frame=frame,
                    initial_shapes=[],
                    initial_scale=None,
                    video_path=videos[0],
                    debug_mode=False,  # TODO: Wire up debug mode.
                    save_path=None,
                    on_close=self._on_region_editor_close,
                )
            self._region_editor.run(
                root=self._root,
            )
            self._region_editor._root.grab_set()

    def _on_region_editor_close(self):
        assert self._region_editor is not None
        self._regions = self._region_editor.shapes
        self._current_region.set(
            f"Using {len(self._regions)} regions." if self._regions else NO_REGIONS_SPECIFIED_TEXT
        )
        logger.debug(f"Regions updated: {self._regions}")

        self._region_editor._root.grab_release()
        self._root.focus()

    @property
    def start_end_time(self) -> ty.Optional[ty.Tuple[str, str]]:
        if not self._set_time.get():
            return None
        return self._start_time.get(), self._end_time.get()


class SettingsArea:
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
        self._bg_subtractor = tk.StringVar()
        combo = ttk.Combobox(root, textvariable=self._bg_subtractor, width=SETTING_INPUT_WIDTH)
        combo["values"] = ("MOG2", "CNT")
        combo.state(["readonly"])
        self._bg_subtractor.set("MOG2")
        combo.grid(row=0, column=1, sticky=STICKY)

        tk.Label(root, text="Kernel Size").grid(row=1, column=0, sticky=STICKY)

        self._kernel_size_combobox = ttk.Combobox(root, width=SETTING_INPUT_WIDTH, state="readonly")
        # 0: Auto
        # 1: Off
        # 2: 3x3
        # 3: 5x5
        # 4: 7x7
        # 5: 9x9...
        self._kernel_size_combobox["values"] = (
            "Off",
            "Auto",
            *tuple(f"{n}x{n}" for n in range(3, MAX_KERNEL_SIZE + 1, 2)),
        )
        self._kernel_size_combobox.grid(row=1, column=1, sticky=STICKY)
        self._kernel_size_combobox.current(1)

        tk.Label(root, text="Threshold").grid(row=2, column=0, sticky=STICKY)
        self._threshold = Spinbox(
            root,
            value=str(CONFIG_MAP["threshold"]),
            from_=0.0,
            to=255.0,
            increment=0.01,
        )
        self._threshold.grid(row=2, column=1, sticky=STICKY)

        # Events
        tk.Label(root, text="Min. Event Length").grid(row=0, column=3, sticky=STICKY)
        self._min_event_length = Spinbox(
            root,
            value=str(CONFIG_MAP["min-event-length"]),
            from_=0.0,
            to=MAX_DURATION,
            increment=DURATION_INCREMENT,
            suffix="s",
        )
        self._min_event_length.grid(row=0, column=4, sticky=STICKY)

        tk.Label(root, text="Time Pre-Event").grid(row=1, column=3, sticky=STICKY)
        self._time_before_event = Spinbox(
            root,
            value=str(CONFIG_MAP["time-before-event"]),
            from_=0.0,
            to=MAX_DURATION,
            increment=DURATION_INCREMENT,
            suffix="s",
        )
        self._time_before_event.grid(row=1, column=4, sticky=STICKY)

        tk.Label(root, text="Time Post-Event").grid(row=2, column=3, sticky=STICKY)
        self._time_post_event = Spinbox(
            root,
            value=str(CONFIG_MAP["time-post-event"]),
            from_=0.0,
            to=MAX_DURATION,
            increment=DURATION_INCREMENT,
            suffix="s",
        )
        self._time_post_event.grid(row=2, column=4, sticky=STICKY)

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

        self._downscale_factor = tk.StringVar(value=1)
        tk.Label(frame, text="Downscale Factor").grid(
            row=0, column=0, sticky=STICKY, padx=PADDING, pady=PADDING
        )
        self._downscale_factor = Spinbox(
            frame,
            value=float(CONFIG_MAP["downscale-factor"]),
            from_=0.0,
            to=float(MAX_DOWNSCALE_FACTOR),
            increment=1.0,
            convert=lambda val: round(float(val)),
        )
        self._downscale_factor.grid(row=0, column=1, sticky=STICKY, padx=PADDING, pady=PADDING)

        self._learning_rate_auto = tk.BooleanVar(value=True)
        tk.Label(frame, text="Learning Rate").grid(row=0, column=3, padx=PADDING, sticky=STICKY)
        self._learning_rate_value = Spinbox(
            frame,
            value=0.5,
            from_=0.0,
            to=1.0,
            increment=0.01,
            state=tk.DISABLED,
        )
        self._learning_rate_value.grid(row=0, column=4, padx=PADDING, sticky=STICKY, pady=PADDING)
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
            increment=1.0,
        )
        self._frame_skip.grid(row=2, column=4, padx=PADDING, sticky=tk.N + STICKY, pady=PADDING)

    def _on_auto_learning_rate(self):
        self._learning_rate_value["state"] = (
            tk.DISABLED if self._learning_rate_auto.get() else tk.NORMAL
        )

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
    def _kernel_size(self) -> int:
        index = self._kernel_size_combobox.current()
        if index == 0:
            return 0
        elif index == 1:
            return -1
        else:
            assert index > 0
            return (index * 2) - 1

    @_kernel_size.setter
    def _kernel_size(self, size):
        # TODO: Handle this discrepency properly, we're clipping the user config right now.
        if size > MAX_KERNEL_SIZE:
            logger.warning("Kernel sizes above 21 are not supported by the UI, clipping to 21.")
        kernel_size = min(size, MAX_KERNEL_SIZE)
        auto_kernel = bool(kernel_size < 0)
        none_kernel = bool(kernel_size == 0)
        index = 0 if none_kernel else 1 if auto_kernel else (1 + (kernel_size // 2))
        self._kernel_size_combobox.current(index)

    @property
    def _learning_rate(self) -> float:
        if self._learning_rate_auto.get():
            return CONFIG_MAP["learning-rate"]
        return self._learning_rate_value.get()

    @_learning_rate.setter
    def _learning_rate(self, newval: float):
        if newval < 0.0:
            self._learning_rate_auto.set(True)
        else:
            self._learning_rate_auto.set(False)
            self._learning_rate_value.set(newval)
        self._on_auto_learning_rate()

    def set(self, settings: ScanSettings):
        self._kernel_size = settings.get("kernel-size")
        self._learning_rate = settings.get("learning-rate")
        self._bg_subtractor.set(settings.get("bg-subtractor"))
        self._threshold.set(settings.get("threshold"))
        self._min_event_length.set(settings.get("min-event-length"))
        self._time_before_event.set(settings.get("time-before-event"))
        self._time_post_event.set(settings.get("time-post-event"))
        self._use_pts.set(settings.get("use-pts"))
        self._downscale_factor.set(settings.get("downscale-factor"))
        self._frame_skip.set(settings.get("frame-skip"))
        self._max_threshold.set(settings.get("max-threshold"))
        self._variance_threshold.set(settings.get("variance-threshold"))

    def update(self, settings: ScanSettings) -> ScanSettings:
        settings.set("kernel-size", self._kernel_size)
        settings.set("bg-subtractor", self._bg_subtractor.get())
        settings.set("threshold", float(self._threshold.get()))
        settings.set("min-event-length", self._min_event_length.get())
        settings.set("time-before-event", self._time_before_event.get())
        settings.set("time-post-event", self._time_post_event.get())
        settings.set("use-pts", self._use_pts.get())
        settings.set("downscale-factor", int(self._downscale_factor.get()))
        settings.set("learning-rate", float(self._learning_rate_value.get()))
        settings.set("max-threshold", float(self._max_threshold.get()))
        settings.set("variance-threshold", float(self._variance_threshold.get()))
        settings.set("frame-skip", int(self._frame_skip.get()))
        # NOTE: There is no mask-output in the get function above as it does not exist in the
        # config file (CLI only).
        settings.set("mask-output", self._mask_output.get())
        return settings


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
        self._output_mode_combo = ttk.Combobox(root, width=SETTING_INPUT_WIDTH, state="readonly")
        self._output_mode_combo.grid(row=0, column=1, sticky=tk.EW, padx=PADDING, pady=(0, PADDING))
        self._output_mode_combo.bind(
            "<<ComboboxSelected>>", lambda _: self._on_mode_combo_selected()
        )

        self._options_button = ttk.Button(
            root, text="Options...", command=self._show_options, width=SETTING_INPUT_WIDTH
        )
        self._options_button.grid(row=0, column=2, sticky=tk.EW, pady=(0, PADDING))

        self._output_mode_combo["values"] = (
            "OpenCV (.avi)",
            "ffmpeg",
            "ffmpeg (copy)",
        )
        self._output_mode_combo.current(1)

        self._output_dir_str = ""
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

        def clear_output_directory():
            self._output_dir = ""

        self._clear_button = ttk.Button(
            root, text="Clear", state=tk.DISABLED, command=clear_output_directory
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
        self._ffmpeg_input_args = tk.StringVar(value=CONFIG_MAP["ffmpeg-input-args"])
        self._ffmpeg_input_entry = ttk.Entry(
            self._ffmpeg_options,
            textvariable=self._ffmpeg_input_args,
            width=LONG_SETTING_INPUT_WIDTH,
        )
        self._ffmpeg_input_entry.grid(row=0, column=1, sticky=STICKY, padx=PADDING, pady=PADDING)

        self._ffmpeg_output_label = tk.Label(self._ffmpeg_options, text="ffmpeg\nOutput Args")
        self._ffmpeg_output_label.grid(row=1, column=0, sticky=STICKY, padx=PADDING, pady=PADDING)
        self._ffmpeg_output_args = tk.StringVar(value=CONFIG_MAP["ffmpeg-output-args"])
        self._ffmpeg_output_entry = ttk.Entry(
            self._ffmpeg_options,
            textvariable=self._ffmpeg_output_args,
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

        tk.Label(self._opencv_options, text="Text Color").grid(
            row=2, column=0, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._text_font_color = ColorPicker(self._opencv_options)
        self._text_font_color.grid(row=2, column=1, sticky=tk.NSEW, pady=(PADDING, 0), padx=PADDING)
        tk.Label(self._opencv_options, text="Background").grid(
            row=2, column=2, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._text_bg_color = ColorPicker(self._opencv_options)
        self._text_bg_color.grid(row=2, column=3, sticky=tk.NSEW, pady=(PADDING, 0), padx=PADDING)

        tk.Label(self._opencv_options, text="Font Scale").grid(
            row=3, column=0, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._text_font_scale = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["text-font-scale"]),
            from_=0.0,
            to=1000.0,
            increment=0.1,
        )
        self._text_font_scale.grid(row=3, column=1, sticky=STICKY, padx=PADDING, pady=(PADDING, 0))

        tk.Label(self._opencv_options, text="Font Weight").grid(
            row=3, column=2, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._text_font_thickness = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["text-font-thickness"]),
            from_=0.0,
            to=1000.0,
            increment=1.0,
            convert=lambda val: round(float(val)),
        )
        self._text_font_thickness.grid(
            row=3, column=3, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )

        tk.Label(self._opencv_options, text="Text Border").grid(row=4, column=0, sticky=STICKY)
        # TODO: Constrain to be <= text margin
        self._text_border = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["text-border"]),
            from_=0.0,
            to=1000.0,
            increment=1.0,
            convert=lambda val: round(float(val)),
        )
        self._text_border.grid(row=4, column=1, sticky=STICKY, padx=PADDING, pady=PADDING)

        tk.Label(self._opencv_options, text="Text Margin").grid(
            row=4, column=2, sticky=STICKY, padx=PADDING, pady=PADDING
        )
        self._text_margin = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["text-margin"]),
            from_=0.0,
            to=1000.0,
            increment=1.0,
            convert=lambda val: round(float(val)),
        )
        self._text_margin.grid(row=4, column=3, sticky=STICKY, padx=PADDING, pady=PADDING)

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
            row=5, column=0, columnspan=2, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )

        tk.Label(self._opencv_options, text="Line Color").grid(
            row=6, column=0, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._bounding_box_color = ColorPicker(self._opencv_options)
        self._bounding_box_color.grid(
            row=6, column=1, sticky=tk.NSEW, pady=(PADDING, 0), padx=PADDING
        )

        tk.Label(self._opencv_options, text="Line Thickness").grid(
            row=6, column=2, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )
        self._bounding_box_thickness = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["bounding-box-thickness"]),
            from_=0.0,
            to=1.0,
            increment=0.001,
        )
        self._bounding_box_thickness.grid(
            row=6, column=3, sticky=STICKY, padx=PADDING, pady=(PADDING, 0)
        )

        tk.Label(self._opencv_options, text="Smooth Time").grid(
            row=7, column=0, sticky=STICKY, padx=PADDING, pady=PADDING
        )
        self._bounding_box_smooth_time = Spinbox(
            self._opencv_options,
            str(CONFIG_MAP["bounding-box-smooth-time"]),
            from_=0.0,
            to=MAX_DURATION,
            increment=DURATION_INCREMENT,
            suffix="s",
        )
        self._bounding_box_smooth_time.grid(
            row=7, column=1, sticky=STICKY, padx=PADDING, pady=PADDING
        )

        tk.Label(self._opencv_options, text="Min. Box Size").grid(
            row=7, column=2, sticky=STICKY, padx=PADDING, pady=PADDING
        )
        self._bounding_box_min_size = Spinbox(
            self._opencv_options,
            value=str(CONFIG_MAP["bounding-box-min-size"]),
            from_=0.0,
            to=1.0,
            increment=0.001,
        )
        self._bounding_box_min_size.grid(row=7, column=3, sticky=STICKY, padx=PADDING, pady=PADDING)

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
        if self._output_mode == OutputMode.OPENCV:
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
            self._output_dir_str = output_path
            self._clear_button["state"] = tk.NORMAL

    def _clear_output_directory(self):
        self._output_dir_label.set("Ask Me")
        self._output_dir_str = ""
        self._clear_button["state"] = tk.DISABLED

    def _on_text_overlay(self):
        self._timecode_checkbutton["state"] = tk.NORMAL
        self._frame_metrics_checkbutton["state"] = tk.NORMAL
        state = tk.NORMAL if (self._frame_metrics.get() or self._timecode.get()) else tk.DISABLED
        self._text_border["state"] = state
        self._text_font_scale["state"] = state
        self._text_font_thickness["state"] = state
        self._text_margin["state"] = state
        self._text_bg_color["state"] = state
        self._text_font_color["state"] = state

    def _on_bounding_box(self):
        self._bounding_box_button["state"] = tk.NORMAL
        state = tk.NORMAL if self._bounding_box.get() else tk.DISABLED
        self._bounding_box_color["state"] = state
        self._bounding_box_thickness["state"] = state
        self._bounding_box_smooth_time["state"] = state
        self._bounding_box_min_size["state"] = state

    def _on_mode_combo_selected(self):
        self._options_button["state"] = (
            tk.DISABLED if self._output_mode == OutputMode.COPY else tk.NORMAL
        )

    @property
    def _output_mode(self) -> OutputMode:
        index = self._output_mode_combo.current()
        if index == 0:
            return OutputMode.OPENCV
        elif index == 1:
            return OutputMode.FFMPEG
        else:
            return OutputMode.COPY

    @_output_mode.setter
    def _output_mode(self, newval: OutputMode):
        assert newval != OutputMode.SCAN_ONLY  # Scan only is a separate checkbox in the UI.
        if newval == OutputMode.OPENCV:
            self._output_mode_combo.current(0)
        elif newval == OutputMode.FFMPEG:
            self._output_mode_combo.current(1)
        elif newval == OutputMode.COPY:
            self._output_mode_combo.current(2)

    @property
    def _output_dir(self) -> str:
        return self._output_dir_str

    @_output_dir.setter
    def _output_dir(self, newval: str):
        if newval:
            self._output_dir_str = newval
            self._output_dir_label.set(newval)
            self._clear_button["state"] = tk.NORMAL
        else:
            self._output_dir_label.set("Ask Me")
            self._output_dir_str = ""
            self._clear_button["state"] = tk.DISABLED

    def load(self, settings: ScanSettings):
        output_mode = OutputMode[settings.get("output-mode").upper()]
        if output_mode != OutputMode.SCAN_ONLY:
            self._output_mode = output_mode
        output_dir = settings.get("output-dir")
        if output_dir:
            self._output_dir = output_dir
        self._ffmpeg_input_args.set(settings.get("ffmpeg-input-args"))
        self._ffmpeg_output_args.set(settings.get("ffmpeg-output-args"))
        self._opencv_codec.set(settings.get("opencv-codec"))
        # Text Overlays
        self._timecode.set(settings.get("time-code"))
        self._frame_metrics.set(settings.get("frame-metrics"))
        self._text_font_color.set(settings.get("text-font-color"))
        self._text_bg_color.set(settings.get("text-bg-color"))
        self._text_font_scale.set(settings.get("text-font-scale"))
        self._text_font_thickness.set(settings.get("text-font-thickness"))
        self._text_border.set(settings.get("text-border"))
        self._text_margin.set(settings.get("text-margin"))
        # Bounding Box
        self._bounding_box.set(settings.get("bounding-box"))
        self._bounding_box_color.set(settings.get("bounding-box-color"))
        self._bounding_box_min_size.set(settings.get("bounding-box-min-size"))
        self._bounding_box_smooth_time.set(settings.get("bounding-box-smooth-time"))
        self._bounding_box_thickness.set(settings.get("bounding-box-thickness"))

    def save(self, settings: ScanSettings) -> ScanSettings:
        settings.set("output-mode", self._output_mode)
        if self._output_dir:
            settings.set("output-dir", self._output_dir)
        if self._output_mode == OutputMode.FFMPEG:
            settings.set("ffmpeg-input-args", self._ffmpeg_input_args.get())
            settings.set("ffmpeg-output-args", self._ffmpeg_output_args.get())
        elif self._output_mode == OutputMode.OPENCV:
            settings.set("opencv-codec", self._opencv_codec.get())
            # Text Overlays
            settings.set("time-code", self._timecode.get())
            settings.set("frame-metrics", self._frame_metrics.get())
            settings.set("text-font-color", self._text_font_color.get())
            settings.set("text-bg-color", self._text_bg_color.get())
            settings.set("text-font-scale", float(self._text_font_scale.get()))
            settings.set("text-font-thickness", int(self._text_font_thickness.get()))
            settings.set("text-border", int(self._text_border.get()))
            settings.set("text-margin", int(self._text_margin.get()))
            # Bounding Box
            settings.set("bounding-box", self._bounding_box.get())
            settings.set("bounding-box-smooth-time", self._bounding_box_smooth_time.get())
            settings.set("bounding-box-color", self._bounding_box_color.get())
            settings.set("bounding-box-min-size", float(self._bounding_box_min_size.get()))
            settings.set("bounding-box-thickness", float(self._bounding_box_thickness.get()))
        return settings


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

    def __init__(self, settings: ScanSettings, initial_videos: []):
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
        self._input_area = InputArea(input_frame)
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
        self._root.bind("<<StartScan>>", lambda _: self._start_scan())
        self._root.protocol("WM_DELETE_WINDOW", self._destroy)

        if not SUPPRESS_EXCEPTIONS:

            def error_handler(*args):
                raise

            self._root.report_callback_exception = error_handler

        # Initialize UI state from config.
        self._initialize_settings(settings)
        for path in initial_videos:
            self._input_area._add_video(path)

    def _create_menubar(self):
        root_menu = tk.Menu(self._root)
        self._root["menu"] = root_menu

        file_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=file_menu, label="File", underline=0)

        file_menu.add_command(
            label="Start Scan",
            underline=0,
            command=lambda: self._root.event_generate("<<StartScan>>"),
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Quit",
            underline=0,
            command=self._destroy,
        )

        settings_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=settings_menu, label="Settings", underline=0)
        settings_menu.add_command(
            label="Load...",
            underline=0,
            command=self._load_config,
        )
        # TODO: Add functionality to save settings to a config file.
        settings_menu.add_command(label="Save...", underline=0, command=self._on_save_config)
        # settings_menu.add_command(label="Save as User Default", underline=2, state=tk.DISABLED)
        settings_menu.add_separator()
        settings_menu.add_command(
            label="Reset (User Default)", underline=12, command=self._reset_config
        )
        settings_menu.add_command(
            label="Reset (Program Default)",
            underline=0,
            command=lambda: self._reset_config(program_default=True),
        )

        help_menu = tk.Menu(root_menu)
        root_menu.add_cascade(menu=help_menu, label="Help", underline=0)
        help_menu.add_command(
            label="Help Guide",
            command=lambda: webbrowser.open_new_tab("www.dvr-scan.com/guide"),
            underline=0,
        )
        # TODO: Add window to show log messages and copy them to clipboard or save to a logfile.
        # help_menu.add_command(label="Debug Log", underline=0, state=tk.DISABLED)
        help_menu.add_separator()

        help_menu.add_command(
            label="About DVR-Scan",
            command=lambda: AboutWindow().show(root=self._root),
            underline=0,
        )

    def _destroy(self):
        logger.debug("shutting down")
        if self._scan_window is not None:
            # NOTE: We do not actually wait here,
            logger.debug("waiting for worker threads")
            # Signal all active worker threads to start shutting down.
            self._root.event_generate("<<Shutdown>>")
            # Make sure they actually have stopped.
            self._root.after(0, lambda: self._scan_window.stop())
        if self._input_area._region_editor:
            self._input_area._region_editor.prompt_save_on_scan(self._root)
        self._root.after(0, lambda: self._root.destroy())
        self._root.withdraw()

    def _start_scan(self):
        # It should not be possible to start two scans in parallel with the current UI.
        # Once we start a scan, the scan window should grab input focus until it is closed.
        assert self._scan_window is None

        # TODO: Instead of just returning None below if the settings are invalid or we can't start
        # the scan (e.g. no input videos selected), we should throw an exception and catch it here.
        # We should then display a messagebox to the user indicating why the scan couldn't start.
        settings = self._get_settings()
        if not settings:
            return

        logger.debug(f"ui settings:\n{settings.app_settings}")

        def on_closed():
            logger.debug("scan window closed, restoring focus")
            self._scan_window = None
            self._scan_area.enable()
            self._root.deiconify()
            self._root.focus()

        self._scan_window = ScanWindow(self._root, settings, on_closed, PADDING)
        self._scan_area.disable()
        self._scan_window.show()

    def _load_config(self):
        load_path = tkinter.filedialog.askopenfilename(
            title="Load Config File...",
            filetypes=[("Config File", "*.cfg")],
            defaultextension=".cfg",
            parent=self._root,
        )
        if not load_path:
            return
        try:
            config = ConfigRegistry()
            config.load(load_path)
        except ConfigLoadFailure as ex:
            for log_level, log_str in ex.init_log:
                logger.log(log_level, log_str)
            tkinter.messagebox.showerror(
                title="Config Load Failure",
                message="Invalid config file. See log messages for details.",
            )
            return

        for log_level, log_str in config.consume_init_log():
            logger.log(log_level, log_str)
        self._reload_config(config)

    def _reset_config(self, program_default: bool = False):
        if not tkinter.messagebox.askyesno(
            title="Reset Settings",
            message="All settings will be reset. Do you want to continue?",
            icon=tkinter.messagebox.WARNING,
        ):
            return
        try:
            config = ConfigRegistry()
            if not program_default:
                config.load()
        except ConfigLoadFailure as ex:
            for log_level, log_str in ex.init_log:
                logger.log(log_level, log_str)
            tkinter.messagebox.showerror(
                title="Config Load Failure",
                message="Failed to load specified config file. See log messages for details.",
            )
            return

        for log_level, log_str in config.consume_init_log():
            logger.log(log_level, log_str)
        self._reload_config(config)

    def _reload_config(self, config: ConfigRegistry):
        """Reinitialize UI from another config."""
        self._initialize_settings(ScanSettings(args=self._settings._args, config=config))

    def _initialize_settings(self, settings: ScanSettings):
        """Initialize UI from both UI command-line arguments and config file."""
        logger.debug("initializing UI state from settings")
        # Store copy of settings internally.
        self._settings = settings
        if settings.get("load-region"):
            tkinter.messagebox.showwarning(
                title="Regions Not Loaded",
                message="Warning: region file from config was not loaded.\n\n"
                "You can load it from the Region Editor.",
            )
        self._settings_area.set(settings)
        self._output_area.load(settings)
        if OutputMode[settings.get("output-mode").upper()] == OutputMode.SCAN_ONLY:
            self._scan_area.scan_only = True

    def _on_save_config(self):
        save_path = tkinter.filedialog.asksaveasfilename(
            title="Save Config File...",
            filetypes=[("Config File", "*.cfg")],
            defaultextension=".cfg",
            confirmoverwrite=True,
            parent=self._root,
        )
        if not save_path:
            return
        settings = self._get_config_settings()
        with open(save_path, "w") as file:
            settings.write_to_file(file)

    def _get_config_settings(self) -> ScanSettings:
        """Get current UI state for writing a config file."""
        settings = ScanSettings(args=None, config=ConfigRegistry())
        # Only include settings/output areas, exclude input/scan area.
        settings = self._settings_area.update(settings)
        settings = self._output_area.save(settings)
        return settings

    def _get_settings(self) -> ty.Optional[ScanSettings]:
        """Get current UI state with all options to run a scan."""
        settings = copy.deepcopy(self._settings)

        # Input Area
        settings = self._input_area.update(settings)
        if not settings:
            return None

        # Settings Area
        settings = self._settings_area.update(settings)

        # Output Area
        settings = self._output_area.save(settings)

        # Scan Area
        # TODO: Move this logic into the scan area.
        settings.set("scan-only", self._scan_area.scan_only)
        if not settings.get("output-dir") and (
            not settings.get("scan-only") or settings.get("mask-output")
        ):
            # We will create files but an output directory wasn't set ahead of time - prompt the
            # user to select one.
            output_dir = tkinter.filedialog.askdirectory(
                title="Set Output Directory", mustexist=True
            )
            if output_dir:
                settings.set("output-dir", output_dir)
            else:
                return None

        if settings.get("mask-output"):
            video_name = Path(settings.get("input")[0]).stem
            settings.set("mask-output", f"{video_name}-mask.avi")

        if not self._input_area.concatenate and len(settings.get_arg("input")) > 1:
            logger.error("ERROR - TODO: Handle non-concatenated inputs.")
            return None

        return settings
