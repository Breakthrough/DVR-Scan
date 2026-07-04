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

"""Tests for the Scan Wizard's custom video list (Tk-free logic only)."""

from types import SimpleNamespace

import pytest

from dvr_scan.app.application import VideoInfo
from dvr_scan.app.video_list import VideoList


def _row(name: str, path: str, date: str = "2026-01-01 00:00:00") -> SimpleNamespace:
    info = VideoInfo(
        path=path,
        name=name,
        duration="00:00:01.000",
        framerate="30",
        resolution="640 x 480",
        date=date,
    )
    return SimpleNamespace(info=info)


def _list_with(rows: dict, order: list) -> VideoList:
    area = VideoList.__new__(VideoList)
    area._rows = rows
    area._order = order
    return area


def test_videos_returns_paths_in_display_order():
    rows = {"a": _row("b.mp4", "/tmp/b.mp4"), "b": _row("a.mp4", "/tmp/a.mp4")}
    area = _list_with(rows, ["a", "b"])

    assert area.videos == ["/tmp/b.mp4", "/tmp/a.mp4"]


def test_sort_by_name_reorders_case_insensitively():
    rows = {
        "x": _row("Banana.mp4", "/tmp/banana.mp4"),
        "y": _row("apple.mp4", "/tmp/apple.mp4"),
    }
    area = _list_with(rows, ["x", "y"])
    area._regrid = lambda: None

    area.sort_by("#0", descending=False)
    assert area.videos == ["/tmp/apple.mp4", "/tmp/banana.mp4"]

    area.sort_by("#0", descending=True)
    assert area.videos == ["/tmp/banana.mp4", "/tmp/apple.mp4"]


def test_sort_by_date_sorts_chronologically():
    rows = {
        "x": _row("a.mp4", "/tmp/a.mp4", date="2026-06-13 09:00:00"),
        "y": _row("b.mp4", "/tmp/b.mp4", date="2026-01-02 09:00:00"),
    }
    area = _list_with(rows, ["x", "y"])
    area._regrid = lambda: None

    area.sort_by("date", descending=False)
    assert area.videos == ["/tmp/b.mp4", "/tmp/a.mp4"]


def test_sort_by_rejects_unknown_column():
    area = _list_with({"x": _row("a.mp4", "/tmp/a.mp4")}, ["x"])
    area._regrid = lambda: None

    with pytest.raises(ValueError):
        area.sort_by("duration", descending=False)


def test_update_sets_input_or_returns_none_when_empty():
    captured = {}
    settings = SimpleNamespace(set=lambda key, value: captured.__setitem__(key, value))

    empty = _list_with({}, [])
    assert empty.update(settings) is None
    assert "input" not in captured

    area = _list_with({"a": _row("a.mp4", "/tmp/a.mp4")}, ["a"])
    assert area.update(settings) is settings
    assert captured["input"] == ["/tmp/a.mp4"]


def test_add_video_forwards_parent_to_dialog(monkeypatch):
    area = VideoList.__new__(VideoList)
    seen = {}

    def fake_askopenfilename(**kwargs):
        seen.update(kwargs)
        return ()

    monkeypatch.setattr(
        "dvr_scan.app.video_list.tkinter.filedialog.askopenfilename", fake_askopenfilename
    )

    # Empty dialog result returns before any Tk widget work.
    area.add_video(parent="wizard-parent")

    assert seen["parent"] == "wizard-parent"
    assert seen["multiple"] is True
