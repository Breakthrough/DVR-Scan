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
    def __init__(self, frame):
        self._frame = frame

    def read(self):
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
    area._regions = []
    area._current_region = _FakeVar(NO_REGIONS_SPECIFIED_TEXT)
    area._set_region = _FakeVar(True)
    area._set_time = _FakeVar(False)
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
