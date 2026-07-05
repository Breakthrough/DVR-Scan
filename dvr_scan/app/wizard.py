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

"""Scan Wizard: a simplified step-by-step workflow for running a scan, and the
default entry point of the application. The first step doubles as the app's
landing screen, with a large drop target for adding videos."""

import importlib.resources as resources
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.ttk as ttk
import traceback
import typing as ty
import webbrowser
from logging import getLogger
from pathlib import Path

import PIL
import PIL.Image
import PIL.ImageTk
from tkinterdnd2 import DND_FILES

import dvr_scan
import dvr_scan.presets as presets
from dvr_scan.app.about_window import AboutWindow
from dvr_scan.app.application import (
    PADDING,
    SORT_FIELDS,
    finalize_output_names,
)
from dvr_scan.app.common import MenuBar, register_icon
from dvr_scan.app.scan_window import (
    ScanProgressView,
    build_event_table,
    prompt_stop_scan,
    save_report,
)
from dvr_scan.app.video_list import VideoList
from dvr_scan.app.widgets import Spinbox
from dvr_scan.config import ConfigLoadFailure, ConfigRegistry
from dvr_scan.platform import is_ffmpeg_available
from dvr_scan.scanner import OutputMode
from dvr_scan.shared import ScanSettings
from dvr_scan.video_input import BackendUnavailable

WIZARD_TITLE = "DVR-Scan"
MIN_WIZARD_WIDTH = 640
MIN_WIZARD_HEIGHT = 420
LOGO_SIZE = 200
# The drop-zone logo and text sit at this opacity at rest and brighten to full while a file
# is dragged over the zone.
DROP_ZONE_OPACITY = 0.70
DROP_ZONE_ACTIVE_OPACITY = 1.0
# CTA text color (the logo's dominant slate-blue); blended toward the background to match the
# logo's at-rest opacity.
DROP_ZONE_TEXT_COLOR = "#474d57"
# How often the videos step checks if the drop zone should be swapped for the list.
DROP_ZONE_REFRESH_MS = 250
MAX_THRESHOLD = 255.0
MAX_SUMMARY_VIDEOS = 5

logger = getLogger("dvr_scan")


def _faded_logo(
    widget: tk.Widget, background: str, opacity: float = DROP_ZONE_OPACITY
) -> PIL.ImageTk.PhotoImage:
    """Load the DVR-Scan logo blended onto `background` at reduced opacity. Tk cannot
    alpha-composite widgets, so we pre-blend with the background color using PIL. The
    chosen background is baked into the image, so this must be regenerated if the theme
    (and thus the background color) ever changes at runtime."""
    logo = PIL.Image.open(resources.open_binary(dvr_scan, "dvr-scan.png")).convert("RGBA")
    logo.thumbnail((LOGO_SIZE, LOGO_SIZE), PIL.Image.LANCZOS)
    alpha = logo.getchannel("A").point(lambda value: int(value * opacity))
    logo.putalpha(alpha)
    red, green, blue = (channel // 256 for channel in widget.winfo_rgb(background))
    base = PIL.Image.new("RGBA", logo.size, (red, green, blue, 255))
    return PIL.ImageTk.PhotoImage(PIL.Image.alpha_composite(base, logo))


def _blend(widget: tk.Widget, foreground: str, background: str, opacity: float) -> str:
    """Blend `foreground` toward `background` at `opacity` (1.0 = full foreground), returned
    as a #rrggbb string. Labels can't be alpha-composited, so this fakes text opacity to
    match the faded logo."""
    fg = [channel // 256 for channel in widget.winfo_rgb(foreground)]
    bg = [channel // 256 for channel in widget.winfo_rgb(background)]
    blended = (int(f * opacity + b * (1.0 - opacity)) for f, b in zip(fg, bg, strict=True))
    return "#{:02x}{:02x}{:02x}".format(*blended)


class _VideosStep:
    """Step 1: add input videos. Shows a logo drop zone until videos are added,
    then swaps to the input list. Doubles as the app's landing screen."""

    title = "Add Videos"

    def __init__(
        self,
        root: tk.Widget,
        window: tk.Toplevel,
        on_state_changed: ty.Optional[ty.Callable[[], None]] = None,
    ):
        self.frame = ttk.Frame(root)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        self._on_state_changed = on_state_changed
        self._cta_logo = None
        self._drag_active = False

        self._input_frame = ttk.Frame(self.frame)
        self.input_area = VideoList(self._input_frame)
        self._input_frame.grid(row=0, column=0, sticky=tk.NSEW)

        background = ttk.Style().lookup("TFrame", "background") or "white"
        self._drop_zone = tk.Canvas(self.frame, background=background, highlightthickness=0)
        # At-rest vs. drag-over variants: the logo and text brighten to full opacity while a
        # file is dragged over the zone.
        self._logo = _faded_logo(self._drop_zone, background, DROP_ZONE_OPACITY)
        self._logo_active = _faded_logo(self._drop_zone, background, DROP_ZONE_ACTIVE_OPACITY)
        self._text_color = _blend(
            self._drop_zone, DROP_ZONE_TEXT_COLOR, background, DROP_ZONE_OPACITY
        )
        self._text_color_active = DROP_ZONE_TEXT_COLOR
        # The CTA text is a real Label (embedded in the canvas via create_window) rather than
        # a canvas text item: canvas text uses grayscale anti-aliasing and looks soft, while a
        # Label renders with the same crisp ClearType as the rest of the UI.
        self._cta_label = tk.Label(
            self._drop_zone,
            text="Add videos...",
            justify=tk.CENTER,
            font=("TkDefaultFont", 14, "bold"),
            background=background,
            foreground=self._text_color,
        )
        self._drop_zone.bind("<Configure>", lambda _: self._draw_drop_zone())
        self._drop_zone.grid(row=0, column=0, sticky=tk.NSEW)

        # The drop zone is display-only: videos are added by dropping files here or via
        # File > Open. Accept drops anywhere on the wizard (tkdnd was loaded by the main window).
        window.drop_target_register(DND_FILES)
        window.dnd_bind("<<DropEnter>>", self._on_drag_enter)
        window.dnd_bind("<<DropLeave>>", self._on_drag_leave)
        window.dnd_bind("<<Drop>>", self._on_drop)

        self._refresh()

    def _draw_drop_zone(self):
        canvas = self._drop_zone
        canvas.delete("all")
        center_x = canvas.winfo_width() // 2
        center_y = canvas.winfo_height() // 2
        logo = self._logo_active if self._drag_active else self._logo
        self._cta_logo = canvas.create_image(center_x, center_y - 56, image=logo)
        canvas.create_window(center_x, center_y + 88, window=self._cta_label)

    def _set_drag_active(self, active: bool):
        """Brighten (or restore) the logo/text as a file is dragged over the drop zone."""
        if self._drag_active == active or not self._drop_zone.winfo_exists():
            return
        self._drag_active = active
        if self._cta_logo is not None:
            self._drop_zone.itemconfigure(
                self._cta_logo, image=self._logo_active if active else self._logo
            )
        self._cta_label.configure(
            foreground=self._text_color_active if active else self._text_color
        )

    def _on_drag_enter(self, event):
        self._set_drag_active(True)
        return event.action

    def _on_drag_leave(self, _event):
        self._set_drag_active(False)

    def _on_drop(self, event):
        self._set_drag_active(False)
        # Dropped paths are a Tcl list (paths with spaces are wrapped in braces).
        for path_str in self._drop_zone.tk.splitlist(event.data):
            path = Path(path_str)
            if not path.is_file():
                logger.info(f"Ignoring dropped item (not a file): {path}")
                continue
            self.input_area.add_video(str(path))
        self._refresh()

    def _refresh(self):
        """Show the drop zone when the video list is empty, the list otherwise.
        Re-checks periodically since the list can change via the Add/Remove buttons."""
        if not self.frame.winfo_exists():
            return
        if self.input_area.videos:
            self._drop_zone.grid_remove()
            self._input_frame.grid()
        else:
            self._input_frame.grid_remove()
            self._drop_zone.grid()
        if self._on_state_changed is not None:
            self._on_state_changed()
        self.frame.after(DROP_ZONE_REFRESH_MS, self._refresh)

    def on_show(self):
        pass

    def validate(self) -> ty.Optional[str]:
        if not self.input_area.videos:
            return "Add at least one video to scan."
        return None


class _PresetStep:
    """Step 2: choose a preset and adjust sensitivity."""

    title = "Choose Preset"

    def __init__(
        self,
        root: tk.Widget,
        on_preset_applied: ty.Callable[[presets.Preset, ConfigRegistry], None],
    ):
        self.frame = ttk.Frame(root)
        self._on_preset_applied = on_preset_applied
        self._presets: ty.Dict[str, presets.Preset] = {}
        self.config = ConfigRegistry()
        self.config.load()  # Start from the Default preset (user config or defaults).

        self.frame.columnconfigure(1, weight=1)

        tk.Label(self.frame, text="Preset").grid(
            row=0, column=0, sticky=tk.W, padx=PADDING, pady=PADDING
        )
        self._combo = ttk.Combobox(self.frame, state="readonly")
        self._combo.grid(row=0, column=1, sticky=tk.EW, padx=PADDING, pady=PADDING)
        self._combo.bind("<<ComboboxSelected>>", lambda _: self._on_selected())

        tk.Label(self.frame, text="Sensitivity Threshold").grid(
            row=1, column=0, sticky=tk.W, padx=PADDING, pady=PADDING
        )
        self._threshold = Spinbox(
            self.frame,
            value=str(self.config.get("threshold")),
            from_=0.0,
            to=MAX_THRESHOLD,
            increment=0.01,
        )
        self._threshold.grid(row=1, column=1, sticky=tk.W, padx=PADDING, pady=PADDING)
        tk.Label(
            self.frame,
            text="Lower values detect smaller amounts of motion.",
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=PADDING)

    @property
    def preset_name(self) -> str:
        return self._combo.get() or presets.DEFAULT_PRESET_NAME

    @property
    def threshold(self) -> float:
        return float(self._threshold.get())

    def _on_selected(self):
        self._combo.selection_clear()
        name = self._combo.get()
        if name not in self._presets:
            return
        preset = self._presets[name]
        try:
            config = presets.load_preset(preset)
        except ConfigLoadFailure as ex:
            for log_level, log_str in ex.init_log:
                logger.log(log_level, log_str)
            tkinter.messagebox.showerror(
                title="Preset Load Failure",
                message=f"Failed to load preset: {preset.name}. See log messages for details.",
            )
            return
        for log_level, log_str in config.consume_init_log():
            logger.log(log_level, log_str)
        self.config = config
        self._threshold.set(str(config.get("threshold")))
        self._on_preset_applied(preset, config)

    def on_show(self):
        self._presets = {preset.name: preset for preset in presets.list_presets()}
        self._combo["values"] = list(self._presets)
        if not self._combo.get():
            self._combo.set(presets.DEFAULT_PRESET_NAME)

    def validate(self) -> ty.Optional[str]:
        return None


class _OutputStep:
    """Step 3: choose what to do with detected motion events."""

    title = "Choose Output"

    _MODES: ty.List[ty.Tuple[str, ty.Optional[OutputMode]]] = [
        ("Extract Events (MP4, H.264) - Recommended", OutputMode.ENCODE),
        ("Extract Events (OpenCV, .avi)", OutputMode.OPENCV),
        ("Extract Events (ffmpeg)", OutputMode.FFMPEG),
        ("Extract Events (ffmpeg copy)", OutputMode.COPY),
        ("Scan Only (report)", None),
    ]

    def __init__(self, root: tk.Widget):
        self.frame = ttk.Frame(root)
        self.frame.columnconfigure(1, weight=1)

        tk.Label(self.frame, text="Mode").grid(
            row=0, column=0, sticky=tk.W, padx=PADDING, pady=PADDING
        )
        self._mode_combo = ttk.Combobox(self.frame, state="readonly")
        self._mode_combo["values"] = [label for label, _ in self._MODES]
        # Default to MP4 output, unless ffmpeg is unavailable on this system.
        self._mode_combo.current(0 if is_ffmpeg_available() else 1)
        self._mode_combo.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=PADDING)

        self._directory = ""
        self._directory_label = tk.StringVar(self.frame, value="No Directory Selected")
        tk.Label(self.frame, text="Directory").grid(
            row=1, column=0, sticky=tk.W, padx=PADDING, pady=PADDING
        )
        ttk.Entry(self.frame, state=tk.DISABLED, textvariable=self._directory_label).grid(
            row=1, column=1, sticky=tk.EW, padx=PADDING, pady=PADDING
        )
        ttk.Button(self.frame, text="Select...", command=self._on_select).grid(
            row=1, column=2, sticky=tk.EW, padx=PADDING, pady=PADDING
        )

    def _on_select(self):
        directory = tkinter.filedialog.askdirectory(title="Set Output Directory", mustexist=True)
        if directory:
            self._directory = directory
            self._directory_label.set(directory)

    @property
    def mode_label(self) -> str:
        return self._mode_combo.get()

    @property
    def scan_only(self) -> bool:
        return self.output_mode is None

    @property
    def output_mode(self) -> ty.Optional[OutputMode]:
        return dict(self._MODES)[self._mode_combo.get()]

    @property
    def directory(self) -> str:
        return self._directory

    def on_show(self):
        pass

    def validate(self) -> ty.Optional[str]:
        if not self.scan_only and not self._directory:
            return "Select an output directory, or choose Scan Only mode."
        return None


class _SummaryStep:
    """Step 4: review choices before starting the scan."""

    title = "Review & Scan"

    def __init__(
        self,
        root: tk.Widget,
        videos_step: _VideosStep,
        preset_step: _PresetStep,
        output_step: _OutputStep,
    ):
        self.frame = ttk.Frame(root)
        self._videos_step = videos_step
        self._preset_step = preset_step
        self._output_step = output_step
        self._summary = tk.Label(self.frame, justify=tk.LEFT, anchor=tk.NW)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self._summary.grid(row=0, column=0, sticky=tk.NSEW, padx=PADDING, pady=PADDING)

    def on_show(self):
        videos = self._videos_step.input_area.videos
        video_names = [Path(video).name for video in videos[:MAX_SUMMARY_VIDEOS]]
        if len(videos) > MAX_SUMMARY_VIDEOS:
            video_names.append(f"... and {len(videos) - MAX_SUMMARY_VIDEOS} more")
        lines = [
            f"Videos ({len(videos)}):",
            *(f"    {name}" for name in video_names),
            "",
            f"Preset: {self._preset_step.preset_name}",
            f"Sensitivity Threshold: {self._preset_step.threshold:g}",
            "",
            f"Output: {self._output_step.mode_label}",
        ]
        if not self._output_step.scan_only:
            lines.append(f"Directory: {self._output_step.directory}")
        self._summary["text"] = "\n".join(lines)

    def validate(self) -> ty.Optional[str]:
        return None


class _ScanStep:
    """Final step: runs the scan, showing live progress and then a report (or an
    error/stopped panel). Content is swapped in `body` by the ScanWizard."""

    title = "Scan"

    def __init__(self, root: tk.Widget):
        self.frame = ttk.Frame(root)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.body = ttk.Frame(self.frame)
        self.body.grid(row=0, column=0, sticky=tk.NSEW)
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=1)
        self._content: ty.Optional[tk.Widget] = None

    def set_content(self, widget: ty.Optional[tk.Widget]):
        """Replace the displayed content with `widget`, destroying the previous one."""
        if self._content is not None:
            self._content.destroy()
        self._content = widget
        if widget is not None:
            widget.grid(row=0, column=0, sticky=tk.NSEW)

    def on_show(self):
        pass

    def validate(self) -> ty.Optional[str]:
        return None


class ScanWizard:
    """Step-by-step scan workflow shown in place of the main window. Created by the
    `Application`, which provides callbacks for switching back to classic mode. The
    scan runs in-place on the final step rather than in a separate window."""

    def __init__(
        self,
        root: tk.Tk,
        settings: ScanSettings,
        on_close: ty.Callable[[], None],
        on_switch_to_classic: ty.Callable[[ty.List[str]], None],
        on_preset_applied: ty.Callable[[presets.Preset, ConfigRegistry], None],
    ):
        self._settings = settings
        self._on_close = on_close
        self._on_switch_to_classic = on_switch_to_classic
        self._scan_view: ty.Optional[ScanProgressView] = None
        self._scanning = False
        self._browse_in_progress = False

        self._window = tk.Toplevel(master=root)
        self._window.withdraw()
        self._window.title(WIZARD_TITLE)
        register_icon(self._window)
        self._window.minsize(MIN_WIZARD_WIDTH, MIN_WIZARD_HEIGHT)
        self._window.protocol("WM_DELETE_WINDOW", self._on_quit)
        # Row 0 holds the custom menubar (on Windows); content row gets the vertical weight.
        self._window.rowconfigure(2, weight=1)
        self._window.columnconfigure(0, weight=1)

        self._header = tk.Label(self._window, font=("TkDefaultFont", 12, "bold"))
        self._header.grid(row=1, column=0, sticky=tk.W, padx=PADDING, pady=PADDING)

        content = ttk.Frame(self._window)
        content.grid(row=2, column=0, sticky=tk.NSEW, padx=PADDING)
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)

        videos_step = _VideosStep(content, self._window)
        preset_step = _PresetStep(content, on_preset_applied)
        output_step = _OutputStep(content)
        summary_step = _SummaryStep(content, videos_step, preset_step, output_step)
        scan_step = _ScanStep(content)
        self._videos_step = videos_step
        self._preset_step = preset_step
        self._output_step = output_step
        self._scan_step = scan_step
        self._steps = [videos_step, preset_step, output_step, summary_step, scan_step]
        # The scan step is terminal: reached via "Start Scan" on the summary, not "Next".
        self._scan_index = len(self._steps) - 1
        self._summary_index = self._scan_index - 1
        for step in self._steps:
            step.frame.grid(row=0, column=0, sticky=tk.NSEW)
        self._step_index = 0

        self._create_menubar()
        self._videos_step._on_state_changed = self._refresh_form_nav_state

        buttons = ttk.Frame(self._window)
        buttons.grid(row=3, column=0, sticky=tk.EW, padx=PADDING, pady=PADDING)
        buttons.columnconfigure(1, weight=1)

        self._classic_button = ttk.Button(buttons, text="Advanced Mode", command=self._on_switch)
        self._classic_button.grid(row=0, column=0, sticky=tk.W)
        self._back_button = ttk.Button(buttons, text="< Back", command=self._on_back)
        self._back_button.grid(row=0, column=2, padx=(PADDING, 0))
        self._next_button = ttk.Button(buttons, text="Next >", command=self._on_next)
        self._next_button.grid(row=0, column=3, padx=(PADDING, 0))
        self._stop_button = ttk.Button(buttons, text="Stop", command=self._on_stop)
        self._stop_button.grid(row=0, column=3, padx=(PADDING, 0))
        self._stop_button.grid_remove()

        self._show_step(0)

    @property
    def videos(self) -> ty.List[str]:
        return self._videos_step.input_area.videos

    def set_videos(self, paths: ty.List[str]):
        """Add `paths` to the wizard's video list, skipping any already present."""
        existing = set(self.videos)
        for path in paths:
            if path not in existing:
                self._videos_step.input_area.add_video(path)
        self._refresh_form_nav_state()

    def show(self):
        self._window.deiconify()
        self._window.focus()

    def hide(self):
        self._window.withdraw()

    def shutdown(self):
        """Stop any in-progress scan. Called when the application is shutting down."""
        if self._scan_view is not None:
            self._scan_view.stop()

    def _show_step(self, index: int):
        self._step_index = index
        step = self._steps[index]
        step.on_show()
        for other in self._steps:
            other.frame.grid_remove()
        step.frame.grid()
        # The first step is also the landing screen: the large drop-zone CTA already labels
        # it, so suppress the redundant "Add Videos" header there but keep it for the rest.
        if index == 0:
            self._header.grid_remove()
        else:
            self._header["text"] = step.title
            self._header.grid()
        # The scan step manages its own navigation buttons via the scan lifecycle.
        if index == self._scan_index:
            return
        self._show_form_nav()

    def _show_form_nav(self):
        self._stop_button.grid_remove()
        self._next_button.grid()
        self._refresh_form_nav_state()

    def _refresh_form_nav_state(self):
        self._classic_button["state"] = tk.NORMAL
        self._back_button["state"] = tk.NORMAL if self._step_index > 0 else tk.DISABLED
        can_advance = self._step_index > 0 or bool(self.videos)
        self._next_button["state"] = tk.NORMAL if can_advance else tk.DISABLED
        self._next_button["text"] = (
            "Start Scan" if self._step_index == self._summary_index else "Next >"
        )

    def _set_form_nav_enabled(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in (
            self._classic_button,
            self._back_button,
            self._next_button,
        ):
            button["state"] = state

    def _show_scanning_nav(self):
        self._next_button.grid_remove()
        self._stop_button.grid()
        self._stop_button["state"] = tk.NORMAL
        self._classic_button["state"] = tk.DISABLED
        self._back_button["state"] = tk.DISABLED

    def _show_report_nav(self):
        # Report panels carry their own New Scan / Save Report buttons; the nav row only
        # offers going Back to tweak settings, switching to advanced mode, or quitting.
        self._stop_button.grid_remove()
        self._next_button.grid_remove()
        self._classic_button["state"] = tk.NORMAL
        self._back_button["state"] = tk.NORMAL

    def _on_back(self):
        if self._browse_in_progress:
            return
        if self._step_index > 0 and not self._scanning:
            self._show_step(self._step_index - 1)

    def _on_next(self):
        if self._browse_in_progress:
            return
        if self._step_index == 0 and not self.videos:
            return
        error = self._steps[self._step_index].validate()
        if error is not None:
            tkinter.messagebox.showerror(title=WIZARD_TITLE, message=error, parent=self._window)
            return
        if self._step_index == self._summary_index:
            self._start_scan()
        elif self._step_index < self._summary_index:
            self._show_step(self._step_index + 1)

    def _on_switch(self):
        if self._browse_in_progress:
            return
        self.hide()
        self._on_switch_to_classic(self.videos)

    def _on_quit(self):
        if self._scanning:
            if self._scan_view is None or not prompt_stop_scan(self._scan_view, self._window):
                return
            self._scan_view.stop()
        self.hide()
        self._on_close()

    def _on_stop(self):
        if self._scan_view is None:
            return
        if prompt_stop_scan(self._scan_view, self._window):
            # The scan is now stopped; the update loop will present the result panel.
            self._scan_view.stop()

    def _browse_videos(self):
        if self._browse_in_progress:
            return
        had_videos = bool(self.videos)
        self._browse_in_progress = True
        self._set_form_nav_enabled(False)
        try:
            self._videos_step.input_area.add_video(parent=self._window)
        finally:
            self._browse_in_progress = False
            if self._window.winfo_exists() and not self._scanning:
                self._refresh_form_nav_state()
                if self._step_index == 0 and not had_videos and self.videos:
                    self._next_button.focus_set()

    def _create_menubar(self):
        self._menubar = MenuBar(self._window)
        if self._menubar.frame is not None:
            self._menubar.frame.grid(row=0, column=0, sticky=tk.EW)
        self._window.bind("<Control-o>", lambda _: self._browse_videos())
        self._window.bind("<Control-O>", lambda _: self._browse_videos())

        file_menu = self._menubar.add_menu("File", underline=0)
        file_menu.add_command(
            label="Open...",
            underline=0,
            command=self._browse_videos,
            accelerator="Ctrl+O",
        )
        file_menu.add_cascade(label="Sort", underline=0, menu=self._build_sort_menu(file_menu))
        file_menu.add_command(label="Advanced Mode", underline=0, command=self._on_switch)
        file_menu.add_command(label="Quit", underline=0, command=self._on_quit)

        help_menu = self._menubar.add_menu("Help", underline=0)
        help_menu.add_command(
            label="Help Guide",
            underline=0,
            command=lambda: webbrowser.open_new_tab("www.dvr-scan.com/guide"),
        )
        help_menu.add_command(
            label="Discord",
            underline=0,
            command=lambda: webbrowser.open_new_tab("https://discord.gg/69kf6f2Exb"),
        )
        help_menu.add_separator()
        help_menu.add_command(
            label="About DVR-Scan",
            underline=0,
            command=lambda: AboutWindow().show(root=self._window),
        )

    def _build_sort_menu(self, parent: tk.Menu) -> tk.Menu:
        """Build the File > Sort submenu: a radio group of fields, then Ascending/
        Descending. Picking a field applies that field's default direction."""
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
        self._videos_step.input_area.sort_by(self._sort_field.get(), self._sort_descending.get())

    def _start_scan(self):
        settings = ScanSettings(args=self._settings.args, config=self._preset_step.config)
        settings = self._videos_step.input_area.update(settings)
        if not settings:
            tkinter.messagebox.showerror(
                title=WIZARD_TITLE, message="Add at least one video to scan.", parent=self._window
            )
            return
        settings.set("threshold", self._preset_step.threshold)
        settings.set("scan-only", self._output_step.scan_only)
        if self._output_step.output_mode is not None:
            settings.set("output-mode", self._output_step.output_mode)
        if self._output_step.directory:
            settings.set("output-dir", self._output_step.directory)
        finalize_output_names(settings, combine=False)
        logger.debug(f"wizard settings:\n{settings.app_settings}")

        try:
            view = ScanProgressView(self._scan_step.body, settings, self._on_scan_finished, PADDING)
        except BackendUnavailable:
            tkinter.messagebox.showerror(
                title="Input Mode Unavailable",
                message=f"The specified input mode ({settings.get('input-mode')}) "
                "is not available on this system.",
                parent=self._window,
            )
            return
        self._scan_view = view
        self._scan_step.set_content(view.frame)
        self._scanning = True
        self._show_step(self._scan_index)
        self._show_scanning_nav()
        view.start()

    def _on_scan_finished(self):
        # Defer presentation so we don't destroy the progress view from within its own
        # update callback (set_content destroys the previous content widget).
        self._window.after(0, self._present_results)

    def _present_results(self):
        view = self._scan_view
        if view is None:
            return
        self._scanning = False
        if view.error is not None:
            formatted = "\n".join(traceback.format_exception(view.error))
            logger.critical(f"error during scan:\n{formatted}")
            self._scan_step.set_content(self._build_error_panel(view.error))
        elif view.was_stopped or view.result is None:
            self._scan_step.set_content(self._build_stopped_panel(view))
        else:
            self._scan_step.set_content(self._build_report_panel(view))
        self._show_report_nav()

    def _on_new_scan(self):
        self._videos_step.input_area.clear()
        self._scan_step.set_content(None)
        self._scan_view = None
        self._show_step(0)

    def _build_report_panel(self, view: ScanProgressView) -> ttk.Frame:
        result = view.result
        panel = ttk.Frame(self._scan_step.body)
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)

        summary = (
            f"Scan complete: found {len(result.event_list)} motion event(s) "
            f"in {view.frames_processed} frames "
            f"(elapsed {view.elapsed}, {view.rate} FPS)."
        )
        tk.Label(panel, text=summary, anchor=tk.W, justify=tk.LEFT).grid(
            row=0, column=0, columnspan=2, sticky=tk.EW, padx=PADDING, pady=PADDING
        )

        table = build_event_table(panel, view.input_paths, result.event_list)
        table.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=(PADDING, 0))

        buttons = ttk.Frame(panel)
        buttons.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=PADDING)
        ttk.Button(
            buttons,
            text="Save Report...",
            command=lambda: save_report(self._window, result.event_list),
        ).grid(row=0, column=0, padx=PADDING)
        ttk.Button(buttons, text="New Scan", command=self._on_new_scan).grid(
            row=0, column=1, padx=PADDING
        )
        return panel

    def _build_stopped_panel(self, view: ScanProgressView) -> ttk.Frame:
        panel = self._build_message_panel(
            "Scan stopped.",
            f"Stopped after processing {view.frames_processed} frames.",
        )
        return panel

    def _build_error_panel(self, error: Exception) -> ttk.Frame:
        return self._build_message_panel(
            "Scan failed.",
            f"{error}\n\nSee the log for details (Help > Open Logs).",
        )

    def _build_message_panel(self, heading: str, body: str) -> ttk.Frame:
        panel = ttk.Frame(self._scan_step.body)
        panel.columnconfigure(0, weight=1)
        tk.Label(panel, text=heading, font=("TkDefaultFont", 12, "bold"), anchor=tk.W).grid(
            row=0, column=0, sticky=tk.EW, padx=PADDING, pady=(PADDING, 0)
        )
        tk.Label(panel, text=body, anchor=tk.W, justify=tk.LEFT).grid(
            row=1, column=0, sticky=tk.EW, padx=PADDING, pady=PADDING
        )
        ttk.Button(panel, text="New Scan", command=self._on_new_scan).grid(
            row=2, column=0, sticky=tk.W, padx=PADDING
        )
        return panel
