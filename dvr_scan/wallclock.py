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
"""``dvr_scan.wallclock`` Module

Date and time of recording for the timecode overlay (the `time-code-start` option).

The option gives the date and time of the first frame of each input video. The time of a
frame is that start time plus the presentation time of the frame in its video. Values:

 - `none`: no date and time. The overlay shows the position in the video.
 - `filename`: read the start time from the file name (e.g. `20261116233730.avi` or
   `VID_20261116_233730.mp4`).
 - `modified`: the file modified time minus the duration of the video. Most cameras set
   the modified time when a clip ends.
 - a date and time (e.g. `2026-11-16 23:37:30`): the start time of the first input.
   Later inputs continue from it, as if the recording was continuous.

All times are local times with no time zone, as cameras write them.
"""

import logging
import re
import typing as ty
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

from scenedetect import FrameTimecode

from dvr_scan.video_input import SourceInfo, VideoStreamConcat

logger = logging.getLogger("dvr_scan")

NONE = "none"
FILENAME = "filename"
MODIFIED = "modified"
TIME_CODE_START_CHOICES = (NONE, FILENAME, MODIFIED)
"""Values of `time-code-start` other than a date and time."""

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
"""Format of the date and time that the overlay shows."""

# A date and time in a file name: YYYYMMDDhhmmss, with optional separators between the
# parts (e.g. 20261116233730, 20261116_233730, 2026-11-16_23-37-30). The digit guards
# prevent a match inside a longer number.
_FILENAME_DATETIME = re.compile(
    r"(?<!\d)(\d{4})[-_.]?(\d{2})[-_.]?(\d{2})[-_.T ]?(\d{2})[-_.:]?(\d{2})[-_.:]?(\d{2})(?!\d)"
)
# A year outside this range is more likely a counter than a date.
_MIN_YEAR = 1990
_MAX_YEAR = 2100


def parse_time_code_start(value: str) -> ty.Union[str, datetime]:
    """Parse a `time-code-start` value. Returns one of `TIME_CODE_START_CHOICES`, or the
    date and time that the user gave.

    Raises:
        ValueError: `value` is not a choice or a date and time.
    """
    text = str(value).strip()
    if text.lower() in TIME_CODE_START_CHOICES:
        return text.lower()
    try:
        start = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(
            f"Invalid time-code-start: {text}. Use one of: {', '.join(TIME_CODE_START_CHOICES)},"
            " or a date and time as YYYY-MM-DD HH:MM:SS."
        ) from None
    if start.tzinfo is not None:
        start = start.astimezone().replace(tzinfo=None)
    return start


def start_time_from_filename(path: ty.Union[str, Path]) -> ty.Optional[datetime]:
    """Date and time in the file name of `path`, or None if the name has none."""
    for match in _FILENAME_DATETIME.finditer(Path(path).stem):
        year, month, day, hour, minute, second = (int(part) for part in match.groups())
        if not _MIN_YEAR <= year <= _MAX_YEAR:
            continue
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            continue
    return None


def start_time_from_modified(
    path: ty.Union[str, Path], duration: ty.Union[Fraction, float]
) -> ty.Optional[datetime]:
    """File modified time of `path` minus `duration` (seconds), or None on error."""
    try:
        modified = datetime.fromtimestamp(Path(path).stat().st_mtime)
    except (OSError, OverflowError, ValueError) as ex:
        logger.debug("Failed to get modified time of %s: %s", path, ex)
        return None
    return modified - timedelta(seconds=float(duration))


def _source_start_time(mode: str, source: SourceInfo) -> ty.Optional[datetime]:
    if mode == FILENAME:
        return start_time_from_filename(source.path)
    assert mode == MODIFIED
    return start_time_from_modified(source.path, source.duration)


class WallClock:
    """Gives the date and time of recording for a time on the global timeline of a
    `VideoStreamConcat`. Use `WallClock.create` to make one."""

    def __init__(self, stream: VideoStreamConcat, mode: ty.Union[str, datetime]):
        self._input = stream
        # Start time of the first input, for a date and time given by the user.
        self._start: ty.Optional[datetime] = None
        # Start time of each input, for the other modes. None if not known.
        self._source_starts: ty.List[ty.Optional[datetime]] = []
        if isinstance(mode, datetime):
            self._start = mode
            if len(stream.sources) > 1:
                logger.warning(
                    "time-code-start: the date and time apply to the first input. Times for"
                    " later inputs assume that the recording was continuous."
                )
            return
        for source in stream.sources:
            start = _source_start_time(mode, source)
            if start is None:
                logger.warning(
                    "time-code-start: no %s date and time for %s. The timecode shows the"
                    " position in the video for this input.",
                    "file name" if mode == FILENAME else "modified",
                    source.path.name,
                )
            else:
                logger.debug("Start time of %s: %s", source.path.name, start)
            self._source_starts.append(start)

    @staticmethod
    def create(stream: VideoStreamConcat, setting: str) -> ty.Optional["WallClock"]:
        """Make a `WallClock` for the `time-code-start` value `setting`, or return None if
        the value is `none`.

        Raises:
            ValueError: `setting` is not a valid value.
        """
        mode = parse_time_code_start(setting)
        if mode == NONE:
            return None
        return WallClock(stream, mode)

    def get_text(self, timecode: FrameTimecode) -> ty.Optional[str]:
        """Date and time of the frame at `timecode`, or None if not known.

        Safe to call from a thread other than the one that reads the input, for frames
        that have been read already (see `VideoStreamConcat.locate`)."""
        if self._start is not None:
            when = self._start + timedelta(seconds=timecode.seconds)
            return when.strftime(DATETIME_FORMAT)
        index, local_seconds = self._input.locate(timecode)
        start = self._source_starts[index]
        if start is None:
            return None
        return (start + timedelta(seconds=float(local_seconds))).strftime(DATETIME_FORMAT)
