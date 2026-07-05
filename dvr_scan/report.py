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
import json
import typing as ty
from datetime import datetime

import dvr_scan

if ty.TYPE_CHECKING:
    from scenedetect import FrameTimecode

    from dvr_scan.scanner import MotionEvent

CSV_HEADER = [
    "Event",
    "Start Time",
    "End Time",
    "Duration",
    "Start Frame",
    "End Frame",
    "Start (Seconds)",
    "End (Seconds)",
]
TIMECODE_PRECISION = 1

JSON_REPORT_VERSION = 1
"""Version of the JSON report schema produced by `write_events_json`."""

SECONDS_PRECISION = 6
"""Number of decimal places used when writing exact times in seconds."""


def write_events_csv(file: ty.TextIO, event_list: ty.List["MotionEvent"]):
    """Write `event_list` to `file` as CSV. Always writes the header row, followed by
    one row per event (empty if there are no events).

    Frame numbers are approximations on variable framerate inputs; the seconds columns
    are exact presentation times."""
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
                event.start.frame_num,
                event.end.frame_num,
                round(event.start.seconds, SECONDS_PRECISION),
                round(event.end.seconds, SECONDS_PRECISION),
            ]
        )


def _time_entry(timecode: "FrameTimecode") -> ty.Dict[str, ty.Any]:
    """Represent `timecode` as a JSON-friendly dict with frame/seconds/timecode forms.

    The frame number is an approximation on variable framerate inputs."""
    return {
        "frame": timecode.frame_num,
        "seconds": round(timecode.seconds, SECONDS_PRECISION),
        "timecode": timecode.get_timecode(),
    }


def write_events_json(
    file: ty.TextIO,
    event_list: ty.List["MotionEvent"],
    input_files: ty.Optional[ty.Sequence[ty.Union[str, "ty.Any"]]] = None,
    frame_rate: ty.Optional[float] = None,
    frames_processed: ty.Optional[int] = None,
):
    """Write `event_list` to `file` as a versioned JSON report.

    Arguments:
        file: Text file to write the report to.
        event_list: Motion events detected by the scan.
        input_files: Paths of the video(s) that were scanned, if known.
        frame_rate: Average framerate of the input, if known.
        frames_processed: Number of frames processed by the scan, if known.
    """
    report = {
        "version": JSON_REPORT_VERSION,
        "generator": "DVR-Scan %s" % dvr_scan.__version__,
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input": {
            "files": [str(file) for file in input_files] if input_files else [],
            "frame_rate": float(frame_rate) if frame_rate is not None else None,
        },
        "scan": {
            "frames_processed": frames_processed,
            "num_events": len(event_list),
        },
        "events": [
            {
                "number": index + 1,
                "start": _time_entry(event.start),
                "end": _time_entry(event.end),
                "duration": _time_entry(event.end - event.start),
            }
            for index, event in enumerate(event_list)
        ],
    }
    json.dump(report, file, indent=2)
    file.write("\n")
