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

"""Tests for the classic application window's input area (Tk-free logic only)."""

import typing as ty

import numpy as np
import pytest
from scenedetect import VideoOpenFailure

import dvr_scan.app.application as application
from dvr_scan.app.application import NO_REGIONS_SPECIFIED_TEXT, InputArea
from dvr_scan.region import Point

SHAPES = [[Point(1, 1), Point(10, 1), Point(10, 10)]]


class _FakeTree:
    """Minimal stand-in for the ttk.Treeview holding the input list."""

    def __init__(self, paths: ty.List[str], resolutions: ty.Optional[ty.List[str]] = None):
        self.paths = paths
        self.resolutions = resolutions or ["64 x 48"] * len(paths)

    def get_children(self):
        return [f"row-{i}" for i in range(len(self.paths))]

    def item(self, item):
        index = int(item.split("-")[1])
        return {
            "values": [
                "00:00:01.000",
                "30",
                self.resolutions[index],
                "2026-01-01",
                self.paths[index],
            ]
        }


class _FakeVar:
    def __init__(self, value):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _FakeAppRoot:
    def focus(self):
        pass


class _FakeEditorRoot:
    def __init__(self):
        self.grabbed = 0

    def grab_set(self):
        self.grabbed += 1

    def grab_release(self):
        pass


class _FakeRegionEditor:
    """Records constructor arguments and exposes the same interface `InputArea` relies on."""

    instances: ty.List["_FakeRegionEditor"] = []
    prompt_result = True  # Return value of prompt_save_on_scan (False = user cancelled).

    def __init__(
        self, frame, initial_shapes, initial_scale, debug_mode, video_path, save_path, on_close=None
    ):
        self.frame = frame
        self.initial_shapes = initial_shapes
        self.video_path = video_path
        self._regions = list(initial_shapes) if initial_shapes else []
        self.on_close = on_close
        self.runs = 0
        self.prompted = 0
        self.persisted = True
        self.persisted_path = ""
        self._root = _FakeEditorRoot()
        _FakeRegionEditor.instances.append(self)

    @property
    def shapes(self):
        return self._regions

    def set_persisted(self, persisted, path=""):
        self.persisted = persisted
        self.persisted_path = path

    def prompt_save_on_scan(self, root=None):
        self.prompted += 1
        return _FakeRegionEditor.prompt_result

    def run(self, root=None):
        self.runs += 1


class _FakeVideo:
    def __init__(self, frame, frame_rate: float = 30.0, total_frames: int = 100):
        self._frame = frame
        self.frame_rate = frame_rate
        self.duration = type("_Dur", (), {"frame_num": total_frames})()
        self.seek_targets: ty.List[ty.Any] = []

    def seek(self, target):
        self.seek_targets.append(target)

    def read(self):
        if callable(self._frame):
            return self._frame(self.seek_targets[-1] if self.seek_targets else None)
        return self._frame


class _FakeSettings:
    def __init__(self):
        self.values = {}

    def set(self, key, value):
        self.values[key] = value


def _frame(width: int, height: int, fill: int) -> np.ndarray:
    return np.full((height, width, 3), fill, dtype=np.uint8)


@pytest.fixture
def area(monkeypatch) -> InputArea:
    _FakeRegionEditor.instances = []
    _FakeRegionEditor.prompt_result = True
    monkeypatch.setattr(application, "RegionEditor", _FakeRegionEditor)
    area = InputArea.__new__(InputArea)
    area._root = _FakeAppRoot()
    area._region_editor = None
    area._region_editor_video = None
    area._region_editor_size = None
    area._region_editor_start_time = None
    area._regions = []
    area._current_region = _FakeVar(NO_REGIONS_SPECIFIED_TEXT)
    area._set_region = _FakeVar(True)
    area._set_time = _FakeVar(False)
    area._start_time = _FakeVar("00:00:00.000")
    area._end_time = _FakeVar("00:00:00.000")
    area._videos = _FakeTree([])
    return area


def _set_frames(monkeypatch, frames: ty.Dict[str, np.ndarray], error=VideoOpenFailure):
    def fake_open_video(path, backend=None):
        if path not in frames:
            raise error(path)
        return _FakeVideo(frames[path])

    monkeypatch.setattr(application, "open_video", fake_open_video)


def _open_editor_with_regions(area, monkeypatch, frames, path="a.mp4"):
    """Open the editor on `path`, draw SHAPES in it, and close it."""
    _set_frames(monkeypatch, frames)
    area._videos = _FakeTree([path])
    area._on_edit_regions()
    area._region_editor._regions = list(SHAPES)
    area._on_region_editor_close()
    assert area._regions == SHAPES
    assert area._current_region.get() == "Using 1 regions."


def test_region_editor_is_reused_when_input_unchanged(area, monkeypatch):
    _open_editor_with_regions(area, monkeypatch, {"a.mp4": _frame(64, 48, 1)})
    editor = area._region_editor

    area._on_edit_regions()

    assert area._region_editor is editor
    assert editor.runs == 2
    assert editor.shapes == SHAPES
    assert len(_FakeRegionEditor.instances) == 1


def test_region_editor_is_reused_when_path_spelled_differently(area, monkeypatch):
    frame = _frame(64, 48, 1)
    _set_frames(monkeypatch, {"a.mp4": frame, "./a.mp4": frame})
    area._videos = _FakeTree(["a.mp4"])
    area._on_edit_regions()
    editor = area._region_editor

    area._videos = _FakeTree(["./a.mp4"])
    area._on_edit_regions()

    assert area._region_editor is editor
    assert len(_FakeRegionEditor.instances) == 1


def test_region_editor_is_rebuilt_when_first_input_changes(area, monkeypatch):
    """Regression test for #274: after replacing the input video, the region editor must show
    a frame from the new video rather than the one it was first created with."""
    frame_a, frame_b = _frame(64, 48, 1), _frame(64, 48, 2)
    _set_frames(monkeypatch, {"a.mp4": frame_a, "b.mp4": frame_b})
    area._videos = _FakeTree(["a.mp4"])
    area._on_edit_regions()
    first = area._region_editor
    assert first.video_path == "a.mp4"
    assert np.array_equal(first.frame, frame_a)

    area._videos = _FakeTree(["b.mp4"])
    area._on_edit_regions()

    second = area._region_editor
    assert second is not first
    assert second.video_path == "b.mp4"
    assert np.array_equal(second.frame, frame_b)
    assert second.runs == 1
    assert second._root.grabbed == 1


def test_region_editor_keeps_regions_when_resolution_matches(area, monkeypatch):
    frames = {"a.mp4": _frame(64, 48, 1), "b.mp4": _frame(64, 48, 2)}
    _open_editor_with_regions(area, monkeypatch, frames)
    first = area._region_editor

    area._videos = _FakeTree(["b.mp4"])
    area._on_edit_regions()

    assert area._region_editor is not first
    assert first.prompted == 0
    assert area._region_editor.initial_shapes == SHAPES
    assert area._region_editor.shapes == SHAPES
    assert area._regions == SHAPES
    assert area._current_region.get() == "Using 1 regions."


def test_region_editor_carries_over_unsaved_state(area, monkeypatch):
    frames = {"a.mp4": _frame(64, 48, 1), "b.mp4": _frame(64, 48, 2)}
    _open_editor_with_regions(area, monkeypatch, frames)
    area._region_editor.set_persisted(False, "regions.txt")

    area._videos = _FakeTree(["b.mp4"])
    area._on_edit_regions()

    assert area._region_editor.persisted is False
    assert area._region_editor.persisted_path == "regions.txt"


def test_region_editor_drops_regions_when_resolution_differs(area, monkeypatch):
    frames = {"a.mp4": _frame(64, 48, 1), "b.mp4": _frame(128, 96, 2)}
    _open_editor_with_regions(area, monkeypatch, frames)
    first = area._region_editor

    area._videos = _FakeTree(["b.mp4"], ["128 x 96"])
    area._on_edit_regions()

    assert first.prompted == 1
    assert area._region_editor is not first
    assert area._region_editor.initial_shapes == []
    assert area._regions == []
    assert area._current_region.get() == NO_REGIONS_SPECIFIED_TEXT


def test_region_editor_kept_when_user_cancels_save_prompt(area, monkeypatch):
    frames = {"a.mp4": _frame(64, 48, 1), "b.mp4": _frame(128, 96, 2)}
    _open_editor_with_regions(area, monkeypatch, frames)
    first = area._region_editor
    _FakeRegionEditor.prompt_result = False

    area._videos = _FakeTree(["b.mp4"], ["128 x 96"])
    area._on_edit_regions()

    assert first.prompted == 1
    assert area._region_editor is first
    assert first.runs == 1  # Not re-opened.
    assert area._regions == SHAPES
    assert area._current_region.get() == "Using 1 regions."


@pytest.mark.parametrize("error", [VideoOpenFailure, OSError])
def test_region_editor_not_created_when_video_cannot_be_opened(area, monkeypatch, error):
    _set_frames(monkeypatch, {}, error=error)
    shown = []
    monkeypatch.setattr(
        application.tkinter.messagebox, "showerror", lambda *a, **kw: shown.append((a, kw))
    )
    area._videos = _FakeTree(["missing.mp4"])

    area._on_edit_regions()

    assert area._region_editor is None
    assert len(shown) == 1
    assert "missing.mp4" in shown[0][0][1]


def test_region_editor_not_created_when_frame_cannot_be_read(area, monkeypatch):
    # A video that opens but yields no frame (read() returns False) is handled the same way.
    monkeypatch.setattr(application, "open_video", lambda path, backend=None: _FakeVideo(False))
    shown = []
    monkeypatch.setattr(
        application.tkinter.messagebox, "showerror", lambda *a, **kw: shown.append((a, kw))
    )
    area._videos = _FakeTree(["a.mp4"])

    area._on_edit_regions()

    assert area._region_editor is None
    assert len(shown) == 1


def test_update_exports_regions_for_unchanged_input(area, monkeypatch):
    _open_editor_with_regions(area, monkeypatch, {"a.mp4": _frame(64, 48, 1)})
    settings = _FakeSettings()

    assert area.update(settings) is settings
    assert settings.values["regions"] == SHAPES


def test_update_exports_regions_when_new_input_has_same_resolution(area, monkeypatch):
    _open_editor_with_regions(area, monkeypatch, {"a.mp4": _frame(64, 48, 1)})
    area._videos = _FakeTree(["b.mp4"], ["64 x 48"])
    settings = _FakeSettings()

    area.update(settings)

    assert settings.values["regions"] == SHAPES
    assert area._regions == SHAPES


def test_update_drops_stale_regions_when_input_resolution_changes(area, monkeypatch):
    """Removing the video the regions were drawn on and adding one with a different resolution,
    then scanning without reopening the editor, must not export the stale regions."""
    _open_editor_with_regions(area, monkeypatch, {"a.mp4": _frame(64, 48, 1)})
    area._videos = _FakeTree(["b.mp4"], ["128 x 96"])
    settings = _FakeSettings()

    assert area.update(settings) is settings

    assert "regions" not in settings.values
    assert settings.values["input"] == ["b.mp4"]
    assert area._regions == []
    assert area._current_region.get() == NO_REGIONS_SPECIFIED_TEXT


def test_update_ignores_regions_when_checkbox_unset(area, monkeypatch):
    _open_editor_with_regions(area, monkeypatch, {"a.mp4": _frame(64, 48, 1)})
    area._set_region.set(False)
    settings = _FakeSettings()

    area.update(settings)

    assert "regions" not in settings.values


def test_region_editor_seeks_to_start_time_and_rebuilds_on_change(area, monkeypatch):
    """When a start time is set, the region editor opens on the frame at start time and
    rebuilds while keeping regions if start time changes (#248)."""
    frame_0 = _frame(64, 48, 1)
    frame_60 = _frame(64, 48, 99)
    _set_frames(
        monkeypatch,
        {"a.mp4": lambda target: frame_60 if (target and target.frame_num == 60) else frame_0},
    )
    area._videos = _FakeTree(["a.mp4"])
    area._on_edit_regions()
    first = area._region_editor
    assert np.array_equal(first.frame, frame_0)
    first._regions = list(SHAPES)
    area._on_region_editor_close()

    area._set_time.set(True)
    area._start_time.set("00:00:02.000")
    area._on_edit_regions()

    second = area._region_editor
    assert second is not first
    assert np.array_equal(second.frame, frame_60)
    assert second.shapes == SHAPES


def test_region_editor_seek_and_step_frame(monkeypatch):
    """RegionEditor.seek_to_frame and step_frame update the frame and clamp to bounds (#248)."""
    import dvr_scan.app.region_editor as region_editor_mod
    from dvr_scan.app.region_editor import RegionEditor

    frames_by_num = {i: _frame(64, 48, i + 10) for i in range(5)}
    fake_video = _FakeVideo(
        lambda target: frames_by_num[target.frame_num if target else 0],
        frame_rate=10.0,
        total_frames=5,
    )
    monkeypatch.setattr(region_editor_mod, "open_video", lambda path, backend=None: fake_video)

    editor = RegionEditor(
        frame=frames_by_num[0],
        initial_shapes=SHAPES,
        initial_scale=1,
        debug_mode=False,
        video_path="a.mp4",
        save_path=None,
    )
    assert editor.seek_to_frame(3)
    assert editor._current_frame_num == 3
    assert np.array_equal(editor._source_frame, frames_by_num[3])

    assert editor.step_frame(10)
    assert editor._current_frame_num == 4
    assert np.array_equal(editor._source_frame, frames_by_num[4])

    assert editor.step_frame(-2)
    assert editor._current_frame_num == 2
    assert np.array_equal(editor._source_frame, frames_by_num[2])


def test_application_on_preset_selected_ignores_noop(monkeypatch):
    import dvr_scan.presets as presets
    from dvr_scan.app.application import Application

    app = Application.__new__(Application)
    app._active_preset = presets.DEFAULT_PRESET_NAME
    app._preset_snapshot = {"threshold": "0.15"}
    ui_state = [{"threshold": "0.15"}]
    app._serialize_ui_state = lambda: ui_state[0]
    applied = []
    app._on_preset_applied = lambda preset, config: applied.append(preset.name)

    loads = []
    orig_load = presets.load_preset

    def tracked_load(preset):
        loads.append(preset.name)
        return orig_load(preset)

    monkeypatch.setattr(presets, "load_preset", tracked_load)

    default_preset = presets.default_preset()
    app._on_preset_selected(default_preset)
    assert loads == []
    assert applied == []

    # Once UI state diverges from snapshot, selecting the same preset reloads it.
    ui_state[0] = {"threshold": "0.50"}
    app._on_preset_selected(default_preset)
    assert loads == [presets.DEFAULT_PRESET_NAME]
    assert applied == [presets.DEFAULT_PRESET_NAME]


# --- Select All / Remove Selected -------------------------------------------------------


class _SelectableTree:
    """Treeview stand-in supporting selection and deletion."""

    def __init__(self, items: ty.List[str]):
        self.items = list(items)
        self._selection: ty.List[str] = []
        self.selection_set_calls = []
        self.deleted = []

    def get_children(self):
        return list(self.items)

    def selection_set(self, items):
        self.selection_set_calls.append(list(items))
        self._selection = list(items)

    def selection(self):
        return list(self._selection)

    def delete(self, item):
        self.deleted.append(item)
        self.items.remove(item)
        if item in self._selection:
            self._selection.remove(item)


def test_input_area_select_all_selects_every_tree_item():
    area = InputArea.__new__(InputArea)
    tree = _SelectableTree(["row-1", "row-2", "row-3"])
    area._videos = tree

    area.select_all()

    assert tree.selection_set_calls == [["row-1", "row-2", "row-3"]]
    assert tree.selection() == ["row-1", "row-2", "row-3"]


def test_input_area_remove_selected_deletes_each_selected_item_and_refreshes():
    area = InputArea.__new__(InputArea)
    tree = _SelectableTree(["row-1", "row-2", "row-3"])
    tree.selection_set(["row-1", "row-3"])
    area._videos = tree
    refreshed = []
    area._refresh_remove_state = lambda: refreshed.append(True)

    area.remove_selected()

    assert tree.deleted == ["row-1", "row-3"]
    assert tree.get_children() == ["row-2"]
    assert refreshed == [True]


def test_input_area_key_handlers_act_and_break():
    area = InputArea.__new__(InputArea)
    tree = _SelectableTree(["row-1", "row-2"])
    area._videos = tree
    area._refresh_remove_state = lambda: None

    assert area._on_select_all_key(object()) == "break"
    assert tree.selection() == ["row-1", "row-2"]

    assert area._on_remove_key(object()) == "break"
    assert tree.get_children() == []


class _FakeStringVar:
    def __init__(self, value: str):
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str):
        self.value = value


def _startup_mode_app(default: str):
    """A Tk-free Application with only the startup mode state set."""
    from dvr_scan.app.application import Application

    app = Application.__new__(Application)
    app._saved_startup_mode = default
    app._startup_mode_var = _FakeStringVar(default)
    return app


def test_startup_mode_change_is_saved(monkeypatch):
    app = _startup_mode_app("classic")
    saved = []
    monkeypatch.setattr(application, "save_startup_mode", lambda mode: saved.append(mode))
    app._startup_mode_var.set("wizard")
    app._on_startup_mode_changed()
    assert saved == ["wizard"]
    assert app._saved_startup_mode == "wizard"


def test_startup_mode_unchanged_selection_does_not_save(monkeypatch):
    app = _startup_mode_app("classic")
    monkeypatch.setattr(
        application, "save_startup_mode", lambda mode: pytest.fail("should not save")
    )
    app._on_startup_mode_changed()
    assert app._saved_startup_mode == "classic"


def test_startup_mode_save_failure_reverts_selection(monkeypatch):
    app = _startup_mode_app("classic")

    def failing_save(mode):
        raise OSError("disk full")

    errors = []
    monkeypatch.setattr(application, "save_startup_mode", failing_save)
    monkeypatch.setattr(
        application.tkinter.messagebox, "showerror", lambda **kwargs: errors.append(kwargs)
    )
    app._startup_mode_var.set("wizard")
    app._on_startup_mode_changed()
    assert app._startup_mode_var.get() == "classic"
    assert app._saved_startup_mode == "classic"
    assert len(errors) == 1 and errors[0]["title"] == "Startup Mode"


# --- Default preset shown at startup ----------------------------------------------------


def test_loaded_config_is_default_preset():
    import argparse

    from dvr_scan.app.application import loaded_config_is_default_preset

    assert loaded_config_is_default_preset(None) is True
    assert loaded_config_is_default_preset(argparse.Namespace(ignore_user_config=False)) is True
    assert (
        loaded_config_is_default_preset(
            argparse.Namespace(ignore_user_config=False, config="other.cfg")
        )
        is False
    )
    assert loaded_config_is_default_preset(argparse.Namespace(ignore_user_config=True)) is False


# --- Fit main window to screen ----------------------------------------------------------


class _FakeWindow:
    def __init__(self, req, screen):
        self._req = req
        self._screen = screen
        self.geometry_calls = []

    def update_idletasks(self):
        pass

    def winfo_reqwidth(self):
        return self._req[0]

    def winfo_reqheight(self):
        return self._req[1]

    def winfo_screenwidth(self):
        return self._screen[0]

    def winfo_screenheight(self):
        return self._screen[1]

    def geometry(self, value):
        self.geometry_calls.append(value)


def test_fit_window_to_screen_noop_when_it_fits():
    from dvr_scan.app.common import fit_window_to_screen

    window = _FakeWindow(req=(1073, 1107), screen=(3440, 1440))
    assert fit_window_to_screen(window) is False
    assert window.geometry_calls == []


def test_fit_window_to_screen_shrinks_oversized_dimensions_only():
    from dvr_scan.app.common import fit_window_to_screen

    # 1366x768 laptop: width fits, height does not.
    window = _FakeWindow(req=(1073, 1107), screen=(1366, 768))
    assert fit_window_to_screen(window) is True
    assert window.geometry_calls == ["1073x648"]
    # Both too large.
    window = _FakeWindow(req=(1073, 1107), screen=(1024, 600))
    assert fit_window_to_screen(window) is True
    assert window.geometry_calls == ["984x480"]


# --- Active preset refresh ----------------------------------------------------------------


def test_refresh_active_preset_clears_when_ui_state_changed():
    from dvr_scan.app.application import Application

    app = Application.__new__(Application)
    app._active_preset = "Default"
    app._preset_snapshot = {"threshold": "0.15"}
    app._serialize_ui_state = lambda: {"threshold": "0.3"}
    cleared = []
    app._preset_area = type("Area", (), {"set_active": lambda self, name: cleared.append(name)})()
    app._refresh_active_preset()
    assert app._active_preset is None
    assert app._preset_snapshot is None
    assert cleared == [None]

    # Unchanged state keeps the preset.
    app._active_preset = "Default"
    app._preset_snapshot = {"threshold": "0.3"}
    app._refresh_active_preset()
    assert app._active_preset == "Default"
    assert cleared == [None]
