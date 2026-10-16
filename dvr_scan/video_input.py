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
a single, contiguous stream with a monotonic PTS-based timeline.

The concatenation logic itself lives upstream in PySceneDetect
(`scenedetect.backends.concat.VideoStreamConcat`); this module adds the DVR-Scan specific
parts on top of it: a PyAV-based metadata probe (`probe_source`/`SourceInfo`, which also
describes audio streams for the encoder), the `BackendUnavailable` error, and a few
convenience properties used by the scanner.
"""

import logging
import typing as ty
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av
from scenedetect.backends import AVAILABLE_BACKENDS
from scenedetect.backends.concat import SourceSpan
from scenedetect.backends.concat import VideoStreamConcat as _VideoStreamConcat
from scenedetect.video_stream import VideoOpenFailure

logger = logging.getLogger("dvr_scan")

# Tolerance in frames/sec above which a framerate mismatch between inputs is warned about.
FRAMERATE_DELTA_TOLERANCE: float = 0.1


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


EventSpan = SourceSpan
"""Portion of a single input video covered by a time span on the global timeline, as
returned by `VideoStreamConcat.map_span`. Alias of `scenedetect.backends.concat.SourceSpan`."""


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


def _describe(source: SourceInfo) -> ty.Tuple[str, int, int, float]:
    video = source.video
    fps = float(video.average_rate) if video.average_rate else 0.0
    return (source.path.name, video.width, video.height, fps)


class VideoStreamConcat(_VideoStreamConcat):
    """Concatenates multiple videos into a single, contiguous video stream with a
    monotonic PTS-based global timeline (see `scenedetect.backends.concat`).

    Extends the upstream implementation with stream metadata probed via PyAV
    (`sources`), which the encoder uses for audio extraction, and requires the requested
    backend to be available rather than silently falling back to OpenCV.

    Raises:
        VideoOpenFailure: Failed to open a video, or video parameters don't match.
        BackendUnavailable: The specified backend is not available on this system.
    """

    def __init__(
        self,
        paths: ty.List[ty.Union[str, Path]],
        backend: str = "pyav",
        frame_rate: ty.Optional[Fraction] = None,
    ):
        assert paths
        backend = backend.lower()
        if backend not in AVAILABLE_BACKENDS:
            raise BackendUnavailable(backend=backend)
        # Probe all inputs up front for stream metadata (including audio), which the
        # child backends do not expose.
        self._source_info: ty.List[SourceInfo] = []
        for path in paths:
            try:
                self._source_info.append(probe_source(path))
            except VideoOpenFailure:
                logger.error(f"Error: Couldn't load video {path}")
                raise
        logger.info("Opened video %s (%d x %d at %2.3f FPS).", *_describe(self._source_info[0]))
        first_rate = self._source_info[0].video.average_rate
        for source in self._source_info[1:]:
            logger.info("Appending video %s (%d x %d at %2.3f FPS).", *_describe(source))
            # Upstream compares the nominal rate of each child backend; compare the probed
            # average rates too, which differ for VFR inputs and affect frame-based params.
            if first_rate and source.video.average_rate:
                if abs(float(source.video.average_rate - first_rate)) > FRAMERATE_DELTA_TOLERANCE:
                    logger.warning(
                        "Framerate of %s (%2.3f FPS) does not match the first input (%2.3f FPS)."
                        " Frame numbers may be inaccurate; event times are unaffected.",
                        source.path.name,
                        float(source.video.average_rate),
                        float(first_rate),
                    )
        # Enable frame threading for PyAV; other backends do not accept this option.
        kwargs = {"threading_mode": "AUTO"} if backend == "pyav" else {}
        super().__init__(paths, frame_rate=frame_rate, backend=backend, **kwargs)
        # WORKAROUND(scenedetect 0.7.2): the upstream constructor estimates where each input
        # starts on the global timeline from the child backend's declared duration, which
        # for PyAV is the frame count divided by the nominal rate. That is wrong for VFR
        # inputs (e.g. 23s instead of 34s), so `map_span`/`seek` would resolve times near
        # the end of such an input to the wrong file until it has been fully decoded.
        # Rebuild the estimates from the probed stream durations, which are time-based.
        # Depends on the private `_offsets` list; remove once upstream uses exact durations.
        offsets = [Fraction(0)]
        for index, source in enumerate(self._source_info):
            declared = source.duration if source.duration > 0 else self._sources[index].duration
            offsets.append(offsets[-1] + declared)
        self._offsets = offsets

    @property
    def sources(self) -> ty.List[SourceInfo]:
        """Stream metadata for each input video."""
        return self._source_info

    @property
    def resolution(self) -> ty.Tuple[int, int]:
        """Video resolution (width x height) in pixels. Alias for `frame_size`."""
        return self.frame_size

    @property
    def frame_rate(self) -> Fraction:
        """Average framerate of the first input video (frames/sec).

        The probed `average_rate` is preferred over the child backend's rate (PyAV reports
        the nominal `guessed_rate`), as frame-based parameters are converted to time using
        this value and the average is more accurate for inputs with irregular timing."""
        if self._frame_rate_override is not None:
            return Fraction(self._frame_rate_override)
        average_rate = self._source_info[0].video.average_rate
        return average_rate if average_rate else super().frame_rate

    @property
    def framerate(self) -> Fraction:
        """Video framerate (frames/sec). Alias for `frame_rate`."""
        return self.frame_rate

    @property
    def total_frames(self) -> int:
        """Total number of frames of all input videos combined. May be inaccurate."""
        total = 0
        for source in self._source_info:
            if source.video.frames > 0:
                total += source.video.frames
            elif source.video.average_rate:
                total += round(source.duration * source.video.average_rate)
        return total


def open_input(
    paths: ty.List[ty.Union[str, Path]],
    input_mode: str = "pyav",
    frame_rate: ty.Optional[Fraction] = None,
) -> VideoStreamConcat:
    """Open one or more videos as a single contiguous stream using the given backend."""
    return VideoStreamConcat(paths, backend=input_mode, frame_rate=frame_rate)
