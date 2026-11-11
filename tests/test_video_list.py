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

from dvr_scan.app.inputs import VideoInfo
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
    area._refresh_button_state = lambda: None

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
    area._refresh_button_state = lambda: None

    area.sort_by("date", descending=False)
    assert area.videos == ["/tmp/b.mp4", "/tmp/a.mp4"]


def test_sort_by_refreshes_buttons_and_notifies_owner():
    """Sorting moves the selected row, so Up/Down must be re-evaluated, and the owner is
    told the order changed (the wizard's summary lists the videos in order)."""
    area = _with_buttons(_selectable_list(3))
    area._selected = {"r0"}
    changed = []
    area.on_changed = lambda: changed.append(True)

    area.sort_by("#0", descending=True)

    assert area._order == ["r2", "r1", "r0"]
    assert _button_states(area)["up"] == "normal"
    assert _button_states(area)["down"] == "disabled"
    assert changed == [True]


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
        "dvr_scan.app.inputs.tkinter.filedialog.askopenfilename", fake_askopenfilename
    )

    # Empty dialog result returns before any Tk widget work.
    area.add_video(parent="wizard-parent")

    assert seen["parent"] == "wizard-parent"
    assert seen["multiple"] is True


def test_add_video_missing_path_warns_and_continues_loading_remaining(monkeypatch, tmp_path):
    valid_file = tmp_path / "valid.mp4"
    valid_file.write_bytes(b"fake")
    missing_file = tmp_path / "missing.mp4"

    area = _list_with({}, [])
    added_infos = []
    area._add_row = lambda info: added_infos.append(info)
    area._refresh_button_state = lambda: None

    monkeypatch.setattr(
        "dvr_scan.app.inputs.tkinter.filedialog.askopenfilename",
        lambda **_kwargs: (str(missing_file), str(valid_file)),
    )
    monkeypatch.setattr(
        "dvr_scan.app.inputs.probe_video",
        lambda p: VideoInfo(
            path=str(p),
            name="valid.mp4",
            duration="00:00:01.000",
            framerate="30",
            resolution="640 x 480",
            date="2026-01-01 00:00:00",
        ),
    )

    warnings = []
    monkeypatch.setattr(
        "dvr_scan.app.inputs.tkinter.messagebox.showwarning",
        lambda *_args, **kwargs: warnings.append(kwargs),
    )

    area.add_video(parent="wizard-win")

    assert len(added_infos) == 1
    assert added_infos[0].name == "valid.mp4"
    assert len(warnings) == 1
    assert warnings[0]["parent"] == "wizard-win"


# --- Multi-selection, Select All and removal -----------------------------------------------


class _FakeButton:
    def __init__(self):
        self.values = {}

    def __setitem__(self, key, value):
        self.values[key] = value

    def __getitem__(self, key):
        return self.values[key]


class _FakeFrame:
    def __init__(self, iid: str, destroyed: list):
        self._iid = iid
        self._destroyed = destroyed

    def destroy(self):
        self._destroyed.append(self._iid)


def _selectable_list(count: int) -> VideoList:
    """A Tk-free list of `count` rows (iids "r0", "r1", ...) with selection state, recording
    frame destroys in `area.destroyed` and `_regrid` calls in `area.regrids`."""
    destroyed = []
    rows = {}
    for index in range(count):
        row = _row(f"v{index}.mp4", f"/tmp/v{index}.mp4")
        row.frame = _FakeFrame(f"r{index}", destroyed)
        rows[f"r{index}"] = row
    area = _list_with(rows, [f"r{index}" for index in range(count)])
    area._selected = set()
    area._anchor = None
    area.destroyed = destroyed
    area.regrids = []
    area._regrid = lambda: area.regrids.append(list(area._order))
    area._paint_selection = lambda: None
    area._refresh_button_state = lambda: None
    return area


def _with_buttons(area: VideoList) -> VideoList:
    area._remove_button = _FakeButton()
    area._up_button = _FakeButton()
    area._down_button = _FakeButton()
    area._sort_button = _FakeButton()
    # Use the real implementation rather than the no-op stub.
    del area._refresh_button_state
    return area


def _button_states(area: VideoList) -> dict:
    return {
        "remove": area._remove_button["state"],
        "up": area._up_button["state"],
        "down": area._down_button["state"],
        "sort": area._sort_button["state"],
    }


def test_select_all_selects_every_row():
    area = _selectable_list(3)
    area._order = ["r2", "r0", "r1"]

    area.select_all()

    assert area._selected == {"r0", "r1", "r2"}


def test_clear_selection_empties_selection():
    area = _selectable_list(3)
    area.select_all()

    area.clear_selection(object())

    assert area._selected == set()


def test_plain_click_resets_to_single_row_and_sets_anchor():
    area = _selectable_list(4)
    area._selected = {"r0", "r1", "r3"}
    area._anchor = "r0"

    area._on_click("r2")

    assert area._selected == {"r2"}
    assert area._anchor == "r2"


def test_shift_click_selects_range_forward_and_keeps_anchor():
    area = _selectable_list(5)
    area._on_click("r1")

    area._on_shift_click("r3")

    assert area._selected == {"r1", "r2", "r3"}
    assert area._anchor == "r1"


def test_shift_click_selects_range_backward_and_keeps_anchor():
    area = _selectable_list(5)
    area._on_click("r3")

    area._on_shift_click("r0")

    assert area._selected == {"r0", "r1", "r2", "r3"}
    assert area._anchor == "r3"


def test_shift_click_range_can_be_adjusted_from_same_anchor():
    area = _selectable_list(5)
    area._on_click("r2")
    area._on_shift_click("r4")

    area._on_shift_click("r1")

    assert area._selected == {"r1", "r2"}
    assert area._anchor == "r2"


def test_shift_click_without_anchor_acts_as_plain_click():
    area = _selectable_list(4)
    area._selected = {"r0"}

    area._on_shift_click("r2")

    assert area._selected == {"r2"}
    assert area._anchor == "r2"


def test_shift_click_with_stale_anchor_acts_as_plain_click():
    area = _selectable_list(4)
    area._anchor = "gone"

    area._on_shift_click("r1")

    assert area._selected == {"r1"}
    assert area._anchor == "r1"


def test_toggle_click_adds_and_removes_rows_and_sets_anchor():
    area = _selectable_list(4)
    area._on_click("r0")

    area._on_toggle_click("r2")
    assert area._selected == {"r0", "r2"}
    assert area._anchor == "r2"

    area._on_toggle_click("r0")
    assert area._selected == {"r2"}
    assert area._anchor == "r0"


def test_remove_selected_with_nothing_selected_is_noop():
    area = _selectable_list(3)

    area.remove_selected()

    assert area.destroyed == []
    assert area.regrids == []
    assert area._order == ["r0", "r1", "r2"]
    assert len(area._rows) == 3


def test_remove_selected_non_contiguous_rows_selects_row_at_lowest_removed_index():
    area = _selectable_list(5)
    area._selected = {"r1", "r3"}
    area._anchor = "r3"
    refreshed = []
    area._refresh_button_state = lambda: refreshed.append(True)

    area.remove_selected()

    assert sorted(area.destroyed) == ["r1", "r3"]
    assert area._order == ["r0", "r2", "r4"]
    assert set(area._rows) == {"r0", "r2", "r4"}
    assert area.regrids == [["r0", "r2", "r4"]]
    # r2 fell into slot 1, the lowest removed index.
    assert area._selected == {"r2"}
    assert area._anchor == "r2"
    assert refreshed


def test_remove_selected_last_row_selects_new_last_row():
    area = _selectable_list(3)
    area._on_click("r2")

    area.remove_selected()

    assert area.destroyed == ["r2"]
    assert area._order == ["r0", "r1"]
    assert area._selected == {"r1"}
    assert area._anchor == "r1"


def test_remove_selected_trailing_block_clamps_to_new_last_row():
    area = _selectable_list(4)
    area._selected = {"r2", "r3"}

    area.remove_selected()

    assert area._order == ["r0", "r1"]
    assert area._selected == {"r1"}
    assert area._anchor == "r1"


def test_remove_selected_all_rows_leaves_empty_selection_and_no_anchor():
    area = _selectable_list(3)
    area.select_all()
    area._anchor = "r1"
    refreshed = []
    area._refresh_button_state = lambda: refreshed.append(True)

    area.remove_selected()

    assert sorted(area.destroyed) == ["r0", "r1", "r2"]
    assert area._order == []
    assert area._rows == {}
    assert area._selected == set()
    assert area._anchor is None
    assert area.videos == []
    assert refreshed


def test_remove_selected_after_select_all_disables_buttons():
    area = _with_buttons(_selectable_list(2))
    area.select_all()

    area.remove_selected()

    assert _button_states(area) == {
        "remove": "disabled",
        "up": "disabled",
        "down": "disabled",
        "sort": "disabled",
    }


def test_move_up_shifts_contiguous_block_preserving_order():
    area = _selectable_list(4)
    area._selected = {"r2", "r3"}

    area._on_move_up()

    assert area._order == ["r0", "r2", "r3", "r1"]
    assert area._selected == {"r2", "r3"}
    assert area.regrids == [["r0", "r2", "r3", "r1"]]


def test_move_down_shifts_contiguous_block_preserving_order():
    area = _selectable_list(4)
    area._selected = {"r0", "r1"}

    area._on_move_down()

    assert area._order == ["r2", "r0", "r1", "r3"]
    assert area._selected == {"r0", "r1"}
    assert area.regrids == [["r2", "r0", "r1", "r3"]]


def test_move_up_is_noop_when_top_selected_row_is_first():
    area = _selectable_list(4)
    area._selected = {"r0", "r2"}

    area._on_move_up()

    assert area._order == ["r0", "r1", "r2", "r3"]
    assert area.regrids == []


def test_move_down_is_noop_when_bottom_selected_row_is_last():
    area = _selectable_list(4)
    area._selected = {"r1", "r3"}

    area._on_move_down()

    assert area._order == ["r0", "r1", "r2", "r3"]
    assert area.regrids == []


def test_move_with_empty_selection_is_noop():
    area = _selectable_list(3)

    area._on_move_up()
    area._on_move_down()

    assert area._order == ["r0", "r1", "r2"]
    assert area.regrids == []


def test_move_down_non_contiguous_selection_displaces_unselected_rows():
    area = _selectable_list(4)
    area._selected = {"r0", "r2"}

    area._on_move_down()

    assert area._order == ["r1", "r0", "r3", "r2"]
    assert area._selected_indices() == [1, 3]


def test_move_up_non_contiguous_selection_displaces_unselected_rows():
    area = _selectable_list(4)
    area._selected = {"r1", "r3"}

    area._on_move_up()

    assert area._order == ["r1", "r0", "r3", "r2"]
    assert area._selected_indices() == [0, 2]


def test_refresh_button_state_empty_list():
    area = _with_buttons(_selectable_list(0))

    area._refresh_button_state()

    assert _button_states(area) == {
        "remove": "disabled",
        "up": "disabled",
        "down": "disabled",
        "sort": "disabled",
    }


def test_refresh_button_state_rows_without_selection():
    area = _with_buttons(_selectable_list(3))

    area._refresh_button_state()

    assert _button_states(area) == {
        "remove": "disabled",
        "up": "disabled",
        "down": "disabled",
        "sort": "normal",
    }


def test_refresh_button_state_single_top_row_selected():
    area = _with_buttons(_selectable_list(3))
    area._selected = {"r0"}

    area._refresh_button_state()

    assert _button_states(area) == {
        "remove": "normal",
        "up": "disabled",
        "down": "normal",
        "sort": "normal",
    }


def test_refresh_button_state_single_bottom_row_selected():
    area = _with_buttons(_selectable_list(3))
    area._selected = {"r2"}

    area._refresh_button_state()

    assert _button_states(area) == {
        "remove": "normal",
        "up": "normal",
        "down": "disabled",
        "sort": "normal",
    }


def test_refresh_button_state_multiple_middle_rows_selected():
    area = _with_buttons(_selectable_list(5))
    area._selected = {"r1", "r3"}

    area._refresh_button_state()

    assert _button_states(area) == {
        "remove": "normal",
        "up": "normal",
        "down": "normal",
        "sort": "normal",
    }


def test_refresh_button_state_all_rows_selected():
    area = _with_buttons(_selectable_list(3))
    area._selected = {"r0", "r1", "r2"}

    area._refresh_button_state()

    assert _button_states(area) == {
        "remove": "normal",
        "up": "disabled",
        "down": "disabled",
        "sort": "normal",
    }


# --- Add button and first video resolution ------------------------------------------------


def test_add_button_uses_on_add_callback_when_given(monkeypatch):
    """The Scan Wizard routes "+" through its own browse handler (parented dialog, locked
    navigation) instead of an unparented dialog opened by the list."""
    area = VideoList.__new__(VideoList)
    calls = []
    area._on_add = lambda: calls.append("wizard-browse")
    monkeypatch.setattr(
        "dvr_scan.app.inputs.tkinter.filedialog.askopenfilename",
        lambda **kwargs: pytest.fail("list must not open its own dialog"),
    )
    area._on_add_clicked()
    assert calls == ["wizard-browse"]


def test_add_button_without_callback_parents_dialog_to_toplevel(monkeypatch):
    area = VideoList.__new__(VideoList)
    area._on_add = None
    area._root = SimpleNamespace(winfo_toplevel=lambda: "list-toplevel")
    seen = {}

    def fake_askopenfilename(**kwargs):
        seen.update(kwargs)
        return ()

    monkeypatch.setattr(
        "dvr_scan.app.inputs.tkinter.filedialog.askopenfilename", fake_askopenfilename
    )
    area._on_add_clicked()
    assert seen["parent"] == "list-toplevel"


def test_first_video_resolution():
    area = _list_with({"a": _row("a.mp4", "/tmp/a.mp4"), "b": _row("b.mp4", "/tmp/b.mp4")}, [])
    assert area.first_video_resolution is None
    area._order = ["b", "a"]
    area._rows["b"].info.resolution = "1280 x 720"
    assert area.first_video_resolution == (1280, 720)
    area._rows["b"].info.resolution = "N/A"
    assert area.first_video_resolution is None
