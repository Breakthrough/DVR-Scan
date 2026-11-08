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
    wizard._classic_button = _FakeButton()
    wizard._back_button = _FakeButton()
    wizard._next_button = _FakeButton()
    wizard._window = SimpleNamespace(winfo_exists=lambda: True)
    wizard._step_index = 0
    wizard._summary_index = 3
    wizard._scanning = False
    wizard._browse_in_progress = False

    states_during_dialog = {}
    videos = []

    def fake_add_video(parent=None):
        states_during_dialog["parent"] = parent
        states_during_dialog["classic"] = wizard._classic_button["state"]
        states_during_dialog["back"] = wizard._back_button["state"]
        states_during_dialog["next"] = wizard._next_button["state"]
        videos.append("sample.mp4")

    wizard._videos_step = SimpleNamespace(
        input_area=SimpleNamespace(add_video=fake_add_video, videos=videos)
    )

    wizard._browse_videos()

    assert states_during_dialog["parent"] == wizard._window
    assert states_during_dialog["classic"] == "disabled"
    assert states_during_dialog["back"] == "disabled"
    assert states_during_dialog["next"] == "disabled"
    assert wizard._browse_in_progress is False
    assert wizard._classic_button["state"] == "normal"
    assert wizard._back_button["state"] == "disabled"
    assert wizard._next_button["state"] == "normal"
    assert wizard._next_button["text"] == "Next >"
    assert wizard._next_button.focused is True


def test_wizard_next_is_disabled_until_videos_exist():
    wizard = ScanWizard.__new__(ScanWizard)
    wizard._classic_button = _FakeButton()
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
    wizard._classic_button = _FakeButton()
    wizard._back_button = _FakeButton()
    wizard._next_button = _FakeButton()
    wizard._classic_button["state"] = "disabled"
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
    assert wizard._classic_button["state"] == "disabled"
    assert wizard._back_button["state"] == "disabled"
    assert wizard._next_button["state"] == "disabled"

    # Should not re-enable buttons on _scan_index even after scan finishes
    wizard._scanning = False
    wizard._refresh_form_nav_state()
    assert wizard._classic_button["state"] == "disabled"
    assert wizard._back_button["state"] == "disabled"
    assert wizard._next_button["state"] == "disabled"


def test_wizard_on_switch_ignored_while_scanning():
    wizard = ScanWizard.__new__(ScanWizard)
    wizard._browse_in_progress = False
    wizard._scanning = True
    switched = []
    wizard._on_switch_to_classic = lambda videos: switched.append(videos)

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
    wizard._classic_button = _FakeButton()
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
    records the order of select_all / remove_selected / state-changed callbacks."""
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
    wizard._on_videos_state_changed = lambda: calls.append("state_changed")
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
    assert wizard.calls == ["select_all", "remove_selected", "state_changed"]


def test_wizard_select_all_calls_input_area_and_breaks():
    wizard = _shortcut_wizard()

    assert wizard._on_select_all(object()) == "break"
    assert wizard.calls == ["select_all"]


def test_wizard_remove_selected_removes_then_refreshes_state_and_breaks():
    wizard = _shortcut_wizard()

    assert wizard._on_remove_selected(object()) == "break"
    assert wizard.calls == ["remove_selected", "state_changed"]
