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
"""``dvr_scan.video_input`` Module

Provides multi-video input handling for DVR-Scan. Multiple input videos are treated as
a single, contiguous stream with a monotonic PTS-based timeline. Implements the
PySceneDetect `VideoStream` interface so the concatenation logic is backend-agnostic
and can be promoted upstream.
"""

import bisect
import logging
import typing as ty
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from scenedetect import FrameTimecode, VideoStream
from scenedetect.backends import AVAILABLE_BACKENDS
from scenedetect.backends.pyav import VideoStreamAv
from scenedetect.common import Timecode, TimecodeLike
from scenedetect.video_stream import VideoOpenFailure

logger = logging.getLogger("dvr_scan")

# Time base used for the global (concatenated) timeline.
GLOBAL_TIME_BASE = Fraction(1, 1000000)

# Tolerance in frames/sec above which a framerate mismatch between inputs is warned about.
FRAMERATE_DELTA_TOLERANCE: float = 0.1

# Max amount of consecutive decode failures to tolerate before giving up on a source.
MAX_CONSECUTIVE_DECODE_FAILURES: int = 8


class BackendUnavailable(Exception):
    """Raised when specified input backend is unavailable."""

    def __init__(
        self, backend: str, message: str = "Specified backend (%s) is not available on this system."
    ):
        super().__init__(message % backend)


@dataclass(frozen=True)
class AudioStreamInfo:
    """Metadata describing one audio stream of an input video."""

    index: int
    codec_name: str
    sample_rate: ty.Optional[int]
    channels: ty.Optional[int]
    layout: ty.Optional[str]
    time_base: ty.Optional[Fraction]
    start_time: ty.Optional[int]
    duration: ty.Optional[int]
    bit_rate: ty.Optional[int]


@dataclass(frozen=True)
class VideoStreamInfo:
    """Metadata describing the primary video stream of an input video."""

    index: int
    codec_name: str
    profile: ty.Optional[str]
    pix_fmt: ty.Optional[str]
    width: int
    height: int
    sample_aspect_ratio: ty.Optional[Fraction]
    time_base: ty.Optional[Fraction]
    start_time: ty.Optional[int]
    duration: ty.Optional[int]
    average_rate: ty.Optional[Fraction]
    frames: int
    bit_rate: ty.Optional[int]


@dataclass(frozen=True)
class SourceInfo:
    """Metadata for one input video, obtained by `probe_source` without decoding."""

    path: Path
    container_format: str
    video: VideoStreamInfo
    audio: ty.Tuple[AudioStreamInfo, ...]
    has_subtitles: bool
    duration: Fraction
    """Duration of the video stream in seconds (exact rational value)."""


@dataclass(frozen=True)
class EventSpan:
    """Portion of a single input video covered by a time span on the global timeline.
    Local times are relative to the start of that video, directly usable as seek targets
    or ffmpeg `-ss`/`-t` values."""

    source_index: int
    path: Path
    local_start: FrameTimecode
    local_end: FrameTimecode


def _exact_seconds(timecode: FrameTimecode) -> Fraction:
    """Time represented by `timecode` as an exact rational number of seconds."""
    return Fraction(timecode.pts) * timecode.time_base


def probe_source(path: ty.Union[str, Path]) -> SourceInfo:
    """Probe `path` for stream metadata using PyAV without decoding any frames.

    Raises:
        VideoOpenFailure: The file could not be opened or has no video stream.
    """
    path = Path(path)
    try:
        container = av.open(str(path))
    except FileNotFoundError:
        raise VideoOpenFailure(f"File not found: {path}") from None
    except OSError:
        raise
    except Exception as ex:
        raise VideoOpenFailure(str(ex)) from ex
    try:
        if not container.streams.video:
            raise VideoOpenFailure(f"No video stream found in {path.name}!")
        stream = container.streams.video[0]
        codec = stream.codec_context
        average_rate = stream.average_rate or stream.guessed_rate
        video_info = VideoStreamInfo(
            index=stream.index,
            codec_name=codec.name,
            profile=codec.profile,
            pix_fmt=codec.pix_fmt,
            width=codec.width,
            height=codec.height,
            sample_aspect_ratio=Fraction(codec.sample_aspect_ratio)
            if codec.sample_aspect_ratio
            else None,
            time_base=stream.time_base,
            start_time=stream.start_time,
            duration=stream.duration,
            average_rate=Fraction(average_rate) if average_rate else None,
            frames=stream.frames,
            bit_rate=codec.bit_rate,
        )
        audio_info = tuple(
            AudioStreamInfo(
                index=audio.index,
                codec_name=audio.codec_context.name,
                sample_rate=audio.codec_context.sample_rate,
                channels=audio.codec_context.channels,
                layout=audio.codec_context.layout.name if audio.codec_context.layout else None,
                time_base=audio.time_base,
                start_time=audio.start_time,
                duration=audio.duration,
                bit_rate=audio.codec_context.bit_rate,
            )
            for audio in container.streams.audio
        )
        # Calculate duration of the video stream in seconds, preferring stream-level
        # timing, then container duration, then an estimate from the frame count.
        duration = Fraction(0)
        if stream.duration is not None and stream.time_base is not None:
            duration = Fraction(stream.duration) * stream.time_base
        elif container.duration is not None and container.duration > 0:
            duration = Fraction(container.duration, av.time_base)
        elif stream.frames > 0 and video_info.average_rate:
            duration = Fraction(stream.frames) / video_info.average_rate
        return SourceInfo(
            path=path,
            container_format=container.format.name,
            video=video_info,
            audio=audio_info,
            has_subtitles=len(container.streams.subtitles) > 0,
            duration=duration,
        )
    finally:
        container.close()


# Upstream candidate: fold the corrupt-frame handling below into VideoStreamAv itself
# (see https://scenedetect.com/issues/258).
class VideoStreamAvTolerant(VideoStreamAv):
    """`VideoStreamAv` variant which skips over corrupt frames instead of failing.

    Tracks the number of packets which failed to decode via `decode_failures`."""

    def __init__(self, path: str, frame_rate: ty.Optional[Fraction] = None):
        super().__init__(path, frame_rate=frame_rate, threading_mode="AUTO")
        self._decode_failure_count: int = 0

    @property
    def decode_failures(self) -> int:
        """Number of packets which failed to decode (may indicate video corruption)."""
        return self._decode_failure_count

    def _normalized_pts(self) -> int:
        """PTS of the current frame relative to the start of the stream. Some files have
        a nonzero stream start_time (e.g. from edit lists); other backends report the
        first frame's presentation time as 0, so we must do the same."""
        assert self._frame is not None
        start_time = self._video_stream.start_time or 0
        if start_time and self._video_stream.time_base != self._frame.time_base:
            start_time = int(start_time * self._video_stream.time_base / self._frame.time_base)
        return self._frame.pts - start_time

    @property
    def position(self) -> FrameTimecode:
        """Current position within stream as FrameTimecode, normalized so the first frame
        of the stream has a presentation time of 0."""
        if self._frame is None or self._frame.pts is None or self._frame.time_base is None:
            return self.base_timecode
        timecode = Timecode(pts=self._normalized_pts(), time_base=self._frame.time_base)
        return FrameTimecode(timecode=timecode, fps=self.frame_rate)

    @property
    def position_ms(self) -> float:
        if self._frame is None or self._frame.pts is None or self._frame.time_base is None:
            return 0.0
        return float(self._normalized_pts() * self._frame.time_base) * 1000.0

    @property
    def frame_number(self) -> int:
        if self._frame is None or self._frame.pts is None or self._frame.time_base is None:
            return 0
        seconds = float(self._normalized_pts() * self._frame.time_base)
        return round(seconds * float(self.frame_rate)) + 1

    def read(self, decode: bool = True) -> ty.Union[np.ndarray, bool]:
        consecutive_failures = 0
        while True:
            try:
                return super().read(decode)
            except av.FFmpegError as ex:
                # NOTE: `av.error.EOFError` cannot reach here, the base class handles it.
                self._decode_failure_count += 1
                consecutive_failures += 1
                # The decoder generator is closed once an exception propagates through it;
                # recreating it resumes demuxing after the packet which failed to decode.
                self._decoder = None
                if consecutive_failures >= MAX_CONSECUTIVE_DECODE_FAILURES:
                    logger.error(
                        "Failed to decode %d consecutive frames (%s), stopping: %s",
                        consecutive_failures,
                        self.name,
                        str(ex),
                    )
                    return False
                logger.debug("Failed to decode frame in %s: %s", self.name, str(ex))


class VideoStreamConcat(VideoStream):
    """Concatenates multiple videos into a single, contiguous video stream with a
    monotonic PTS-based global timeline.

    The concatenation logic is backend-agnostic: frames are read through any PySceneDetect
    `VideoStream` backend, selected by name (default `pyav`).

    Raises:
        VideoOpenFailure: Failed to open a video, or video parameters don't match.
        BackendUnavailable: The specified backend is not available on this system.
    """

    BACKEND_NAME = "concat"

    def __init__(
        self,
        paths: ty.List[ty.Union[str, Path]],
        backend: str = "pyav",
        frame_rate: ty.Optional[Fraction] = None,
    ):
        assert paths
        backend = backend.lower()
        if backend != "pyav" and backend not in AVAILABLE_BACKENDS:
            raise BackendUnavailable(backend=backend)
        self._paths: ty.List[Path] = [Path(p) for p in paths]
        self._child_backend: str = backend
        self._frame_rate_override = frame_rate

        # Probe all inputs up front for validation and metadata, then only keep one
        # source open at a time for decoding.
        self._sources: ty.List[SourceInfo] = []
        for path in self._paths:
            try:
                self._sources.append(probe_source(path))
            except VideoOpenFailure:
                logger.error(f"Error: Couldn't load video {path}")
                raise
        self._validate_sources()

        # Global start time of each source in exact rational seconds. Has one extra
        # entry at the end holding the total (declared) duration. Values after the
        # current source are estimates from container metadata, and are corrected
        # once the actual end of each source is reached during decode.
        self._offsets: ty.List[Fraction] = [Fraction(0)]
        for source in self._sources:
            self._offsets.append(self._offsets[-1] + source.duration)

        self._index: int = 0
        self._frames_prior: int = 0
        self._decode_failures_prior: int = 0
        self._cap: VideoStream = self._open_source(0)

    #
    # Concatenation Logic
    #

    def _validate_sources(self):
        first = self._sources[0].video
        for source in self._sources[1:]:
            video = source.video
            logger.info(
                "Appending video %s (%d x %d at %2.3f FPS).",
                source.path.name,
                video.width,
                video.height,
                float(video.average_rate) if video.average_rate else 0.0,
            )
            if (video.width, video.height) != (first.width, first.height):
                logger.error("Error: Video resolution does not match the first input.")
                raise VideoOpenFailure("Video resolutions must match to be concatenated!")
            if (
                video.average_rate
                and first.average_rate
                and abs(float(video.average_rate) - float(first.average_rate))
                > FRAMERATE_DELTA_TOLERANCE
            ):
                logger.warning(
                    "Warning: framerate does not match first input. Timing is based on "
                    "presentation timestamps, but reported frame numbers may be inaccurate."
                )

    def _open_source(self, index: int) -> VideoStream:
        path = str(self._paths[index])
        if index == 0:
            source = self._sources[0]
            logger.info(
                "Opened video %s (%d x %d at %2.3f FPS).",
                source.path.name,
                source.video.width,
                source.video.height,
                float(source.video.average_rate) if source.video.average_rate else 0.0,
            )
        if self._child_backend == "pyav":
            return VideoStreamAvTolerant(path, frame_rate=self._frame_rate_override)
        backend_type = AVAILABLE_BACKENDS[self._child_backend]
        if self._frame_rate_override is not None:
            return backend_type(path, frame_rate=self._frame_rate_override)
        return backend_type(path)

    def _child_decode_failures(self) -> int:
        return getattr(self._cap, "decode_failures", getattr(self._cap, "_decode_failures", 0))

    def _child_position_seconds(self) -> Fraction:
        """Position of the current source as exact rational seconds (local timeline)."""
        return _exact_seconds(self._cap.position)

    def _finish_current_source(self):
        """Correct the declared offset of the next source now that the actual end of the
        current source is known, guaranteeing strictly monotonic PTS across the seam even
        when container metadata is inaccurate."""
        self._decode_failures_prior += self._child_decode_failures()
        self._frames_prior += self._cap.frame_number
        actual_end = (
            self._offsets[self._index]
            + self._child_position_seconds()
            + Fraction(1) / self._cap.frame_rate
        )
        declared_end = self._offsets[self._index + 1]
        if actual_end > declared_end:
            delta = actual_end - declared_end
            for i in range(self._index + 1, len(self._offsets)):
                self._offsets[i] += delta

    def read(self, decode: bool = True) -> ty.Union[np.ndarray, bool]:
        """Read/decode the next frame. Returns False when all inputs have been processed."""
        while True:
            result = self._cap.read(decode=decode)
            if result is not False:
                return result
            if (self._index + 1) >= len(self._paths):
                logger.debug("No more input to process.")
                return False
            self._finish_current_source()
            self._index += 1
            logger.info(f"Processing complete, opening next video: {self._paths[self._index]}")
            self._cap = self._open_source(self._index)

    def seek(self, target: TimecodeLike):
        """Seek to `target` on the global timeline. Supports seeking across sources in
        either direction."""
        if not isinstance(target, FrameTimecode):
            target = FrameTimecode(target, self.frame_rate)
        if target < 0:
            raise ValueError("Target seek position cannot be negative!")
        target_seconds = _exact_seconds(target)
        # Find the last source which starts at or before the target.
        index = bisect.bisect_right(self._offsets, target_seconds) - 1
        index = max(0, min(index, len(self._paths) - 1))
        if index != self._index:
            self._decode_failures_prior += self._child_decode_failures()
            self._frames_prior = sum(source.video.frames for source in self._sources[:index])
            self._index = index
            self._cap = self._open_source(index)
        local_seconds = target_seconds - self._offsets[index]
        self._cap.seek(float(local_seconds))

    def reset(self):
        """Close and re-open the stream (equivalent to seeking back to the beginning)."""
        self._index = 0
        self._frames_prior = 0
        self._decode_failures_prior = 0
        self._cap = self._open_source(0)

    #
    # VideoStream Properties
    #

    @property
    def path(self) -> str:
        """Path of the first input video."""
        return str(self._paths[0])

    @property
    def name(self) -> str:
        """Name of the first input video, without extension."""
        return self._paths[0].stem

    @property
    def is_seekable(self) -> bool:
        return self._cap.is_seekable

    @property
    def frame_rate(self) -> Fraction:
        """Average framerate of the first input video. Individual sources may vary; use
        `position` for accurate timing."""
        if self._frame_rate_override is not None:
            return self._frame_rate_override
        average_rate = self._sources[0].video.average_rate
        return average_rate if average_rate else self._cap.frame_rate

    @property
    def duration(self) -> FrameTimecode:
        """Total duration of all input videos combined. May be inaccurate."""
        return self.base_timecode + float(self._offsets[-1])

    @property
    def frame_size(self) -> ty.Tuple[int, int]:
        """Video resolution (width x height) in pixels."""
        return (self._sources[0].video.width, self._sources[0].video.height)

    @property
    def aspect_ratio(self) -> float:
        return self._cap.aspect_ratio

    @property
    def position(self) -> FrameTimecode:
        """Presentation time of the last-read frame on the global timeline (the first
        frame of the first video has a presentation time of 0)."""
        global_seconds = self._offsets[self._index] + self._child_position_seconds()
        return FrameTimecode(
            timecode=Timecode(
                pts=round(global_seconds / GLOBAL_TIME_BASE), time_base=GLOBAL_TIME_BASE
            ),
            fps=self.frame_rate,
        )

    @property
    def position_ms(self) -> float:
        """Presentation time of the last-read frame in milliseconds on the global timeline."""
        return float((self._offsets[self._index] + self._child_position_seconds()) * 1000)

    @property
    def frame_number(self) -> int:
        """Number of frames read so far across all sources."""
        return self._frames_prior + self._cap.frame_number

    #
    # DVR-Scan Extensions
    #

    @property
    def paths(self) -> ty.List[Path]:
        """All paths this object was created with."""
        return self._paths

    @property
    def sources(self) -> ty.List[SourceInfo]:
        """Stream metadata for each input video."""
        return self._sources

    @property
    def child_backend(self) -> str:
        """Name of the backend used to decode each input video."""
        return self._cap.BACKEND_NAME

    @property
    def resolution(self) -> ty.Tuple[int, int]:
        """Video resolution (width x height) in pixels. Alias for `frame_size`."""
        return self.frame_size

    @property
    def framerate(self) -> Fraction:
        """Video framerate (frames/sec). Alias for `frame_rate`."""
        return self.frame_rate

    @property
    def total_frames(self) -> int:
        """Total number of frames of all input videos combined. May be inaccurate."""
        total = 0
        for source in self._sources:
            if source.video.frames > 0:
                total += source.video.frames
            elif source.video.average_rate:
                total += round(source.duration * source.video.average_rate)
        return total

    @property
    def decode_failures(self) -> int:
        """Number of frames which failed to decode (may indicate video corruption)."""
        return self._decode_failures_prior + self._child_decode_failures()

    def map_span(self, start: FrameTimecode, end: FrameTimecode) -> ty.List[EventSpan]:
        """Map a time span on the global timeline to the input video(s) covering it.
        A span which straddles one or more file boundaries yields multiple entries."""
        start_seconds = _exact_seconds(start)
        end_seconds = _exact_seconds(end)
        spans: ty.List[EventSpan] = []
        for index, source in enumerate(self._sources):
            source_start, source_end = self._offsets[index], self._offsets[index + 1]
            if end_seconds <= source_start:
                break
            if start_seconds >= source_end:
                continue
            local_start = max(Fraction(0), start_seconds - source_start)
            local_end = min(source_end - source_start, end_seconds - source_start)
            fps = source.video.average_rate if source.video.average_rate else self.frame_rate
            spans.append(
                EventSpan(
                    source_index=index,
                    path=source.path,
                    local_start=FrameTimecode(
                        timecode=Timecode(
                            pts=round(local_start / GLOBAL_TIME_BASE), time_base=GLOBAL_TIME_BASE
                        ),
                        fps=fps,
                    ),
                    local_end=FrameTimecode(
                        timecode=Timecode(
                            pts=round(local_end / GLOBAL_TIME_BASE), time_base=GLOBAL_TIME_BASE
                        ),
                        fps=fps,
                    ),
                )
            )
        return spans


def open_input(
    paths: ty.List[ty.Union[str, Path]],
    input_mode: str = "pyav",
    frame_rate: ty.Optional[Fraction] = None,
) -> VideoStreamConcat:
    """Open one or more videos as a single contiguous stream using the given backend."""
    return VideoStreamConcat(paths, backend=input_mode, frame_rate=frame_rate)
