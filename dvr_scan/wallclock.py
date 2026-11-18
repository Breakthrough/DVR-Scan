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
 - `modified`: the file modified time minus the duration of the video. Many cameras set
   the modified time when a clip ends; cameras without a clock write a fixed date.
 - a date and time (e.g. `2026-11-16 23:37:30`): the start time of the first input. If
   all input file names contain a date and time, later inputs are placed using the
   differences between their file name times (which corrects camera clock and time zone
   errors and allows gaps between clips within one power cycle). Otherwise, later inputs
   continue from the first input, as if the recording was continuous.

All times are local times with no time zone, as cameras write them.
"""

import logging
import re
import typing as ty
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

from scenedetect import FrameTimecode

from dvr_scan.video_input import VideoStreamConcat

logger = logging.getLogger("dvr_scan")

NONE = "none"
FILENAME = "filename"
MODIFIED = "modified"
TIME_CODE_START_CHOICES = (NONE, FILENAME, MODIFIED)
"""Values of `time-code-start` other than a date and time."""

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
"""Format of the date and time that the overlay shows."""

# A date and time in a file name: YYYYMMDDhhmmss, with consistent separators inside the
# date (YYYYMMDD or YYYY<sep>MM<sep>DD) and time (hhmmss or hh<sep>mm<sep>ss) parts, e.g.
# 20261116233730, 20261116_233730, 2026-11-16_23-37-30, 2026-11-16t23:37:30. Requiring
# consistent separators prevents a 4-digit prefix or year from being split across fields, and
# the digit guards prevent matching inside a longer number.
_FILENAME_DATETIME = re.compile(
    r"(?<!\d)"
    r"(?:(?P<y1>\d{4})(?P<m1>\d{2})(?P<d1>\d{2})"
    r"|(?P<y2>\d{4})(?P<dsep>[-_.])(?P<m2>\d{2})(?P=dsep)(?P<d2>\d{2}))"
    r"[-_.Tt ]?"
    r"(?:(?P<H1>\d{2})(?P<M1>\d{2})(?P<S1>\d{2})"
    r"|(?P<H2>\d{2})(?P<tsep>[-_.:])(?P<M2>\d{2})(?P=tsep)(?P<S2>\d{2}))"
    r"(?!\d)"
)
# A year outside this range is more likely a counter than a date.
_MIN_YEAR = 1990
_MAX_YEAR = 2100


def parse_time_code_start(value: str) -> ty.Union[str, datetime]:
    """Parse a `time-code-start` value. Returns one of `TIME_CODE_START_CHOICES`, or the
    local date and time that the user gave.

    Raises:
        ValueError: `value` is not a choice or a local date and time without a time zone.
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
        raise ValueError(
            f"Invalid time-code-start: {text}. Give a local date and time without a time zone,"
            " e.g. YYYY-MM-DD HH:MM:SS."
        )
    return start


def normalize_time_code_start(value: str) -> str:
    """Validate and normalize a `time-code-start` value to a string (lowercasing keyword
    choices)."""
    parsed = parse_time_code_start(value)
    return parsed if isinstance(parsed, str) else str(value).strip()


def start_time_from_filename(path: ty.Union[str, Path]) -> ty.Optional[datetime]:
    """Date and time in the file name of `path`, or None if the name has none."""
    stem = Path(path).stem
    pos = 0
    while (match := _FILENAME_DATETIME.search(stem, pos)) is not None:
        year = int(match.group("y1") or match.group("y2"))
        month = int(match.group("m1") or match.group("m2"))
        day = int(match.group("d1") or match.group("d2"))
        hour = int(match.group("H1") or match.group("H2"))
        minute = int(match.group("M1") or match.group("M2"))
        second = int(match.group("S1") or match.group("S2"))
        if _MIN_YEAR <= year <= _MAX_YEAR:
            try:
                return datetime(year, month, day, hour, minute, second)
            except ValueError:
                pass
        pos = match.start() + 1
    return None


def _modified_time(path: ty.Union[str, Path]) -> ty.Optional[datetime]:
    """File modified time of `path` as local datetime, or None on error."""
    try:
        return datetime.fromtimestamp(Path(path).stat().st_mtime)
    except (OSError, OverflowError, ValueError) as ex:
        logger.debug("Failed to get modified time of %s: %s", path, ex)
        return None


def start_time_from_modified(
    path: ty.Union[str, Path], duration: ty.Union[Fraction, float]
) -> ty.Optional[datetime]:
    """File modified time of `path` minus `duration` (seconds), or None on error."""
    modified = _modified_time(path)
    if modified is None:
        return None
    return modified - timedelta(seconds=float(duration))


def _warn_missing(label: str, missing: ty.List[str], total: int) -> None:
    if len(missing) == 1:
        logger.warning(
            "time-code-start: no %s date and time for %s. The timecode shows the"
            " position in the video for this input.",
            label,
            missing[0],
        )
    else:
        logger.warning(
            "time-code-start: no %s date and time for %d of %d inputs (e.g. %s). The"
            " timecode shows the position in the video for those inputs.",
            label,
            len(missing),
            total,
            missing[0],
        )


class WallClock:
    """Gives the date and time of recording for a time on the global timeline of a
    `VideoStreamConcat`. Use `WallClock.create` to make one."""

    def __init__(self, stream: VideoStreamConcat, mode: ty.Union[str, datetime]):
        self._input = stream
        # Start time of the first input, for continuous explicit-start mode.
        self._start: ty.Optional[datetime] = None
        # Start time of each input, for per-source modes. None if not known.
        self._source_starts: ty.List[ty.Optional[datetime]] = []
        if isinstance(mode, datetime):
            self._init_explicit(stream, mode)
            return
        if mode == FILENAME:
            self._init_filename(stream)
            return
        assert mode == MODIFIED
        self._init_modified(stream)

    def _init_explicit(self, stream: VideoStreamConcat, start: datetime) -> None:
        if len(stream.sources) <= 1:
            self._start = start
            return
        parsed = [
            name_time
            for source in stream.sources
            if (name_time := start_time_from_filename(source.path)) is not None
        ]
        if len(parsed) != len(stream.sources):
            self._start = start
            logger.warning(
                "time-code-start: not all input file names have a date and time. Times for"
                " later inputs assume that the recording was continuous."
            )
            return
        if any(curr < prev for prev, curr in zip(parsed, parsed[1:], strict=False)):
            logger.warning(
                "time-code-start: input file name times are not in order; timestamps still"
                " use file name differences, which may be wrong if the camera clock reset"
                " between files."
            )
        offset = start - parsed[0]
        for source, name_time in zip(stream.sources, parsed, strict=True):
            source_start = name_time + offset
            logger.debug("Start time of %s: %s", source.path.name, source_start)
            self._source_starts.append(source_start)

    def _init_filename(self, stream: VideoStreamConcat) -> None:
        missing: ty.List[str] = []
        for source in stream.sources:
            start = start_time_from_filename(source.path)
            if start is None:
                missing.append(source.path.name)
            else:
                logger.debug("Start time of %s: %s", source.path.name, start)
            self._source_starts.append(start)
        if missing:
            _warn_missing("file name", missing, len(stream.sources))

    def _init_modified(self, stream: VideoStreamConcat) -> None:
        missing: ty.List[str] = []
        zero_duration: ty.List[str] = []
        mtimes: ty.List[datetime] = []
        for index, source in enumerate(stream.sources):
            modified = _modified_time(source.path)
            if modified is None:
                missing.append(source.path.name)
                self._source_starts.append(None)
                continue
            mtimes.append(modified)
            duration = stream.source_duration(index)
            if duration <= 0:
                zero_duration.append(source.path.name)
            start = modified - timedelta(seconds=float(duration))
            logger.debug("Start time of %s: %s", source.path.name, start)
            self._source_starts.append(start)
        if missing:
            _warn_missing("modified", missing, len(stream.sources))
        if zero_duration:
            logger.warning(
                "time-code-start: duration unknown for %d of %d inputs (e.g. %s); using"
                " file modified time directly as start time.",
                len(zero_duration),
                len(stream.sources),
                zero_duration[0],
            )
        if len(mtimes) > 1 and len({m.replace(microsecond=0) for m in mtimes}) == 1:
            logger.warning(
                "time-code-start: all %d inputs have the same modified time (%s). Cameras"
                " without a clock write a fixed date, so the timecode may not be accurate.",
                len(mtimes),
                mtimes[0].strftime(DATETIME_FORMAT),
            )

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
