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

"""Scan report generation. Produces shareable summaries of detected motion events,
independent of how the scan was run (CLI or UI)."""

import csv
import typing as ty

if ty.TYPE_CHECKING:
    from dvr_scan.scanner import MotionEvent

CSV_HEADER = ["Event", "Start Time", "End Time", "Duration", "Start Frame", "End Frame"]
TIMECODE_PRECISION = 1


def write_events_csv(file: ty.TextIO, event_list: ty.List["MotionEvent"]):
    """Write `event_list` to `file` as CSV. Always writes the header row, followed by
    one row per event (empty if there are no events)."""
    writer = csv.writer(file, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for index, event in enumerate(event_list):
        duration = event.end - event.start
        writer.writerow(
            [
                index + 1,
                event.start.get_timecode(precision=TIMECODE_PRECISION),
                event.end.get_timecode(precision=TIMECODE_PRECISION),
                duration.get_timecode(precision=TIMECODE_PRECISION),
                event.start.get_frames(),
                event.end.get_frames(),
            ]
        )
