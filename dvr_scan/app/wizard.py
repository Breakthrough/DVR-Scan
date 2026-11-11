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

import copy
import importlib.resources as resources
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.ttk as ttk
import typing as ty
from logging import getLogger
from pathlib import Path

import PIL
import PIL.Image
import PIL.ImageTk
from tkinterdnd2 import DND_FILES

import dvr_scan
import dvr_scan.presets as presets
from dvr_scan.app.common import (
    MAX_THRESHOLD,
    PADDING,
    MenuBar,
    add_startup_mode_menu,
    fill_help_menu,
    register_icon,
)
from dvr_scan.app.inputs import handle_drop
from dvr_scan.app.region_editor import ACCELERATOR_KEY
from dvr_scan.app.scan_window import (
    SCAN_SETUP_ERRORS,
    ScanProgressView,
    build_event_table,
    prompt_stop_scan,
    save_report,
    show_scan_setup_error,
)
from dvr_scan.app.video_list import VideoList
from dvr_scan.app.widgets import Spinbox
from dvr_scan.config import ConfigLoadFailure, ConfigRegistry
from dvr_scan.platform import is_ffmpeg_available, open_path
from dvr_scan.scanner import OutputMode
from dvr_scan.shared import ScanSettings, finalize_output_names

WIZARD_TITLE = "DVR-Scan"
MIN_WIZARD_WIDTH = 780
MIN_WIZARD_HEIGHT = 440
LOGO_SIZE = 200
# The drop-zone logo and text sit at this opacity at rest and brighten to full while a file
# is dragged over the zone.
DROP_ZONE_OPACITY = 0.70
DROP_ZONE_ACTIVE_OPACITY = 1.0
# CTA text color (the logo's dominant slate-blue); blended toward the background to match the
# logo's at-rest opacity.
DROP_ZONE_TEXT_COLOR = "#474d57"
MAX_SUMMARY_VIDEOS = 5
# Output modes which run ffmpeg, and the label suffix shown for them when it is missing.
FFMPEG_OUTPUT_MODES = frozenset({OutputMode.ENCODE, OutputMode.FFMPEG, OutputMode.COPY})
FFMPEG_MISSING_SUFFIX = " - requires ffmpeg (not found)"
RECOMMENDED_SUFFIX = " - Recommended"
# Classes of focused widgets that handle Ctrl+A / Delete / BackSpace themselves; the video list
# shortcuts are suppressed while one of these has keyboard focus.
TEXT_ENTRY_CLASSES = frozenset({"Entry", "TEntry", "Spinbox", "TSpinbox", "TCombobox", "Text"})

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
        on_browse: ty.Optional[ty.Callable[[], None]] = None,
        can_accept_drop: ty.Optional[ty.Callable[[], bool]] = None,
        on_load_config: ty.Optional[ty.Callable[[str], bool]] = None,
    ):
        """`on_load_config` loads a dropped `.cfg` file, returning True on success."""
        self.frame = ttk.Frame(root)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        self._window = window
        self._on_state_changed = on_state_changed
        self._on_browse = on_browse
        self._can_accept_drop = can_accept_drop
        self._on_load_config = on_load_config
        self._cta_logo = None
        self._drag_active = False

        self._input_frame = ttk.Frame(self.frame)
        # The list's "+" button goes through the same browse path as the drop zone and
        # File > Open, so the dialog is parented to the wizard and navigation is locked.
        self.input_area = VideoList(self._input_frame, on_add=on_browse)
        self._input_frame.grid(row=0, column=0, sticky=tk.NSEW)

        background = ttk.Style().lookup("TFrame", "background") or "white"
        self._drop_zone = tk.Canvas(
            self.frame, background=background, highlightthickness=0, cursor="hand2"
        )
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
            cursor="hand2",
        )
        self._cta_hint = tk.Label(
            self._drop_zone,
            text="Click to browse or drag and drop video files",
            justify=tk.CENTER,
            font=("TkDefaultFont", 9),
            background=background,
            foreground=self._text_color,
            cursor="hand2",
        )
        for widget in (self._drop_zone, self._cta_label, self._cta_hint):
            widget.bind("<Button-1>", self._on_drop_zone_click)
        self._drop_zone.bind("<Configure>", lambda _: self._draw_drop_zone())
        self._drop_zone.grid(row=0, column=0, sticky=tk.NSEW)

        # Videos can be added by clicking the drop zone, dropping files onto the wizard,
        # or via File > Open.
        window.drop_target_register(DND_FILES)
        window.dnd_bind("<<DropEnter>>", self._on_drag_enter)
        window.dnd_bind("<<DropLeave>>", self._on_drag_leave)
        window.dnd_bind("<<Drop>>", self._on_drop)

        self.input_area.on_changed = self._refresh
        self._refresh()

    def _on_drop_zone_click(self, _event=None):
        if self._on_browse is not None:
            self._on_browse()

    def _draw_drop_zone(self):
        canvas = self._drop_zone
        canvas.delete("all")
        center_x = canvas.winfo_width() // 2
        center_y = canvas.winfo_height() // 2
        logo = self._logo_active if self._drag_active else self._logo
        self._cta_logo = canvas.create_image(center_x, center_y - 60, image=logo)
        canvas.create_window(center_x, center_y + 76, window=self._cta_label)
        canvas.create_window(center_x, center_y + 104, window=self._cta_hint)

    def _set_drag_active(self, active: bool):
        """Brighten (or restore) the logo/text as a file is dragged over the drop zone."""
        if self._drag_active == active or not self._drop_zone.winfo_exists():
            return
        self._drag_active = active
        if self._cta_logo is not None:
            self._drop_zone.itemconfigure(
                self._cta_logo, image=self._logo_active if active else self._logo
            )
        color = self._text_color_active if active else self._text_color
        self._cta_label.configure(foreground=color)
        self._cta_hint.configure(foreground=color)

    def _on_drag_enter(self, event):
        if self._can_accept_drop is not None and not self._can_accept_drop():
            return event.action
        self._set_drag_active(True)
        return event.action

    def _on_drag_leave(self, _event):
        self._set_drag_active(False)

    def _on_drop(self, event):
        self._set_drag_active(False)
        if self._can_accept_drop is not None and not self._can_accept_drop():
            return
        # Like the Advanced Mode window, a dropped config file is loaded as the active settings.
        handle_drop(
            self._drop_zone,
            event.data,
            add_video=lambda path: self.input_area.add_video(path, parent=self._window),
            load_config=self._on_load_config,
        )

    def _refresh(self):
        """Show the drop zone when the video list is empty, the list otherwise, and notify
        the wizard. Runs whenever the list changes (`VideoList.on_changed`)."""
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

    def on_show(self):
        pass

    def validate(self) -> ty.Optional[str]:
        if not self.input_area.videos:
            return "Add at least one video to scan."
        return None


class _PresetStep:
    """Step 2: choose a preset and adjust sensitivity."""

    title = "Choose Preset"

    _PRESET_DESCRIPTIONS: ty.Dict[str, str] = {
        presets.DEFAULT_PRESET_NAME: (
            "Balanced motion detection using your default configuration settings."
        ),
        "High Sensitivity": (
            "Detects faint or small motion with extra padding before and after each event."
        ),
        "Low Sensitivity": (
            "Only triggers on sustained, significant motion; helps ignore camera noise or flicker."
        ),
        "Fast Scan": (
            "Prioritizes scan speed by downscaling video, skipping frames, and using CNT."
        ),
    }

    def __init__(
        self,
        root: tk.Widget,
        on_preset_applied: ty.Callable[[presets.Preset, ConfigRegistry], None],
        base_config: ty.Optional[ConfigRegistry] = None,
        active_preset: ty.Optional[str] = presets.DEFAULT_PRESET_NAME,
    ):
        """`active_preset` names the preset `base_config` corresponds to (None when it
        came from a config file given on the command line, or when the user config was
        ignored); it is shown in the dropdown the first time the step is displayed."""
        self.frame = ttk.Frame(root)
        self._on_preset_applied = on_preset_applied
        self._presets: ty.Dict[str, presets.Preset] = {}
        self._active_preset: ty.Optional[str] = active_preset
        # Set once the dropdown has been populated from `active_preset` or synced from
        # Advanced Mode, so a later `on_show` does not override the user's selection.
        self._combo_initialized = False
        if base_config is not None:
            self.config = copy.deepcopy(base_config)
        else:
            self.config = presets.load_preset(presets.default_preset())

        self.frame.columnconfigure(1, weight=1)

        tk.Label(self.frame, text="Preset").grid(
            row=0, column=0, sticky=tk.W, padx=PADDING, pady=PADDING
        )
        self._combo = ttk.Combobox(self.frame, state="readonly")
        self._combo.grid(row=0, column=1, sticky=tk.EW, padx=PADDING, pady=PADDING)
        self._combo.bind("<<ComboboxSelected>>", lambda _: self._on_selected())

        self._preset_desc = tk.Label(self.frame, text="", anchor=tk.W, justify=tk.LEFT)
        self._preset_desc.grid(
            row=1, column=0, columnspan=2, sticky=tk.W, padx=PADDING, pady=(0, PADDING)
        )

        tk.Label(self.frame, text="Sensitivity Threshold").grid(
            row=2, column=0, sticky=tk.W, padx=PADDING, pady=PADDING
        )
        self._threshold = Spinbox(
            self.frame,
            value=str(self.config.get("threshold")),
            from_=0.0,
            to=MAX_THRESHOLD,
            increment=0.01,
        )
        self._threshold.grid(row=2, column=1, sticky=tk.W, padx=PADDING, pady=PADDING)
        tk.Label(
            self.frame,
            text="Lower values detect smaller amounts of motion.",
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=PADDING)

    @property
    def preset_name(self) -> str:
        name = self._combo.get()
        if not name:
            return "Custom"
        if abs(self.threshold - float(self.config.get("threshold"))) > 1e-6:
            return "Custom"
        return name

    @property
    def threshold(self) -> float:
        return float(self._threshold.get())

    def _update_description(self):
        name = self._combo.get()
        if not name:
            self._preset_desc["text"] = "Custom settings (from a config file or Advanced Mode)."
        else:
            self._preset_desc["text"] = self._PRESET_DESCRIPTIONS.get(name, "Custom user preset.")

    def _on_selected(self):
        self._combo.selection_clear()
        name = self._combo.get()
        if name not in self._presets:
            return
        if (
            name == self._active_preset
            and abs(self.threshold - float(self.config.get("threshold"))) <= 1e-6
        ):
            return
        preset = self._presets[name]
        try:
            config = presets.load_preset(preset)
        except ConfigLoadFailure as ex:
            ex.log(logger)
            tkinter.messagebox.showerror(
                title="Preset Load Failure",
                message=f"Failed to load preset: {preset.name}. See log messages for details.",
                parent=self.frame.winfo_toplevel(),
            )
            self._combo.set(self._active_preset if self._active_preset else "")
            return
        self._active_preset = name
        self.config = config
        self._threshold.set(str(config.get("threshold")))
        self._update_description()
        self._on_preset_applied(preset, config)

    def sync_from_settings(
        self,
        settings: ScanSettings,
        active_preset: ty.Optional[str] = None,
        config: ty.Optional[ConfigRegistry] = None,
    ):
        """Sync from Advanced Mode `settings`. `config`, if given, replaces the base config
        first (e.g. a config file that was just loaded)."""
        if config is not None:
            self.config = copy.deepcopy(config)
        self._presets = {preset.name: preset for preset in presets.list_available_presets()}
        self._combo["values"] = list(self._presets)
        self._combo_initialized = True
        if active_preset and active_preset in self._presets:
            self._combo.set(active_preset)
            self._active_preset = active_preset
        elif active_preset is None and self._combo.get():
            # Preserve current selection only if threshold still matches; otherwise clear.
            self._combo.set("")
            self._active_preset = None
        for key, value in settings.app_settings.items():
            if not self.config.is_default(key):
                self.config.set(key, value)
        self._threshold.set(str(settings.get("threshold")))
        self._update_description()

    def on_show(self):
        self._presets = {preset.name: preset for preset in presets.list_available_presets()}
        self._combo["values"] = list(self._presets)
        if not self._combo_initialized:
            self._combo_initialized = True
            if self._active_preset in self._presets:
                self._combo.set(self._active_preset)
            else:
                self._combo.set("")
                self._active_preset = None
        self._update_description()

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

    def __init__(
        self,
        root: tk.Widget,
        videos_step: ty.Optional[_VideosStep] = None,
        settings: ty.Optional[ScanSettings] = None,
    ):
        self.frame = ttk.Frame(root)
        self.frame.columnconfigure(1, weight=1)
        self._videos_step = videos_step
        # Checked once: it spawns a process. A combobox can't disable single entries, so
        # modes which need ffmpeg are labelled as unavailable and rejected by `validate`.
        self._ffmpeg_available = is_ffmpeg_available()
        self._modes = self.mode_choices(self._ffmpeg_available)

        tk.Label(self.frame, text="Mode").grid(
            row=0, column=0, sticky=tk.W, padx=PADDING, pady=PADDING
        )
        self._mode_combo = ttk.Combobox(self.frame, state="readonly")
        self._mode_combo["values"] = [label for label, _ in self._modes]
        # Default to MP4 output, unless ffmpeg is unavailable on this system.
        self._mode_combo.current(0 if self._ffmpeg_available else 1)
        self._mode_combo.bind("<<ComboboxSelected>>", lambda _: self._on_mode_changed())
        self._mode_combo.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=PADDING)

        self._directory = ""
        self._user_selected_dir = False
        self._directory_label = tk.StringVar(self.frame, value="No Directory Selected")
        tk.Label(self.frame, text="Directory").grid(
            row=1, column=0, sticky=tk.W, padx=PADDING, pady=PADDING
        )
        self._dir_entry = ttk.Entry(
            self.frame, state=tk.DISABLED, textvariable=self._directory_label
        )
        self._dir_entry.grid(row=1, column=1, sticky=tk.EW, padx=PADDING, pady=PADDING)
        self._select_button = ttk.Button(self.frame, text="Select...", command=self._on_select)
        self._select_button.grid(row=1, column=2, sticky=tk.EW, padx=PADDING, pady=PADDING)

        if settings is not None:
            self.sync_from_settings(settings)
        else:
            self._on_mode_changed()

    @classmethod
    def mode_choices(
        cls, ffmpeg_available: bool
    ) -> ty.List[ty.Tuple[str, ty.Optional[OutputMode]]]:
        """(label, mode) choices for the mode dropdown. Without ffmpeg, the modes that need
        it are labelled as unavailable (and lose the "Recommended" tag)."""
        if ffmpeg_available:
            return list(cls._MODES)
        return [
            (
                (label.removesuffix(RECOMMENDED_SUFFIX) + FFMPEG_MISSING_SUFFIX)
                if mode in FFMPEG_OUTPUT_MODES
                else label,
                mode,
            )
            for label, mode in cls._MODES
        ]

    def _on_mode_changed(self):
        self._mode_combo.selection_clear()
        if self.scan_only:
            self._select_button["state"] = tk.DISABLED
            self._directory_label.set("Not used in Scan Only mode")
        else:
            self._select_button["state"] = tk.NORMAL
            self._directory_label.set(
                self._directory if self._directory else "No Directory Selected"
            )

    def _on_select(self):
        initial_dir = self._directory if self._directory else None
        dialog_options = {
            "title": "Set Output Directory",
            "mustexist": True,
            "parent": self.frame.winfo_toplevel(),
        }
        if initial_dir:
            dialog_options["initialdir"] = initial_dir
        directory = tkinter.filedialog.askdirectory(**dialog_options)
        if directory:
            self._directory = directory
            self._user_selected_dir = True
            self._directory_label.set(directory)

    def set_directory(self, directory: str, user_selected: bool = True):
        self._directory = directory
        self._user_selected_dir = user_selected and bool(directory)
        self._directory_label.set(directory if directory else "No Directory Selected")

    def reset_default_directory(self):
        """Reset directory if it was auto-populated from a previous scan's video."""
        if not self._user_selected_dir:
            self._directory = ""
            self._directory_label.set("No Directory Selected")

    def sync_from_settings(self, settings: ScanSettings):
        output_mode = OutputMode.parse(settings.get("output-mode"))
        if output_mode in FFMPEG_OUTPUT_MODES and not self._ffmpeg_available:
            # Even if set explicitly: the mode can't run, so start from one that can.
            logger.info(f"ffmpeg not found, using OpenCV output instead of {output_mode.name}.")
            output_mode = OutputMode.OPENCV
        target_mode = (
            None
            if (settings.get("scan-only") or output_mode == OutputMode.SCAN_ONLY)
            else output_mode
        )
        for index, (_label, mode) in enumerate(self._modes):
            if mode == target_mode:
                self._mode_combo.current(index)
                break
        output_dir = settings.get("output-dir")
        if output_dir:
            self.set_directory(str(output_dir), user_selected=True)
        self._on_mode_changed()

    @property
    def mode_label(self) -> str:
        return self._mode_combo.get()

    @property
    def scan_only(self) -> bool:
        return self.output_mode is None

    @property
    def output_mode(self) -> ty.Optional[OutputMode]:
        return dict(self._modes)[self._mode_combo.get()]

    @property
    def directory(self) -> str:
        return self._directory

    @property
    def user_selected_directory(self) -> bool:
        """True if `directory` was chosen by the user (or synced from Advanced Mode), False
        if it is empty or was auto-filled from the first video's folder."""
        return self._user_selected_dir

    def on_show(self):
        if (
            not self._user_selected_dir
            and self._videos_step is not None
            and self._videos_step.input_area.videos
        ):
            default_dir = str(Path(self._videos_step.input_area.videos[0]).parent)
            self._directory = default_dir
            self._directory_label.set(default_dir)
        self._on_mode_changed()

    def validate(self) -> ty.Optional[str]:
        if self.output_mode in FFMPEG_OUTPUT_MODES and not self._ffmpeg_available:
            return (
                "The selected output mode requires ffmpeg, which was not found. "
                "Install ffmpeg or choose another output mode."
            )
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
        get_overrides: ty.Optional[ty.Callable[[], ty.Dict[str, ty.Any]]] = None,
    ):
        """`get_overrides` returns the settings from Advanced Mode (start/end time,
        regions) that will be applied to the scan, so they can be listed here."""
        self.frame = ttk.Frame(root)
        self._videos_step = videos_step
        self._preset_step = preset_step
        self._output_step = output_step
        self._get_overrides = get_overrides
        self._summary = tk.Label(self.frame, justify=tk.LEFT, anchor=tk.NW)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self._summary.grid(row=0, column=0, sticky=tk.NSEW, padx=PADDING, pady=PADDING)

    def on_show(self):
        # Ensure output step has populated its default directory if the user jumped here.
        self._output_step.on_show()
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
        lines += self._override_lines()
        self._summary["text"] = "\n".join(lines)

    def _override_lines(self) -> ty.List[str]:
        overrides = self._get_overrides() if self._get_overrides is not None else {}
        if not overrides:
            return []
        lines = ["", "From Advanced Mode:"]
        if "start-time" in overrides:
            lines.append(f"    Start Time: {overrides['start-time']}")
        if "end-time" in overrides:
            lines.append(f"    End Time: {overrides['end-time']}")
        if "regions" in overrides:
            lines.append(f"    Regions: {len(overrides['regions'])}")
        return lines

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
    `Application`, which provides callbacks for switching back to Advanced Mode. The
    scan runs in-place on the final step rather than in a separate window."""

    # Defaults for state set in `__init__`. They exist for tests, which build bare instances
    # with `__new__` and set only the attributes the method under test reads.
    _scanning = False
    _browse_in_progress = False
    _scan_index = -1
    _get_scan_overrides = None

    def __init__(
        self,
        root: tk.Tk,
        settings: ScanSettings,
        on_close: ty.Callable[[], None],
        on_switch_to_advanced: ty.Callable[[ty.List[str]], None],
        on_preset_applied: ty.Callable[[presets.Preset, ConfigRegistry], None],
        startup_mode_var: tk.StringVar,
        on_startup_mode_changed: ty.Callable[[], None],
        active_preset: ty.Optional[str] = presets.DEFAULT_PRESET_NAME,
        on_load_config: ty.Optional[ty.Callable[[str], bool]] = None,
        get_scan_overrides: ty.Optional[
            ty.Callable[[str, ty.Optional[ty.Tuple[int, int]]], ty.Dict[str, ty.Any]]
        ] = None,
    ):
        """`active_preset` is the preset `settings` corresponds to, if any (see
        `_PresetStep`). `on_load_config` loads a config file dropped onto the wizard and
        syncs the wizard from it, returning True on success. `get_scan_overrides` returns
        the settings made in Advanced Mode that the wizard has no controls for (start/end
        time, regions), given the first input video and its resolution (w, h)."""
        self._settings = settings
        self._on_close = on_close
        self._on_switch_to_advanced = on_switch_to_advanced
        self._get_scan_overrides = get_scan_overrides
        # Shared with the Advanced Mode window so both Startup Mode menus stay in sync.
        self._startup_mode_var = startup_mode_var
        self._on_startup_mode_changed = on_startup_mode_changed
        self._scan_view: ty.Optional[ScanProgressView] = None
        self._scanning = False
        self._browse_in_progress = False
        self._last_output_dir: ty.Optional[str] = None

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

        videos_step = _VideosStep(
            content,
            self._window,
            on_browse=self._browse_videos,
            can_accept_drop=self._can_modify_videos,
            on_load_config=on_load_config,
        )
        preset_step = _PresetStep(
            content, on_preset_applied, base_config=settings.config, active_preset=active_preset
        )
        output_step = _OutputStep(content, videos_step=videos_step, settings=settings)
        summary_step = _SummaryStep(
            content, videos_step, preset_step, output_step, get_overrides=self._scan_overrides
        )
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
        self._videos_step._on_state_changed = self._on_videos_state_changed

        buttons = ttk.Frame(self._window)
        buttons.grid(row=3, column=0, sticky=tk.EW, padx=PADDING, pady=PADDING)
        buttons.columnconfigure(1, weight=1)

        self._advanced_button = ttk.Button(buttons, text="Advanced Mode", command=self._on_switch)
        self._advanced_button.grid(row=0, column=0, sticky=tk.W)
        self._back_button = ttk.Button(buttons, text="< Back", command=self._on_back)
        self._back_button.grid(row=0, column=2, padx=(PADDING, 0))
        self._open_dir_button = ttk.Button(
            buttons, text="Open Output Folder", command=self._on_open_output_dir
        )
        self._open_dir_button.grid(row=0, column=3, padx=(PADDING, 0))
        self._open_dir_button.grid_remove()
        self._save_report_button = ttk.Button(
            buttons, text="Save Report...", command=self._on_save_report
        )
        self._save_report_button.grid(row=0, column=4, padx=(PADDING, 0))
        self._save_report_button.grid_remove()
        self._new_scan_button = ttk.Button(buttons, text="New Scan", command=self._on_new_scan)
        self._new_scan_button.grid(row=0, column=5, padx=(PADDING, 0))
        self._new_scan_button.grid_remove()
        self._next_button = ttk.Button(buttons, text="Next >", command=self._on_next)
        self._next_button.grid(row=0, column=6, padx=(PADDING, 0))
        self._stop_button = ttk.Button(buttons, text="Stop", command=self._on_stop)
        self._stop_button.grid(row=0, column=6, padx=(PADDING, 0))
        self._stop_button.grid_remove()

        self._show_step(0)

    @property
    def videos(self) -> ty.List[str]:
        return self._videos_step.input_area.videos

    @property
    def window(self) -> tk.Toplevel:
        return self._window

    @property
    def is_visible(self) -> bool:
        """True if the wizard window exists and is not withdrawn."""
        try:
            return bool(self._window.winfo_exists()) and self._window.state() != "withdrawn"
        except tk.TclError:
            return False

    def _scan_overrides(self) -> ty.Dict[str, ty.Any]:
        """Settings made in Advanced Mode (start/end time, regions) to apply to a scan of
        the wizard's videos. Empty if there are no videos or no Advanced Mode settings."""
        get_overrides = self._get_scan_overrides
        videos = self.videos
        if get_overrides is None or not videos:
            return {}
        return get_overrides(videos[0], self._videos_step.input_area.first_video_resolution)

    def _can_modify_videos(self) -> bool:
        return not self._scanning and self._step_index != self._scan_index

    def _list_shortcuts_active(self) -> bool:
        """True if the Select All, Remove Selected keyboard shortcuts are active and should
        act: on the videos step, while videos can be modified, and not while a text entry
        has focus (so Ctrl+A / Delete keep their usual text-editing meaning there)."""
        if self._step_index != 0 or not self._can_modify_videos():
            return False
        if self._browse_in_progress:
            return False
        try:
            widget = self._window.focus_get()
        except (KeyError, tk.TclError):
            # focus_get() can fail when focus is on a menu or a window Tkinter doesn't know.
            widget = None
        if widget is not None:
            try:
                if widget.winfo_class() in TEXT_ENTRY_CLASSES:
                    return False
            except tk.TclError:
                pass
        return True

    def _on_select_all(self, _event=None) -> ty.Optional[str]:
        if not self._list_shortcuts_active():
            return None
        self._videos_step.input_area.select_all()
        return "break"

    def _on_remove_selected(self, _event=None) -> ty.Optional[str]:
        if not self._list_shortcuts_active():
            return None
        self._videos_step.input_area.remove_selected()
        return "break"

    def _on_videos_state_changed(self):
        self._refresh_form_nav_state()
        if self._step_index == 0:
            self._update_header()
        # Keep the summary or default output directory up to date if the video list changed
        # while viewing Step 3 or Step 4.
        if self._step_index in (self._summary_index - 1, self._summary_index):
            self._steps[self._step_index].on_show()

    def set_videos(self, paths: ty.List[str]):
        """Sync the wizard's video list to match `paths`."""
        if self.videos != paths:
            self._videos_step.input_area.clear()
            for path in paths:
                self._videos_step.input_area.add_video(path)
        self._refresh_form_nav_state()

    def sync_from_settings(
        self,
        settings: ScanSettings,
        active_preset: ty.Optional[str] = None,
        config: ty.Optional[ConfigRegistry] = None,
    ):
        """Sync wizard preset, threshold, and output choices from Advanced Mode settings.
        `config`, if given, replaces the wizard's base config (see `_PresetStep`)."""
        self._preset_step.sync_from_settings(settings, active_preset=active_preset, config=config)
        self._output_step.sync_from_settings(settings)
        if self._step_index == self._summary_index:
            self._steps[self._summary_index].on_show()

    def apply_to_advanced(self, motion_window, output_area, scan_area):
        """Copy the wizard's current threshold and output choices into Advanced Mode."""
        motion_window._threshold.set(str(self._preset_step.threshold))
        scan_area.scan_only = self._output_step.scan_only
        if self._output_step.output_mode is not None:
            output_area._output_mode = self._output_step.output_mode
            output_area._on_mode_combo_selected()
        # Only a folder the user chose: copying one auto-filled from the first video would
        # come back via `sync_from_settings` as a sticky user choice, so it would no longer
        # follow the input videos.
        if self._output_step.directory and self._output_step.user_selected_directory:
            output_area._output_dir = self._output_step.directory

    def show(self):
        self._window.deiconify()
        self._window.focus()

    def hide(self):
        self._window.withdraw()

    def shutdown(self):
        """Stop any in-progress scan. Called when the application is shutting down."""
        if self._scan_view is not None:
            self._scan_view.stop()

    def _update_header(self):
        index = self._step_index
        step = self._steps[index]
        total_form_steps = self._summary_index + 1
        # On Step 1 when no videos are loaded yet, the large drop-zone CTA already labels
        # the landing screen, so suppress the header until videos are added.
        if index == 0 and not self.videos:
            self._header.grid_remove()
            return
        if index <= self._summary_index:
            self._header["text"] = f"Step {index + 1} of {total_form_steps}: {step.title}"
        elif self._scanning:
            self._header["text"] = "Scanning..."
        else:
            self._header["text"] = "Scan Results"
        self._header.grid()

    def _show_step(self, index: int):
        self._step_index = index
        step = self._steps[index]
        step.on_show()
        for other in self._steps:
            other.frame.grid_remove()
        step.frame.grid()
        self._update_header()
        # The scan step manages its own navigation buttons via the scan lifecycle.
        if index == self._scan_index:
            return
        self._show_form_nav()

    def _show_form_nav(self):
        self._stop_button.grid_remove()
        self._open_dir_button.grid_remove()
        self._save_report_button.grid_remove()
        self._new_scan_button.grid_remove()
        self._next_button.grid()
        self._refresh_form_nav_state()

    def _refresh_form_nav_state(self):
        if self._scanning or self._browse_in_progress or self._step_index == self._scan_index:
            return
        self._advanced_button["state"] = tk.NORMAL
        self._back_button["state"] = tk.NORMAL if self._step_index > 0 else tk.DISABLED
        can_advance = self._step_index > 0 or bool(self.videos)
        self._next_button["state"] = tk.NORMAL if can_advance else tk.DISABLED
        self._next_button["text"] = (
            "Start Scan" if self._step_index == self._summary_index else "Next >"
        )

    def _set_form_nav_enabled(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in (
            self._advanced_button,
            self._back_button,
            self._next_button,
        ):
            button["state"] = state

    def _show_scanning_nav(self):
        self._next_button.grid_remove()
        self._open_dir_button.grid_remove()
        self._save_report_button.grid_remove()
        self._new_scan_button.grid_remove()
        self._stop_button.grid()
        self._stop_button["state"] = tk.NORMAL
        self._advanced_button["state"] = tk.DISABLED
        self._back_button["state"] = tk.DISABLED

    def _show_report_nav(self):
        self._stop_button.grid_remove()
        self._next_button.grid_remove()
        self._advanced_button["state"] = tk.NORMAL
        self._back_button["state"] = tk.NORMAL
        view = self._scan_view
        completed = (
            view is not None
            and view.error is None
            and not view.was_stopped
            and view.result is not None
        )
        if completed and self._last_output_dir:
            self._open_dir_button.grid()
        else:
            self._open_dir_button.grid_remove()
        if completed:
            self._save_report_button.grid()
        else:
            self._save_report_button.grid_remove()
        self._new_scan_button.grid()

    def _on_open_output_dir(self):
        if self._last_output_dir:
            open_path(self._last_output_dir)

    def _on_save_report(self):
        if self._scan_view is not None and self._scan_view.result is not None:
            save_report(self._window, self._scan_view.result.event_list)

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
        if self._browse_in_progress or self._scanning:
            return
        self.hide()
        self._on_switch_to_advanced(self.videos)

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
        if self._browse_in_progress or self._scanning:
            return
        if self._step_index == self._scan_index:
            return
        had_videos = bool(self.videos)
        self._browse_in_progress = True
        self._set_form_nav_enabled(False)
        try:
            self._videos_step.input_area.add_video(parent=self._window)
        finally:
            self._browse_in_progress = False
            if self._window.winfo_exists() and not self._scanning:
                self._on_videos_state_changed()
                if self._step_index == 0 and not had_videos and self.videos:
                    self._next_button.focus_set()

    def _create_menubar(self):
        self._menubar = MenuBar(self._window)
        if self._menubar.frame is not None:
            self._menubar.frame.grid(row=0, column=0, sticky=tk.EW)
        self._window.bind("<Control-o>", lambda _: self._browse_videos())
        self._window.bind("<Control-O>", lambda _: self._browse_videos())
        # Video list shortcuts. On Windows, Tk's <<SelectAll>> virtual event also maps to
        # Ctrl+A; when both match, Tk runs only the physical binding, so the handler fires
        # once per key press.
        for sequence in ("<<SelectAll>>", "<Control-a>", "<Control-A>"):
            self._window.bind(sequence, self._on_select_all)
        for sequence in ("<Delete>", "<BackSpace>"):
            self._window.bind(sequence, self._on_remove_selected)

        file_menu = self._menubar.add_menu("File", underline=0)
        file_menu.add_command(
            label="Open...",
            underline=0,
            command=self._browse_videos,
            accelerator="Ctrl+O",
        )
        file_menu.add_cascade(
            label="Sort",
            underline=0,
            menu=self._videos_step.input_area.build_sort_menu(file_menu),
        )
        file_menu.add_command(label="Advanced Mode", underline=0, command=self._on_switch)
        add_startup_mode_menu(file_menu, self._startup_mode_var, self._on_startup_mode_changed)
        file_menu.add_command(label="Quit", underline=0, command=self._on_quit)

        edit_menu = self._menubar.add_menu("Edit", underline=0)
        edit_menu.add_command(
            label="Select All",
            underline=0,
            command=self._on_select_all,
            accelerator=f"{ACCELERATOR_KEY}+A",
        )
        edit_menu.add_command(
            label="Remove Selected",
            underline=0,
            command=self._on_remove_selected,
            accelerator="Del",
        )

        fill_help_menu(self._menubar.add_menu("Help", underline=0), self._window)

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
        if self._output_step.directory and not self._output_step.scan_only:
            settings.set("output-dir", self._output_step.directory)
            self._last_output_dir = self._output_step.directory
        else:
            self._last_output_dir = None
        # Start/end time and regions set in Advanced Mode (the wizard has no controls for
        # them, and they are shown on the summary step).
        for key, value in self._scan_overrides().items():
            settings.set(key, value)
        finalize_output_names(settings, combine=False)
        logger.debug(f"wizard settings:\n{settings.app_settings}")

        try:
            view = ScanProgressView(self._scan_step.body, settings, self._on_scan_finished)
        except SCAN_SETUP_ERRORS as ex:
            show_scan_setup_error(ex, settings, parent=self._window)
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
        self._update_header()
        if view.error is not None:
            self._scan_step.set_content(self._build_error_panel(view.error))
        elif view.was_stopped or view.result is None:
            self._scan_step.set_content(self._build_stopped_panel(view))
        else:
            self._scan_step.set_content(self._build_report_panel(view))
        self._show_report_nav()

    def _on_new_scan(self):
        self._videos_step.input_area.clear()
        self._output_step.reset_default_directory()
        self._scan_step.set_content(None)
        self._scan_view = None
        self._last_output_dir = None
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
        return panel

    def _build_stopped_panel(self, view: ScanProgressView) -> ttk.Frame:
        return self._build_message_panel(
            "Scan stopped.",
            f"Stopped after processing {view.frames_processed} frames.",
        )

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
        return panel
