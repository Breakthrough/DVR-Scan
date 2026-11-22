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

import logging
import os
import shutil
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest
from scenedetect import FrameTimecode

from dvr_scan.cli import time_code_start_type
from dvr_scan.config import TimeCodeStartValue
from dvr_scan.overlays import TextOverlay
from dvr_scan.scanner import MotionScanner, OutputMode
from dvr_scan.video_input import open_input
from dvr_scan.wallclock import (
    WallClock,
    normalize_time_code_start,
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


@pytest.mark.parametrize(
    "value",
    [
        "",
        "yes",
        "23:37:30",
        "2026-13-01 00:00:00",
        "2026-11-16T23:37:30Z",
        "2026-11-16T23:37:30+02:00",
        # Pre-1970 aware timestamp: must raise ValueError, not OSError on Windows.
        "1960-01-01T00:00:00Z",
    ],
)
def test_parse_time_code_start_invalid(value):
    with pytest.raises(ValueError):
        parse_time_code_start(value)
    with pytest.raises(ValueError):
        TimeCodeStartValue(value)


def test_normalize_time_code_start():
    assert normalize_time_code_start(" FILENAME ") == "filename"
    assert TimeCodeStartValue(" MODIFIED ").value == "modified"
    assert time_code_start_type(" None ") == "none"
    assert TimeCodeStartValue(" 2026-11-16 23:37:30 ").value == "2026-11-16 23:37:30"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("20261116233730.avi", datetime(2026, 11, 16, 23, 37, 30)),
        ("VID_20261116_233730.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("2026-11-16_23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("2026-11-16t23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("REC20261116-233730_0001.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("cam1 2026.11.16 23.37.30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        # 4-digit prefixes and resolutions before the date must not swallow or corrupt it.
        ("0001_2026-11-16_23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("CAM0001_2026-11-16_23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("1920x1080_2026-11-16_23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("1990_2026-11-16_23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("2001_1012_2026-11-16_23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
        ("2026_13_01_2026-11-16_23-37-30.mp4", datetime(2026, 11, 16, 23, 37, 30)),
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


def test_wall_clock_explicit_start_anchors_dated_filenames(dated_inputs, caplog):
    """When all inputs have dated file names, an explicit start time anchors the first input
    and places later inputs using the differences between their file name times."""
    stream = open_input(dated_inputs)
    _read_all(stream)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        clock = WallClock.create(stream, "2026-01-02 03:04:05")
    assert not caplog.records
    assert clock.get_text(FrameTimecode(0.0, 25.0)) == "2026-01-02 03:04:05"
    # Second file name is 7m 30s after the first (23:37:30 -> 23:45:00).
    assert clock.get_text(FrameTimecode(TRAFFIC_CAMERA_DURATION, 25.0)) == "2026-01-02 03:11:35"
    assert clock.get_text(FrameTimecode(TRAFFIC_CAMERA_DURATION + 1, 25.0)) == "2026-01-02 03:11:36"


def test_wall_clock_explicit_start_out_of_order_warns(dated_inputs, caplog):
    """Out-of-order dated file names still use file name differences, with one warning."""
    stream = open_input(list(reversed(dated_inputs)))
    _read_all(stream)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        clock = WallClock.create(stream, "2026-01-02 03:11:35")
    assert len(caplog.records) == 1
    assert "not in order" in caplog.records[0].message
    assert clock.get_text(FrameTimecode(0.0, 25.0)) == "2026-01-02 03:11:35"
    # Second file name is 7m 30s before the first (23:45:00 -> 23:37:30).
    assert clock.get_text(FrameTimecode(TRAFFIC_CAMERA_DURATION, 25.0)) == "2026-01-02 03:04:05"


def test_wall_clock_explicit_start_continuous_fallback(traffic_camera_video, tmp_path, caplog):
    """If any input lacks a dated file name, an explicit start time falls back to continuous
    recording with one warning."""
    paths = [tmp_path / "20261116233730.mp4", tmp_path / "clip02.mp4"]
    for path in paths:
        shutil.copyfile(traffic_camera_video, path)
    stream = open_input([str(p) for p in paths])
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        clock = WallClock.create(stream, "2026-01-02 03:04:05")
    assert len(caplog.records) == 1
    assert "continuous" in caplog.records[0].message
    assert clock.get_text(FrameTimecode(0.0, 25.0)) == "2026-01-02 03:04:05"
    assert clock.get_text(FrameTimecode(TRAFFIC_CAMERA_DURATION + 1, 25.0)) == "2026-01-02 03:04:29"


def test_wall_clock_filename_missing_single_warning(traffic_camera_video, tmp_path, caplog):
    """Multiple inputs with no file name timestamp produce one summary warning, not one per file."""
    paths = [tmp_path / "20261116233730.mp4", tmp_path / "clip01.mp4", tmp_path / "clip02.mp4"]
    for path in paths:
        shutil.copyfile(traffic_camera_video, path)
    stream = open_input([str(p) for p in paths])
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        WallClock.create(stream, "filename")
    assert len(caplog.records) == 1
    assert "2 of 3 inputs" in caplog.records[0].message
    assert "clip01.mp4" in caplog.records[0].message


def test_wall_clock_modified_get_text_and_warnings(
    traffic_camera_video, tmp_path, monkeypatch, caplog
):
    """`modified` mode computes start = mtime - duration, warns once on identical mtimes
    (even when truncated to whole seconds or another file fails stat), and warns on 0 duration."""
    paths = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    fixed = datetime(2017, 5, 1, 1, 0, 0).timestamp()
    for i, path in enumerate(paths):
        shutil.copyfile(traffic_camera_video, path)
        # Sub-second difference within the same second should still trigger identical-mtime warning.
        os.utime(path, (fixed + 0.1 * i, fixed + 0.1 * i))
    stream = open_input([str(p) for p in paths])
    _read_all(stream)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        clock = WallClock.create(stream, "modified")
    assert len(caplog.records) == 1
    assert "same modified time" in caplog.records[0].message
    # 01:00:00 - 23.04s = 00:59:36.96 -> 00:59:36
    assert clock.get_text(FrameTimecode(0.0, 25.0)) == "2017-05-01 00:59:36"

    # Distinct modified times produce no warning and exact per-file wallclock times.
    os.utime(paths[1], (fixed + 60, fixed + 60))
    stream2 = open_input([str(p) for p in paths])
    _read_all(stream2)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        clock2 = WallClock.create(stream2, "modified")
    assert not caplog.records
    assert clock2.get_text(FrameTimecode(TRAFFIC_CAMERA_DURATION, 25.0)) == "2017-05-01 01:00:36"

    # Zero duration warns and uses modified time directly.
    monkeypatch.setattr(stream2, "source_duration", lambda _idx: Fraction(0))
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        clock3 = WallClock.create(stream2, "modified")
    assert len(caplog.records) == 1
    assert "duration unknown" in caplog.records[0].message
    assert clock3.get_text(FrameTimecode(0.0, 25.0)) == "2017-05-01 01:00:00"


def test_wall_clock_single_input_and_single_missing(traffic_camera_video, caplog):
    """Single-input explicit start emits no warning; single missing filename emits one."""
    stream = open_input([traffic_camera_video])
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        clock = WallClock.create(stream, "2026-01-02 03:04:05")
    assert not caplog.records
    assert clock.get_text(FrameTimecode(5.0, 25.0)) == "2026-01-02 03:04:10"

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        clock_fn = WallClock.create(stream, "filename")
    assert len(caplog.records) == 1
    assert "traffic_camera.mp4" in caplog.records[0].message
    assert clock_fn.get_text(FrameTimecode(1.0, 25.0)) is None
    assert WallClock.create(stream, "none") is None


def test_locate_ignores_future_offsets_before_transition(dated_inputs):
    """`locate` only searches finalized offsets 0.._index, so an overrun frame from source 0
    is never attributed to source 1 before source 0 finishes."""
    stream = open_input(dated_inputs)
    # Simulate source 0 overrunning its declared end before transitioning to source 1.
    assert stream._index == 0
    overrun_time = FrameTimecode(TRAFFIC_CAMERA_DURATION + 2.0, 25.0)
    index, local = stream.locate(overrun_time)
    assert index == 0
    assert float(local) == pytest.approx(TRAFFIC_CAMERA_DURATION + 2.0, abs=1e-4)


def test_scanner_draws_wall_clock_and_falls_back(traffic_camera_video, tmp_path, monkeypatch):
    """MotionScanner passes wall-clock date/time text to TextOverlay.draw() when known,
    and falls back to the video position when the filename has no timestamp."""
    dated = tmp_path / "20261116233730.mp4"
    shutil.copyfile(traffic_camera_video, dated)

    drawn: list[str] = []
    orig_draw = TextOverlay.draw

    def record_draw(self, frame, text):
        drawn.append(text)
        return orig_draw(self, frame, text)

    monkeypatch.setattr(TextOverlay, "draw", record_draw)

    scanner = MotionScanner([str(dated)])
    scanner.set_output(output_mode=OutputMode.OPENCV, output_dir=tmp_path)
    scanner.set_video_time(end_time="00:00:02")
    scanner.set_event_params(min_event_len=1, time_pre_event=0, time_post_event=0)
    scanner.set_detection_params(threshold=0.01)
    scanner.set_overlays(timecode_overlay=TextOverlay(), time_code_start="filename")
    scanner.scan()
    assert drawn
    assert all(text.startswith("2026-11-16 23:37:3") for text in drawn)

    # Undated filename falls back to elapsed HH:MM:SS.mmm video timecode.
    drawn.clear()
    scanner2 = MotionScanner([traffic_camera_video])
    scanner2.set_output(output_mode=OutputMode.OPENCV, output_dir=tmp_path)
    scanner2.set_video_time(end_time="00:00:02")
    scanner2.set_event_params(min_event_len=1, time_pre_event=0, time_post_event=0)
    scanner2.set_detection_params(threshold=0.01)
    scanner2.set_overlays(timecode_overlay=TextOverlay(), time_code_start="filename")
    scanner2.scan()
    assert drawn
    assert all(text.startswith("00:00:0") for text in drawn)


def test_scanner_time_code_start(dated_inputs):
    scanner = MotionScanner(dated_inputs)
    with pytest.raises(ValueError):
        scanner.set_overlays(timecode_overlay=TextOverlay(), time_code_start="bogus")
    # The start time is not used without the timecode overlay.
    scanner.set_overlays(time_code_start="filename")
    assert scanner._wall_clock is None
    scanner.set_overlays(timecode_overlay=TextOverlay(), time_code_start="filename")
    assert scanner._wall_clock is not None
