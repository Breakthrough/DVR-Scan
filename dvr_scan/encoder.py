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
"""``dvr_scan.encoder`` Module

Contains encoders used to write motion events to disk (`EventEncoder` and its
implementations), and the `OutputMode` type used to select between them.

Encoders receive fully-composited BGR frames (overlays are drawn by the scanner
before frames reach the encoder) and/or event boundaries, and are responsible for
producing the resulting output files.
"""

import logging
import subprocess
import typing as ty
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import cv2
import numpy as np
from scenedetect import FrameTimecode

logger = logging.getLogger("dvr_scan")

DEFAULT_VIDEOWRITER_CODEC = "XVID"
"""Default codec to use with OpenCV VideoWriter."""

DEFAULT_FFMPEG_INPUT_ARGS = "-v error"
"""Default arguments to add before input when invoking ffmpeg."""

DEFAULT_FFMPEG_OUTPUT_ARGS = (
    "-map 0:v:0 -map 0:a? -map 0:s? -c:v libx264 -preset veryfast -crf 22 -c:a aac"
)
"""Default arguments passed to ffmpeg when using OutputMode.FFMPEG."""

COPY_MODE_OUTPUT_ARGS = "-map 0:v:0 -map 0:a? -map 0:s? -c:v copy -c:a copy"
"""Default arguments passed to ffmpeg when using OutputMode.COPY."""

# TODO(#89): Add ability to set output name template.
OUTPUT_FILE_TEMPLATE = "{VIDEO_NAME}.DSME_{EVENT_NUMBER}.{EXTENSION}"
"""Template to use for generating output files."""


class OutputMode(Enum):
    """Mode to export each motion event using."""

    SCAN_ONLY = 1
    """Don't generate any output files."""
    OPENCV = 2
    """Output using OpenCV VideoWriter."""
    COPY = 3
    """Output using ffmpeg in codec-copy mode."""
    FFMPEG = 4
    """Output using ffmpeg."""

    def __str__(self):
        if self == OutputMode.SCAN_ONLY:
            return "SCAN_ONLY"
        if self == OutputMode.OPENCV:
            return "OPENCV"
        if self == OutputMode.COPY:
            return "COPY"
        if self == OutputMode.FFMPEG:
            return "FFMPEG"


def _extract_event_ffmpeg(
    input_path: Path,
    output_path: Path,
    start_time: FrameTimecode,
    end_time: FrameTimecode,
    ffmpeg_input_args: str,
    ffmpeg_out_args: str,
    log_args: bool = False,
) -> bool:
    args: ty.List[str] = [
        "ffmpeg",
        "-y",
        "-nostdin",
        *ffmpeg_input_args.split(" "),
        "-ss",
        start_time.get_timecode(),
        "-i",
        str(input_path),
        "-t",
        (end_time - start_time).get_timecode(),
        *ffmpeg_out_args.split(" "),
        str(output_path),
    ]
    if log_args or logger.getEffectiveLevel() == logging.DEBUG:
        logger.info("%s", " ".join(args))
    # Invoke the command and capture the output (exception is raised on non-zero return code).
    output: str = subprocess.check_output(
        args=args,
        text=True,
        stderr=subprocess.STDOUT,
    )
    # Log any output we get from the ffmpeg process.
    if output:
        verbosity = logging.INFO
        # Upgrade verbosity depending on specified ffmpeg verbosity (if any).
        if any(["-v %s" % v in ffmpeg_input_args for v in ["panic", "fatal", "error"]]):
            verbosity = logging.ERROR
        elif "-v warning" in ffmpeg_input_args:
            verbosity = logging.WARNING
        logger.log(
            verbosity,
            "ffmpeg output:\n\n%s",
            output,
        )


def _create_video_writer(
    path: Path,
    output_dir: ty.Optional[Path],
    fourcc: ty.Any,
    frame_rate: float,
    frame_size: ty.Tuple[int, int],
) -> cv2.VideoWriter:
    """Create a new cv2.VideoWriter, resolving `path` against `output_dir` if set."""
    if output_dir:
        path = output_dir / path
    return cv2.VideoWriter(str(path), fourcc, float(frame_rate), frame_size)


@dataclass
class EventContext:
    """Information about a completed motion event passed to `EventEncoder.finish_event`."""

    event_number: int
    """1-based index of the event within the current scan."""
    start: FrameTimecode
    """Presentation time of the start of the event on the input timeline."""
    end: FrameTimecode
    """Presentation time of the end of the event on the input timeline."""


class EventEncoder(ABC):
    """Interface for writing motion events to disk.

    Encoders either consume every frame of an event as it is processed
    (`STREAMS_FRAMES` is True, frames arrive via `write_frame`), or generate
    output from the source video using only the event boundaries provided to
    `finish_event`."""

    STREAMS_FRAMES: bool = False
    """Whether the scanner must feed each event frame to `write_frame`."""
    SUPPORTS_COMBINED_OUTPUT: bool = False
    """Whether all events can be concatenated into a single output file (-o/--output)."""
    SUPPORTS_MULTIPLE_INPUTS: bool = False
    """Whether events can be generated from a scan of multiple concatenated inputs."""
    SUPPORTS_OVERLAYS: bool = False
    """Whether frames with overlays (e.g. bounding boxes) can be written."""
    EXTENSION: str = "mp4"
    """Extension to use for generated output files."""

    def write_frame(self, frame_bgr: np.ndarray, timecode: FrameTimecode):
        """Write a frame belonging to the current event. Only called if `STREAMS_FRAMES`."""
        raise NotImplementedError()

    @abstractmethod
    def finish_event(self, context: EventContext):
        """Called at the end of each motion event to finalize its output."""
        raise NotImplementedError()

    def close(self):  # noqa: B027 - overriding is optional, default is a no-op.
        """Release any resources held by the encoder. Called once scanning completes."""


class OpenCVEncoder(EventEncoder):
    """Encodes events by writing frames with an OpenCV VideoWriter (OutputMode.OPENCV)."""

    STREAMS_FRAMES = True
    SUPPORTS_COMBINED_OUTPUT = True
    SUPPORTS_MULTIPLE_INPUTS = True
    SUPPORTS_OVERLAYS = True
    EXTENSION = "avi"

    def __init__(
        self,
        fourcc: ty.Any,
        frame_rate: float,
        video_name: str,
        output_dir: ty.Optional[Path],
        comp_file: ty.Optional[Path],
        completed_events: int = 0,
    ):
        """Arguments:
        fourcc: OpenCV fourcc code (from cv2.VideoWriter_fourcc) to encode with.
        frame_rate: Effective framerate of the output (frame-skip corrected).
        video_name: Name of the (first) input video, used as a filename template.
        output_dir: If set, folder where output files will be written to.
        comp_file: If set, single video that all motion events will be written to.
        completed_events: Events already written by a previous scan, so output file
            numbering continues instead of restarting.
        """
        self._fourcc = fourcc
        self._frame_rate = frame_rate
        self._video_name = video_name
        self._output_dir = output_dir
        self._comp_file = comp_file
        self._video_writer: ty.Optional[cv2.VideoWriter] = None
        # Completed events; the in-progress event is numbered `self._num_events + 1`.
        self._num_events = completed_events

    def write_frame(self, frame_bgr: np.ndarray, timecode: FrameTimecode):
        if self._video_writer is None:
            output_path = (
                self._comp_file
                if self._comp_file
                else Path(
                    OUTPUT_FILE_TEMPLATE.format(
                        VIDEO_NAME=self._video_name,
                        EVENT_NUMBER="%04d" % (1 + self._num_events),
                        EXTENSION=self.EXTENSION,
                    )
                )
            )
            size = (frame_bgr.shape[1], frame_bgr.shape[0])
            self._video_writer = _create_video_writer(
                output_path, self._output_dir, self._fourcc, self._frame_rate, size
            )
        self._video_writer.write(frame_bgr)

    def finish_event(self, context: EventContext):
        self._num_events += 1
        # Close the current VideoWriter to output the next event to a new file (unless we're
        # concatenating all events in the same output file).
        if not self._comp_file and self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None

    def close(self):
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None


class FFmpegExtractEncoder(EventEncoder):
    """Extracts events from the source video by re-encoding with ffmpeg (OutputMode.FFMPEG)."""

    STREAMS_FRAMES = False
    SUPPORTS_COMBINED_OUTPUT = False
    SUPPORTS_MULTIPLE_INPUTS = False
    SUPPORTS_OVERLAYS = False
    EXTENSION = "mp4"

    def __init__(
        self,
        input_path: Path,
        output_dir: ty.Optional[Path],
        ffmpeg_input_args: str,
        ffmpeg_output_args: str,
    ):
        self._input_path = input_path
        self._video_name = input_path.stem
        self._output_dir = output_dir
        self._ffmpeg_input_args = ffmpeg_input_args
        self._ffmpeg_output_args = ffmpeg_output_args

    def finish_event(self, context: EventContext):
        output_path = Path(
            OUTPUT_FILE_TEMPLATE.format(
                VIDEO_NAME=self._video_name,
                EVENT_NUMBER="%04d" % context.event_number,
                EXTENSION=self.EXTENSION,
            )
        )
        if self._output_dir:
            output_path = self._output_dir / output_path
        # Only log the args passed to ffmpeg on the first event, to reduce log spam.
        log_args = False
        if context.event_number == 1:
            logger.info("Splitting events using ffmpeg, first event:")
            log_args = True
        _extract_event_ffmpeg(
            input_path=self._input_path,
            output_path=output_path,
            start_time=context.start,
            end_time=context.end,
            ffmpeg_input_args=self._ffmpeg_input_args,
            ffmpeg_out_args=self._ffmpeg_output_args,
            log_args=log_args,
        )


class FFmpegCopyEncoder(FFmpegExtractEncoder):
    """Extracts events from the source video with ffmpeg in codec-copy mode (OutputMode.COPY)."""

    def __init__(
        self,
        input_path: Path,
        output_dir: ty.Optional[Path],
        ffmpeg_input_args: str,
    ):
        super().__init__(
            input_path=input_path,
            output_dir=output_dir,
            ffmpeg_input_args=ffmpeg_input_args,
            ffmpeg_output_args=COPY_MODE_OUTPUT_ARGS,
        )


def get_encoder_type(mode: OutputMode) -> ty.Optional[ty.Type[EventEncoder]]:
    """Get the `EventEncoder` implementation used for `mode`.

    Returns None for modes which do not generate event videos (SCAN_ONLY)."""
    return {
        OutputMode.OPENCV: OpenCVEncoder,
        OutputMode.FFMPEG: FFmpegExtractEncoder,
        OutputMode.COPY: FFmpegCopyEncoder,
    }.get(mode)


class MaskWriter:
    """Writes motion masks to a video file using an OpenCV VideoWriter.

    Not an `EventEncoder`: masks are written for every processed frame, regardless
    of whether it is part of a motion event."""

    def __init__(
        self,
        path: Path,
        fourcc: ty.Any,
        frame_rate: float,
        output_dir: ty.Optional[Path],
    ):
        self._path = path
        self._fourcc = fourcc
        self._frame_rate = frame_rate
        self._output_dir = output_dir
        self._writer: ty.Optional[cv2.VideoWriter] = None
        self._mask_size: ty.Optional[ty.Tuple[int, int]] = None

    def write_frame(self, frame_bgr: np.ndarray, timecode: FrameTimecode):
        size = (frame_bgr.shape[1], frame_bgr.shape[0])
        # Initialize the VideoWriter used for mask output using the first frame's size.
        if self._writer is None:
            self._mask_size = size
            self._writer = _create_video_writer(
                self._path, self._output_dir, self._fourcc, self._frame_rate, size
            )
        if size != self._mask_size:
            logger.warn(
                f"WARNING: Failed to write mask at frame {timecode.frame_num} "
                f"[{timecode.get_timecode()}] due to size mismatch: {size[0]}x{size[1]}, "
                f" expected {self._mask_size[0]}x{self._mask_size[1]}"
            )
            return
        self._writer.write(frame_bgr)

    def close(self):
        if self._writer is not None:
            self._writer.release()
            self._writer = None
