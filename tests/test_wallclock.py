#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""DVR-Scan Wall Clock Tests

Validates the date and time of recording for the timecode overlay (`time-code-start`, #285)."""

import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from scenedetect import FrameTimecode

from dvr_scan.config import TimeCodeStartValue
from dvr_scan.overlays import TextOverlay
from dvr_scan.scanner import MotionScanner
from dvr_scan.video_input import open_input
from dvr_scan.wallclock import (
    WallClock,
    parse_time_code_start,
    start_time_from_filename,
    start_time_from_modified,
)

# Duration of traffic_camera.mp4 in seconds (576 frames at 25 fps).
TRAFFIC_CAMERA_DURATION = 23.04


@pytest.mark.parametrize(
    "value,expected",
    [
        ("none", "none"),
        ("FileName", "filename"),
        (" modified ", "modified"),
        ("2026-11-16 23:37:30", datetime(2026, 11, 16, 23, 37, 30)),
        ("2026-11-16T23:37:30", datetime(2026, 11, 16, 23, 37, 30)),
    ],
)
def test_parse_time_code_start(value, expected):
    assert parse_time_code_start(value) == expected


@pytest.mark.parametrize("value", ["", "yes", "23:37:30", "2026-13-01 00:00:00"])
def test_parse_time_code_start_invalid(value):
    with pytest.raises(ValueError):
        parse_time_code_start(value)
    with pytest.raises(ValueError):
        TimeCodeStartValue(value)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("20261116233730.avi", datetime(2026, 11, 16, 23, 37, 30)),
        ("VID_20261116_233730.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("2026-11-16_23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("REC20261116-233730_0001.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("cam1 2026.11.16 23.37.30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        # No date and time in the name.
        ("057706.avi", None),
        ("traffic_camera.mp4", None),
        # Not a valid date, or part of a longer number.
        ("20261316233730.avi", None),
        ("2026111623373099.avi", None),
        ("00001116233730.avi", None),
    ],
)
def test_start_time_from_filename(name, expected):
    assert start_time_from_filename(Path("some_folder_20201010101010") / name) == expected


def test_start_time_from_modified(tmp_path):
    path = tmp_path / "clip.avi"
    path.write_bytes(b"")
    modified = datetime(2026, 11, 16, 23, 38, 30)
    os.utime(path, (modified.timestamp(), modified.timestamp()))
    assert start_time_from_modified(path, 60) == datetime(2026, 11, 16, 23, 37, 30)
    assert start_time_from_modified(tmp_path / "missing.avi", 60) is None


@pytest.fixture
def dated_inputs(traffic_camera_video, tmp_path) -> list[str]:
    """Two copies of traffic_camera.mp4 with a start time in the file name."""
    paths = [tmp_path / "20261116233730.mp4", tmp_path / "VID_20261116_234500.mp4"]
    for path in paths:
        shutil.copyfile(traffic_camera_video, path)
    return [str(path) for path in paths]


def _read_all(stream):
    while stream.read(decode=False) is not False:
        pass


def test_wall_clock_from_filename(dated_inputs):
    """Each input uses the start time in its own file name."""
    stream = open_input(dated_inputs)
    _read_all(stream)
    clock = WallClock.create(stream, "filename")
    get_text = clock.get_text
    assert get_text(FrameTimecode(0.0, 25.0)) == "2026-11-16 23:37:30"
    assert get_text(FrameTimecode(22.96, 25.0)) == "2026-11-16 23:37:52"
    # First frame of the second input. The scanner rounds timecodes to 1 us.
    assert get_text(FrameTimecode(TRAFFIC_CAMERA_DURATION - 1e-7, 25.0)) == "2026-11-16 23:45:00"
    assert get_text(FrameTimecode(TRAFFIC_CAMERA_DURATION + 10.5, 25.0)) == "2026-11-16 23:45:10"


def test_wall_clock_locate_limited_to_current_input(dated_inputs):
    """A time is not mapped to an input that the stream has not opened yet. The start time
    of the next input is not final until the current input ends."""
    stream = open_input(dated_inputs)
    assert stream.read() is not False
    index, _ = stream.locate(FrameTimecode(TRAFFIC_CAMERA_DURATION + 1.0, 25.0))
    assert index == 0


def test_wall_clock_explicit_start(dated_inputs):
    """A date and time from the user is the start of the first input. Later inputs
    continue from it."""
    stream = open_input(dated_inputs)
    clock = WallClock.create(stream, "2026-01-02 03:04:05")
    assert clock.get_text(FrameTimecode(0.0, 25.0)) == "2026-01-02 03:04:05"
    assert clock.get_text(FrameTimecode(TRAFFIC_CAMERA_DURATION + 1, 25.0)) == "2026-01-02 03:04:29"


def test_wall_clock_unknown_start(traffic_camera_video):
    """An input with no date and time in its name gives no text. The scanner then draws
    the position in the video."""
    stream = open_input([traffic_camera_video])
    clock = WallClock.create(stream, "filename")
    assert clock.get_text(FrameTimecode(1.0, 25.0)) is None
    assert WallClock.create(stream, "none") is None


def test_scanner_time_code_start(dated_inputs):
    scanner = MotionScanner(dated_inputs)
    with pytest.raises(ValueError):
        scanner.set_overlays(timecode_overlay=TextOverlay(), time_code_start="bogus")
    # The start time is not used without the timecode overlay.
    scanner.set_overlays(time_code_start="filename")
    assert scanner._wall_clock is None
    scanner.set_overlays(timecode_overlay=TextOverlay(), time_code_start="filename")
    assert scanner._wall_clock is not None
