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

from scenedetect import FrameTimecode

from dvr_scan.report import CSV_HEADER, write_events_csv
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
    assert rows[1] == ["1", "00:00:03.0", "00:00:07.5", "00:00:04.5", "30", "75"]
    assert rows[2] == ["2", "00:00:10.0", "00:00:13.0", "00:00:03.0", "100", "130"]
    assert len(rows) == 3


def test_write_events_csv_empty_writes_header_only():
    buffer = io.StringIO()
    write_events_csv(buffer, [])
    rows = list(csv_reader(buffer))
    assert rows == [CSV_HEADER]
