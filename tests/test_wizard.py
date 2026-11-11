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

"""Tests for the Scan Wizard UI helpers."""

from types import SimpleNamespace

import pytest

from dvr_scan.app.application import InputArea
from dvr_scan.app.wizard import ScanWizard


class _FakeButton:
    def __init__(self):
        self.values = {}
        self.focused = False

    def __setitem__(self, key, value):
        self.values[key] = value

    def __getitem__(self, key):
        return self.values[key]

    def focus_set(self):
        self.focused = True


class _FakeTree:
    def __init__(self, row):
        self._row = row

    def get_children(self):
        return ["row-1"]

    def item(self, item):
        return {"values": self._row}


def test_input_area_add_video_forwards_parent_to_dialog(monkeypatch):
    area = InputArea.__new__(InputArea)
    seen = {}

    def fake_askopenfilename(**kwargs):
        seen.update(kwargs)
        return ()

    monkeypatch.setattr(
        "dvr_scan.app.application.tkinter.filedialog.askopenfilename", fake_askopenfilename
    )

    InputArea.add_video(area, parent="wizard-parent")

    assert seen["parent"] == "wizard-parent"
    assert seen["multiple"] is True


def test_input_area_videos_reads_path_from_new_column_order():
    area = InputArea.__new__(InputArea)
    area._videos = _FakeTree(
        ["00:00:01.000", "30", "640 x 480", "2026-06-13 12:00:00", "/tmp/a.mp4"]
    )

    assert area.videos == ["/tmp/a.mp4"]


def test_wizard_browse_videos_disables_navigation_until_dialog_returns():
    wizard = ScanWizard.__new__(ScanWizard)
    wizard._advanced_button = _FakeButton()
    wizard._back_button = _FakeButton()
    wizard._next_button = _FakeButton()
    wizard._window = SimpleNamespace(winfo_exists=lambda: True)
    wizard._step_index = 0
    wizard._summary_index = 3
    wizard._scanning = False
    wizard._browse_in_progress = False
    wizard._update_header = lambda: None

    states_during_dialog = {}
    videos = []

    def fake_add_video(parent=None):
        states_during_dialog["parent"] = parent
        states_during_dialog["advanced"] = wizard._advanced_button["state"]
        states_during_dialog["back"] = wizard._back_button["state"]
        states_during_dialog["next"] = wizard._next_button["state"]
        videos.append("sample.mp4")

    wizard._videos_step = SimpleNamespace(
        input_area=SimpleNamespace(add_video=fake_add_video, videos=videos)
    )

    wizard._browse_videos()

    assert states_during_dialog["parent"] == wizard._window
    assert states_during_dialog["advanced"] == "disabled"
    assert states_during_dialog["back"] == "disabled"
    assert states_during_dialog["next"] == "disabled"
    assert wizard._browse_in_progress is False
    assert wizard._advanced_button["state"] == "normal"
    assert wizard._back_button["state"] == "disabled"
    assert wizard._next_button["state"] == "normal"
    assert wizard._next_button["text"] == "Next >"
    assert wizard._next_button.focused is True


def test_wizard_next_is_disabled_until_videos_exist():
    wizard = ScanWizard.__new__(ScanWizard)
    wizard._advanced_button = _FakeButton()
    wizard._back_button = _FakeButton()
    wizard._next_button = _FakeButton()
    wizard._step_index = 0
    wizard._summary_index = 3
    wizard._videos_step = SimpleNamespace(input_area=SimpleNamespace(videos=[]))

    wizard._refresh_form_nav_state()

    assert wizard._next_button["state"] == "disabled"

    wizard._videos_step.input_area.videos.append("sample.mp4")
    wizard._refresh_form_nav_state()

    assert wizard._next_button["state"] == "normal"


def test_wizard_refresh_form_nav_state_noop_during_scan_or_on_scan_step():
    wizard = ScanWizard.__new__(ScanWizard)
    wizard._advanced_button = _FakeButton()
    wizard._back_button = _FakeButton()
    wizard._next_button = _FakeButton()
    wizard._advanced_button["state"] = "disabled"
    wizard._back_button["state"] = "disabled"
    wizard._next_button["state"] = "disabled"
    wizard._summary_index = 3
    wizard._scan_index = 4
    wizard._videos_step = SimpleNamespace(input_area=SimpleNamespace(videos=["sample.mp4"]))

    # Should not re-enable buttons while _scanning is True
    wizard._step_index = 4
    wizard._browse_in_progress = False
    wizard._scanning = True
    wizard._browse_in_progress = False
    wizard._refresh_form_nav_state()
    assert wizard._advanced_button["state"] == "disabled"
    assert wizard._back_button["state"] == "disabled"
    assert wizard._next_button["state"] == "disabled"

    # Should not re-enable buttons on _scan_index even after scan finishes
    wizard._scanning = False
    wizard._refresh_form_nav_state()
    assert wizard._advanced_button["state"] == "disabled"
    assert wizard._back_button["state"] == "disabled"
    assert wizard._next_button["state"] == "disabled"


def test_wizard_on_switch_ignored_while_scanning():
    wizard = ScanWizard.__new__(ScanWizard)
    wizard._browse_in_progress = False
    wizard._scanning = True
    switched = []
    wizard._on_switch_to_advanced = lambda videos: switched.append(videos)

    wizard._on_switch()

    assert switched == []


def test_wizard_set_videos_replaces_when_changed():
    wizard = ScanWizard.__new__(ScanWizard)
    current = ["a.mp4", "b.mp4"]
    calls = []

    class FakeInputArea:
        @property
        def videos(self):
            return list(current)

        def clear(self):
            calls.append(("clear",))
            current.clear()

        def add_video(self, path):
            calls.append(("add", path))
            current.append(path)

    wizard._videos_step = SimpleNamespace(input_area=FakeInputArea())
    wizard._step_index = 0
    wizard._summary_index = 3
    wizard._scan_index = 4
    wizard._scanning = False
    wizard._browse_in_progress = False
    wizard._advanced_button = _FakeButton()
    wizard._back_button = _FakeButton()
    wizard._next_button = _FakeButton()

    # Identical list does not clear/reload
    wizard.set_videos(["a.mp4", "b.mp4"])
    assert calls == []

    # Removed/reordered list replaces existing videos
    wizard.set_videos(["b.mp4"])
    assert calls == [("clear",), ("add", "b.mp4")]
    assert current == ["b.mp4"]


def test_wizard_can_modify_videos_blocks_during_scan_and_on_scan_step():
    wizard = ScanWizard.__new__(ScanWizard)
    wizard._scan_index = 4
    wizard._step_index = 0
    wizard._scanning = False
    wizard._browse_in_progress = False

    assert wizard._can_modify_videos() is True

    wizard._browse_in_progress = False
    wizard._scanning = True
    assert wizard._can_modify_videos() is False

    wizard._scanning = False
    wizard._step_index = 4
    assert wizard._can_modify_videos() is False


def test_spinbox_and_timecode_entry_get_refreshes_before_returning():
    from dvr_scan.app.widgets import Spinbox, TimecodeEntry

    for cls in (Spinbox, TimecodeEntry):
        widget = cls.__new__(cls)
        refreshed = []
        widget._refresh = lambda r=refreshed: r.append(True)
        widget._value = SimpleNamespace(get=lambda: "42")
        assert widget.get() == "42"
        assert refreshed == [True]


def test_preset_step_ignores_noop_selection(monkeypatch):
    import dvr_scan.presets as presets
    from dvr_scan.app.wizard import _PresetStep
    from dvr_scan.config import ConfigRegistry

    step = _PresetStep.__new__(_PresetStep)
    step.config = ConfigRegistry()
    step._presets = {p.name: p for p in presets.list_presets()}
    step._active_preset = presets.DEFAULT_PRESET_NAME
    selected_name = [presets.DEFAULT_PRESET_NAME]
    step._combo = SimpleNamespace(
        selection_clear=lambda: None,
        get=lambda: selected_name[0],
        set=lambda val: selected_name.__setitem__(0, val),
    )
    threshold_val = [str(step.config.get("threshold"))]
    step._threshold = SimpleNamespace(
        get=lambda: threshold_val[0],
        set=lambda val: threshold_val.__setitem__(0, val),
    )
    step._preset_desc = {}
    applied = []
    step._on_preset_applied = lambda preset, cfg: applied.append(preset.name)

    loads = []
    orig_load = presets.load_preset

    def tracked_load(preset):
        loads.append(preset.name)
        return orig_load(preset)

    monkeypatch.setattr(presets, "load_preset", tracked_load)

    # Re-selecting the already active preset with unchanged threshold is a no-op.
    step._on_selected()
    assert loads == []
    assert applied == []

    # Switching to a different preset loads and applies it.
    selected_name[0] = "Fast Scan"
    step._on_selected()
    assert loads == ["Fast Scan"]
    assert applied == ["Fast Scan"]
    assert step._active_preset == "Fast Scan"

    # Modifying threshold makes re-selecting the same preset reload it.
    threshold_val[0] = "0.99"
    step._on_selected()
    assert loads == ["Fast Scan", "Fast Scan"]
    assert applied == ["Fast Scan", "Fast Scan"]
    assert float(threshold_val[0]) == float(step.config.get("threshold"))


# --- Video list shortcuts (Select All / Remove Selected) ----------------------------------


class _FocusWidget:
    def __init__(self, widget_class: str):
        self._widget_class = widget_class

    def winfo_class(self):
        return self._widget_class


def _shortcut_wizard(focus=None, focus_error=None):
    """A Tk-free wizard on the videos step with recording list-shortcut stubs. `calls`
    records the order of select_all / remove_selected calls. (The list itself notifies the
    wizard of changes through `VideoList.on_changed`.)"""
    wizard = ScanWizard.__new__(ScanWizard)
    wizard._step_index = 0
    wizard._scan_index = 4
    wizard._summary_index = 3
    wizard._scanning = False
    wizard._browse_in_progress = False

    def focus_get():
        if focus_error is not None:
            raise focus_error
        return focus

    wizard._window = SimpleNamespace(focus_get=focus_get)
    calls = []
    wizard._videos_step = SimpleNamespace(
        input_area=SimpleNamespace(
            select_all=lambda: calls.append("select_all"),
            remove_selected=lambda: calls.append("remove_selected"),
            videos=["a.mp4"],
        )
    )
    wizard.calls = calls
    return wizard


def _assert_shortcuts_inactive(wizard):
    assert wizard._on_select_all() is None
    assert wizard._on_remove_selected(object()) is None
    assert wizard.calls == []


def test_wizard_list_shortcuts_ignored_off_videos_step():
    wizard = _shortcut_wizard()
    wizard._step_index = 1

    _assert_shortcuts_inactive(wizard)


def test_wizard_list_shortcuts_ignored_while_scanning():
    wizard = _shortcut_wizard()
    wizard._scanning = True

    _assert_shortcuts_inactive(wizard)


def test_wizard_list_shortcuts_ignored_on_scan_step():
    wizard = _shortcut_wizard()
    # Degenerate layout where the scan step is index 0, so only _can_modify_videos() blocks.
    wizard._scan_index = 0

    _assert_shortcuts_inactive(wizard)


def test_wizard_list_shortcuts_ignored_while_browse_dialog_open():
    wizard = _shortcut_wizard()
    wizard._browse_in_progress = True

    _assert_shortcuts_inactive(wizard)


def test_wizard_list_shortcuts_ignored_when_text_entry_focused():
    wizard = _shortcut_wizard(focus=_FocusWidget("TEntry"))

    _assert_shortcuts_inactive(wizard)


def test_wizard_list_shortcuts_ignored_for_every_text_entry_class():
    from dvr_scan.app.wizard import TEXT_ENTRY_CLASSES

    for widget_class in TEXT_ENTRY_CLASSES:
        wizard = _shortcut_wizard(focus=_FocusWidget(widget_class))
        _assert_shortcuts_inactive(wizard)


def test_wizard_list_shortcuts_active_when_non_entry_widget_focused():
    wizard = _shortcut_wizard(focus=_FocusWidget("TButton"))

    assert wizard._on_select_all() == "break"
    assert wizard.calls == ["select_all"]


def test_wizard_list_shortcuts_active_when_focus_get_raises_key_error():
    wizard = _shortcut_wizard(focus_error=KeyError("popdown"))

    assert wizard._on_select_all() == "break"
    assert wizard._on_remove_selected() == "break"
    assert wizard.calls == ["select_all", "remove_selected"]


def test_wizard_select_all_calls_input_area_and_breaks():
    wizard = _shortcut_wizard()

    assert wizard._on_select_all(object()) == "break"
    assert wizard.calls == ["select_all"]


def test_wizard_remove_selected_calls_input_area_and_breaks():
    wizard = _shortcut_wizard()

    assert wizard._on_remove_selected(object()) == "break"
    assert wizard.calls == ["remove_selected"]


# --- Preset step initial selection --------------------------------------------------------


class _FakeCombo:
    """Stand-in for the preset ttk.Combobox: tracks the selection and item config."""

    def __init__(self):
        self.value = ""
        self.config = {}

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def __setitem__(self, key, value):
        self.config[key] = value


def _preset_step_for_on_show(active_preset):
    from dvr_scan.app.wizard import _PresetStep

    step = _PresetStep.__new__(_PresetStep)
    step._active_preset = active_preset
    step._combo_initialized = False
    step._presets = {}
    step._combo = _FakeCombo()
    step._preset_desc = {"text": ""}
    return step


def test_preset_step_shows_default_on_first_show():
    step = _preset_step_for_on_show("Default")
    step.on_show()
    assert step._combo.get() == "Default"
    assert "Default" in step._combo.config["values"]
    assert step._preset_desc["text"].startswith("Balanced")


def test_preset_step_shows_custom_when_no_active_preset():
    step = _preset_step_for_on_show(None)
    step.on_show()
    assert step._combo.get() == ""
    assert step._active_preset is None
    assert step._preset_desc["text"].startswith("Custom settings")


def test_preset_step_on_show_keeps_user_selection_after_first_show():
    step = _preset_step_for_on_show("Default")
    step.on_show()
    step._combo.set("Fast Scan")
    step._active_preset = "Fast Scan"
    step.on_show()
    assert step._combo.get() == "Fast Scan"


# --- Output step without ffmpeg (B4) ------------------------------------------------------


class _FakeModeCombo:
    """Stand-in for the output mode ttk.Combobox."""

    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def get(self):
        return self.values[self.index]

    def current(self, index):
        self.index = index

    def selection_clear(self):
        pass


def _output_step(ffmpeg_available: bool, mode_index: int = 0, directory: str = "/out"):
    from dvr_scan.app.wizard import _OutputStep

    step = _OutputStep.__new__(_OutputStep)
    step._ffmpeg_available = ffmpeg_available
    step._modes = _OutputStep.mode_choices(ffmpeg_available)
    step._mode_combo = _FakeModeCombo(label for label, _ in step._modes)
    step._mode_combo.current(mode_index)
    step._directory = directory
    step._user_selected_dir = bool(directory)
    step._select_button = {}
    step._directory_label = SimpleNamespace(set=lambda _value: None)
    return step


def test_output_mode_choices_label_ffmpeg_modes_when_missing():
    from dvr_scan.app.wizard import FFMPEG_MISSING_SUFFIX, FFMPEG_OUTPUT_MODES, _OutputStep
    from dvr_scan.scanner import OutputMode

    assert _OutputStep.mode_choices(True) == _OutputStep._MODES
    choices = _OutputStep.mode_choices(False)
    assert [mode for _, mode in choices] == [mode for _, mode in _OutputStep._MODES]
    for label, mode in choices:
        assert label.endswith(FFMPEG_MISSING_SUFFIX) == (mode in FFMPEG_OUTPUT_MODES)
        assert "Recommended" not in label or mode not in FFMPEG_OUTPUT_MODES
    assert dict(choices)[next(lbl for lbl, m in choices if m == OutputMode.OPENCV)] == (
        OutputMode.OPENCV
    )


def test_output_step_rejects_ffmpeg_modes_without_ffmpeg():
    from dvr_scan.app.wizard import FFMPEG_OUTPUT_MODES
    from dvr_scan.scanner import OutputMode

    for index in range(5):
        step = _output_step(ffmpeg_available=False, mode_index=index)
        error = step.validate()
        if step.output_mode in FFMPEG_OUTPUT_MODES:
            assert error is not None and "ffmpeg" in error
        else:
            assert error is None
    # With ffmpeg, the default (MP4) mode is fine.
    step = _output_step(ffmpeg_available=True, mode_index=0)
    assert step.output_mode == OutputMode.ENCODE
    assert step.validate() is None


def test_output_step_sync_falls_back_to_opencv_without_ffmpeg():
    from dvr_scan.config import ConfigRegistry
    from dvr_scan.scanner import OutputMode
    from dvr_scan.shared import ScanSettings

    for config_text in ("", "output-mode = ffmpeg\n"):
        config = ConfigRegistry()
        if config_text:
            config.load_from_string(config_text)
        step = _output_step(ffmpeg_available=False, mode_index=4)
        step.sync_from_settings(ScanSettings(args=None, config=config))
        assert step.output_mode == OutputMode.OPENCV
        assert step.validate() is None


# --- Dialog parents (S3e) -----------------------------------------------------------------


def test_output_step_select_dialog_is_parented(monkeypatch):
    step = _output_step(ffmpeg_available=True, directory="")
    step.frame = SimpleNamespace(winfo_toplevel=lambda: "wizard-window")
    seen = {}

    def fake_askdirectory(**kwargs):
        seen.update(kwargs)
        return "/chosen"

    monkeypatch.setattr("dvr_scan.app.wizard.tkinter.filedialog.askdirectory", fake_askdirectory)
    step._on_select()
    assert seen["parent"] == "wizard-window"
    assert step.directory == "/chosen" and step.user_selected_directory


def test_preset_load_failure_dialog_is_parented(monkeypatch):
    import dvr_scan.presets as presets
    from dvr_scan.app.wizard import _PresetStep
    from dvr_scan.config import ConfigLoadFailure, ConfigRegistry

    step = _PresetStep.__new__(_PresetStep)
    step.frame = SimpleNamespace(winfo_toplevel=lambda: "wizard-window")
    step.config = ConfigRegistry()
    step._presets = {p.name: p for p in presets.list_presets()}
    step._active_preset = presets.DEFAULT_PRESET_NAME
    selected = ["Fast Scan"]
    step._combo = SimpleNamespace(
        selection_clear=lambda: None,
        get=lambda: selected[0],
        set=lambda value: selected.__setitem__(0, value),
    )
    step._threshold = SimpleNamespace(get=lambda: str(step.config.get("threshold")))

    def failing_load(_preset):
        raise ConfigLoadFailure(init_log=[])

    shown = []
    monkeypatch.setattr(presets, "load_preset", failing_load)
    monkeypatch.setattr(
        "dvr_scan.app.wizard.tkinter.messagebox.showerror", lambda **kwargs: shown.append(kwargs)
    )
    step._on_selected()
    assert shown[0]["parent"] == "wizard-window"
    assert selected[0] == presets.DEFAULT_PRESET_NAME


# --- Dropping a config file on the wizard (S3c) -------------------------------------------


def _videos_step_for_drop(on_load_config):
    from dvr_scan.app.wizard import _VideosStep

    step = _VideosStep.__new__(_VideosStep)
    step._window = "wizard-window"
    step._can_accept_drop = None
    step._on_load_config = on_load_config
    step._set_drag_active = lambda _active: None
    step._drop_zone = SimpleNamespace(tk=SimpleNamespace(splitlist=lambda data: data))
    added = []
    step.input_area = SimpleNamespace(add_video=lambda path, parent: added.append(path))
    return step, added


def test_wizard_drop_loads_config_files_and_adds_videos(tmp_path):
    video = tmp_path / "a.mp4"
    first_cfg = tmp_path / "one.CFG"
    second_cfg = tmp_path / "two.cfg"
    for path in (video, first_cfg, second_cfg):
        path.write_text("")
    loaded = []
    step, added = _videos_step_for_drop(lambda path: loaded.append(path) or True)
    step._on_drop(SimpleNamespace(data=[str(first_cfg), str(video), str(second_cfg)]))
    # Only the first config file is loaded, and none are added as videos.
    assert loaded == [str(first_cfg)]
    assert added == [str(video)]


def test_wizard_drop_tries_next_config_if_first_fails(tmp_path):
    bad_cfg, good_cfg = tmp_path / "bad.cfg", tmp_path / "good.cfg"
    for path in (bad_cfg, good_cfg):
        path.write_text("")
    loaded = []
    step, added = _videos_step_for_drop(
        lambda path: loaded.append(path) or path.endswith("good.cfg")
    )
    step._on_drop(SimpleNamespace(data=[str(bad_cfg), str(good_cfg)]))
    assert loaded == [str(bad_cfg), str(good_cfg)]
    assert added == []


# --- Output folder only copied to Advanced Mode if chosen by the user (S3h) ---------------


def _wizard_for_apply(directory: str, user_selected: bool):
    from dvr_scan.scanner import OutputMode

    wizard = ScanWizard.__new__(ScanWizard)
    wizard._preset_step = SimpleNamespace(threshold=0.15)
    wizard._output_step = SimpleNamespace(
        scan_only=False,
        output_mode=OutputMode.OPENCV,
        directory=directory,
        user_selected_directory=user_selected,
    )
    motion = SimpleNamespace(_threshold=SimpleNamespace(set=lambda _value: None))
    output = SimpleNamespace(_output_dir="", _on_mode_combo_selected=lambda: None)
    scan = SimpleNamespace(scan_only=None)
    return wizard, motion, output, scan


def test_apply_to_advanced_skips_auto_filled_output_dir():
    wizard, motion, output, scan = _wizard_for_apply("/videos", user_selected=False)
    wizard.apply_to_advanced(motion, output, scan)
    assert output._output_dir == ""


def test_apply_to_advanced_copies_user_selected_output_dir():
    wizard, motion, output, scan = _wizard_for_apply("/chosen", user_selected=True)
    wizard.apply_to_advanced(motion, output, scan)
    assert output._output_dir == "/chosen"


# --- Advanced Mode start/end time and regions in wizard scans (S3f) -----------------------


def test_wizard_scan_overrides_use_first_video_and_resolution():
    wizard = ScanWizard.__new__(ScanWizard)
    calls = []
    wizard._get_scan_overrides = lambda video, size: calls.append((video, size)) or {"x": 1}
    wizard._videos_step = SimpleNamespace(
        input_area=SimpleNamespace(videos=["a.mp4", "b.mp4"], first_video_resolution=(64, 48))
    )
    assert wizard._scan_overrides() == {"x": 1}
    assert calls == [("a.mp4", (64, 48))]
    # No videos, or no Advanced Mode window: nothing to apply.
    wizard._videos_step.input_area.videos = []
    assert wizard._scan_overrides() == {}
    wizard._get_scan_overrides = None
    wizard._videos_step.input_area.videos = ["a.mp4"]
    assert wizard._scan_overrides() == {}


def test_summary_lists_advanced_mode_overrides():
    from dvr_scan.app.wizard import _SummaryStep

    step = _SummaryStep.__new__(_SummaryStep)
    step._get_overrides = lambda: {
        "start-time": "00:00:02.000",
        "end-time": "00:00:05.000",
        "regions": [[1], [2]],
    }
    assert step._override_lines() == [
        "",
        "From Advanced Mode:",
        "    Start Time: 00:00:02.000",
        "    End Time: 00:00:05.000",
        "    Regions: 2",
    ]
    step._get_overrides = lambda: {}
    assert step._override_lines() == []
    step._get_overrides = None
    assert step._override_lines() == []


# --- Start Scan errors are shown (B4) -----------------------------------------------------


def _wizard_for_start_scan(overrides=None):
    from dvr_scan.config import ConfigRegistry

    wizard = ScanWizard.__new__(ScanWizard)
    wizard._settings = SimpleNamespace(args=None)
    wizard._preset_step = SimpleNamespace(config=ConfigRegistry(), threshold=0.15)

    def update(settings):
        settings.set("input", ["a.mp4"])
        return settings

    wizard._videos_step = SimpleNamespace(
        input_area=SimpleNamespace(update=update, videos=["a.mp4"], first_video_resolution=None)
    )
    wizard._output_step = SimpleNamespace(scan_only=True, output_mode=None, directory="")
    wizard._get_scan_overrides = (lambda _video, _size: overrides) if overrides else None
    wizard._scan_step = SimpleNamespace(body="scan-body")
    wizard._window = "wizard-window"
    wizard._scan_view = None
    wizard._scanning = False
    return wizard


def test_wizard_start_scan_shows_error_when_setup_fails(monkeypatch):
    import pytest
    from scenedetect import VideoOpenFailure

    import dvr_scan.app.wizard as wizard_module

    for error in (VideoOpenFailure("mismatched"), ValueError("no ffmpeg"), OSError("bad dir")):
        wizard = _wizard_for_start_scan()

        def failing_view(*_args, error=error):
            raise error

        shown = []
        monkeypatch.setattr(wizard_module, "ScanProgressView", failing_view)
        monkeypatch.setattr(
            wizard_module.tkinter.messagebox,
            "showerror",
            lambda shown=shown, **kwargs: shown.append(kwargs),
        )
        wizard._start_scan()
        assert len(shown) == 1, error
        assert shown[0]["parent"] == "wizard-window"
        assert str(error) in shown[0]["message"]
        assert wizard._scanning is False and wizard._scan_view is None

    # Anything else is a bug: it propagates to the release-mode error handler.
    def broken_view(*_args):
        raise RuntimeError("bug")

    monkeypatch.setattr(wizard_module, "ScanProgressView", broken_view)
    with pytest.raises(RuntimeError):
        _wizard_for_start_scan()._start_scan()


def test_wizard_start_scan_applies_advanced_mode_overrides(monkeypatch):
    import dvr_scan.app.wizard as wizard_module

    seen = {}

    def capture_view(_parent, settings, *_args):
        seen.update(settings.app_settings)
        raise ValueError("stop here")

    monkeypatch.setattr(wizard_module, "ScanProgressView", capture_view)
    monkeypatch.setattr(wizard_module.tkinter.messagebox, "showerror", lambda **kwargs: None)
    _wizard_for_start_scan({"start-time": "00:00:02.000", "regions": [["r"]]})._start_scan()
    assert seen["start-time"] == "00:00:02.000"
    assert seen["regions"] == [["r"]]
    assert seen["input"] == ["a.mp4"]


def test_preset_step_sync_replaces_config_with_loaded_config():
    """A config file dropped on the wizard replaces its base config, so options without
    an Advanced Mode control (only copied when already set) still take effect."""
    from dvr_scan.app.wizard import _PresetStep
    from dvr_scan.config import ConfigRegistry
    from dvr_scan.shared import ScanSettings

    step = _preset_step_for_on_show("Default")
    step._combo.set("Default")
    step.config = ConfigRegistry()
    threshold = ["0.15"]
    step._threshold = SimpleNamespace(set=lambda value: threshold.__setitem__(0, value))
    loaded = ConfigRegistry()
    loaded.load_from_string("min-event-length = 5s\nthreshold = 0.4\n")
    settings = ScanSettings(args=None, config=loaded)
    settings.set("threshold", 0.4)
    _PresetStep.sync_from_settings(step, settings, active_preset=None, config=loaded)
    assert step.config is not loaded
    assert not step.config.is_default("min-event-length")
    assert step.config.get("threshold") == 0.4
    assert threshold == ["0.4"]
    assert step._active_preset is None


@pytest.mark.parametrize("cnt_available", [True, False])
def test_fast_scan_preset_hidden_without_cnt(monkeypatch, cnt_available):
    """The Fast Scan preset uses CNT, which pip installs can lack (the regular OpenCV
    package overwrites the contrib build), so it is only offered when CNT works."""
    import dvr_scan.presets as presets_module

    monkeypatch.setattr(
        presets_module.SubtractorCNT, "is_available", staticmethod(lambda: cnt_available)
    )
    names = [preset.name for preset in presets_module.list_available_presets()]
    assert ("Fast Scan" in names) == cnt_available
    assert "High Sensitivity" in names and "Low Sensitivity" in names
