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
