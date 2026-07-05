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
"""DVR-Scan Report Tests"""

import csv
import io
import json

from scenedetect import FrameTimecode

from dvr_scan.report import CSV_HEADER, JSON_REPORT_VERSION, write_events_csv, write_events_json
from dvr_scan.scanner import MotionEvent


def make_event(start_frame: int, end_frame: int, fps: float = 10.0) -> MotionEvent:
    return MotionEvent(
        start=FrameTimecode(start_frame, fps),
        end=FrameTimecode(end_frame, fps),
    )


def csv_reader(buffer: io.StringIO):
    buffer.seek(0)
    return csv.reader(buffer)


def test_write_events_csv_rows():
    buffer = io.StringIO()
    events = [make_event(30, 75), make_event(100, 130)]
    write_events_csv(buffer, events)
    rows = list(csv_reader(buffer))
    assert rows[0] == CSV_HEADER
    assert rows[1] == ["1", "00:00:03.0", "00:00:07.5", "00:00:04.5", "30", "75", "3.0", "7.5"]
    assert rows[2] == ["2", "00:00:10.0", "00:00:13.0", "00:00:03.0", "100", "130", "10.0", "13.0"]
    assert len(rows) == 3


def test_write_events_csv_empty_writes_header_only():
    buffer = io.StringIO()
    write_events_csv(buffer, [])
    rows = list(csv_reader(buffer))
    assert rows == [CSV_HEADER]


def test_write_events_json():
    buffer = io.StringIO()
    events = [make_event(30, 75), make_event(100, 130)]
    write_events_json(
        buffer,
        events,
        input_files=["video.mp4"],
        frame_rate=10.0,
        frames_processed=200,
    )
    report = json.loads(buffer.getvalue())
    assert report["version"] == JSON_REPORT_VERSION
    assert report["generator"].startswith("DVR-Scan ")
    assert report["input"] == {"files": ["video.mp4"], "frame_rate": 10.0}
    assert report["scan"] == {"frames_processed": 200, "num_events": 2}
    assert len(report["events"]) == 2
    first = report["events"][0]
    assert first["number"] == 1
    assert first["start"] == {"frame": 30, "seconds": 3.0, "timecode": "00:00:03.000"}
    assert first["end"] == {"frame": 75, "seconds": 7.5, "timecode": "00:00:07.500"}
    assert first["duration"] == {"frame": 45, "seconds": 4.5, "timecode": "00:00:04.500"}


def test_write_events_json_empty():
    """An empty scan must still produce a valid report with zero events, and metadata
    fields must be omitted gracefully when unknown (e.g. when saved from the UI)."""
    buffer = io.StringIO()
    write_events_json(buffer, [])
    report = json.loads(buffer.getvalue())
    assert report["version"] == JSON_REPORT_VERSION
    assert report["input"] == {"files": [], "frame_rate": None}
    assert report["scan"] == {"frames_processed": None, "num_events": 0}
    assert report["events"] == []
