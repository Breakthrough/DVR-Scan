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
"""Tests for dvr_scan.encoder (output encoders driven with synthetic frames)."""

import typing as ty
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from scenedetect import FrameTimecode
from scenedetect.common import Timecode

from dvr_scan.encoder import (
    DEFAULT_ENCODE_ARGS,
    EventContext,
    FFmpegCopyEncoder,
    FFmpegExtractEncoder,
    FFmpegPipeEncoder,
    MaskWriter,
    OpenCVEncoder,
    OutputMode,
    build_pipe_command,
    get_encoder_type,
)
from dvr_scan.video_input import AudioStreamInfo, EventSpan, SourceInfo, VideoStreamInfo

FRAME_RATE = 10.0
FRAME_SIZE = (64, 48)  # (width, height)
FOURCC = cv2.VideoWriter_fourcc(*"XVID")


def _make_frame(value: int = 128, size=FRAME_SIZE) -> np.ndarray:
    width, height = size
    return np.full((height, width, 3), value, dtype=np.uint8)


def _tc(seconds: float) -> FrameTimecode:
    return FrameTimecode(seconds, fps=FRAME_RATE)


def _event(number: int, start: float, end: float) -> EventContext:
    return EventContext(event_number=number, start=_tc(start), end=_tc(end))


def _count_frames(path: Path) -> int:
    cap = cv2.VideoCapture(str(path))
    assert cap.isOpened(), f"failed to open {path}"
    num_frames = 0
    while True:
        ret, _ = cap.read()
        if not ret:
            break
        num_frames += 1
    cap.release()
    return num_frames


def test_opencv_encoder_one_file_per_event(tmp_path):
    """Each event must be written to its own output file using the naming template."""
    encoder = OpenCVEncoder(
        fourcc=FOURCC,
        frame_rate=FRAME_RATE,
        video_name="video",
        output_dir=tmp_path,
        comp_file=None,
    )
    for i in range(5):
        encoder.write_frame(_make_frame(), _tc(i / FRAME_RATE))
    encoder.finish_event(_event(1, 0.0, 0.5))
    for i in range(3):
        encoder.write_frame(_make_frame(), _tc(1.0 + i / FRAME_RATE))
    encoder.finish_event(_event(2, 1.0, 1.3))
    encoder.close()
    first, second = tmp_path / "video.DSME_0001.avi", tmp_path / "video.DSME_0002.avi"
    assert first.exists() and second.exists()
    assert _count_frames(first) == 5
    assert _count_frames(second) == 3


def test_opencv_encoder_combined_output(tmp_path):
    """All events must be concatenated into `comp_file` when it is set."""
    encoder = OpenCVEncoder(
        fourcc=FOURCC,
        frame_rate=FRAME_RATE,
        video_name="video",
        output_dir=tmp_path,
        comp_file=Path("combined.avi"),
    )
    for i in range(5):
        encoder.write_frame(_make_frame(), _tc(i / FRAME_RATE))
    encoder.finish_event(_event(1, 0.0, 0.5))
    for i in range(3):
        encoder.write_frame(_make_frame(), _tc(1.0 + i / FRAME_RATE))
    encoder.finish_event(_event(2, 1.0, 1.3))
    encoder.close()
    combined = tmp_path / "combined.avi"
    assert combined.exists()
    assert _count_frames(combined) == 8
    assert not (tmp_path / "video.DSME_0001.avi").exists()


def test_opencv_encoder_lazy_open(tmp_path):
    """No output files may be created until the first frame is written."""
    encoder = OpenCVEncoder(
        fourcc=FOURCC,
        frame_rate=FRAME_RATE,
        video_name="video",
        output_dir=tmp_path,
        comp_file=None,
    )
    encoder.finish_event(_event(1, 0.0, 0.5))
    encoder.close()
    assert not list(tmp_path.iterdir())


def test_mask_writer(tmp_path):
    """Masks are written to a single file; frames with a mismatched size are skipped."""
    writer = MaskWriter(
        path=Path("mask.avi"),
        fourcc=FOURCC,
        frame_rate=FRAME_RATE,
        output_dir=tmp_path,
    )
    for i in range(3):
        writer.write_frame(_make_frame(), _tc(i / FRAME_RATE))
    # Mismatched size compared to the first frame must be skipped, not written.
    writer.write_frame(_make_frame(size=(32, 24)), _tc(0.3))
    writer.close()
    mask_file = tmp_path / "mask.avi"
    assert mask_file.exists()
    assert _count_frames(mask_file) == 3


def test_get_encoder_type():
    assert get_encoder_type(OutputMode.SCAN_ONLY) is None
    assert get_encoder_type(OutputMode.OPENCV) is OpenCVEncoder
    assert get_encoder_type(OutputMode.FFMPEG) is FFmpegExtractEncoder
    assert get_encoder_type(OutputMode.COPY) is FFmpegCopyEncoder
    assert get_encoder_type(OutputMode.ENCODE) is FFmpegPipeEncoder


def test_encoder_capability_flags():
    """set_output relies on these flags for validation; changes here change the CLI/GUI."""
    assert OpenCVEncoder.STREAMS_FRAMES
    assert OpenCVEncoder.SUPPORTS_COMBINED_OUTPUT
    assert OpenCVEncoder.SUPPORTS_MULTIPLE_INPUTS
    assert OpenCVEncoder.SUPPORTS_OVERLAYS
    assert OpenCVEncoder.EXTENSION == "avi"
    for encoder_type in (FFmpegExtractEncoder, FFmpegCopyEncoder):
        assert not encoder_type.STREAMS_FRAMES
        assert not encoder_type.SUPPORTS_COMBINED_OUTPUT
        assert not encoder_type.SUPPORTS_MULTIPLE_INPUTS
        assert not encoder_type.SUPPORTS_OVERLAYS
        assert encoder_type.EXTENSION == "mp4"
    assert FFmpegPipeEncoder.STREAMS_FRAMES
    assert FFmpegPipeEncoder.SUPPORTS_COMBINED_OUTPUT
    assert FFmpegPipeEncoder.SUPPORTS_MULTIPLE_INPUTS
    assert FFmpegPipeEncoder.SUPPORTS_OVERLAYS
    assert FFmpegPipeEncoder.EXTENSION == "mp4"


def test_build_pipe_command_video_only():
    """With no audio inputs there must be no audio maps, concat filter, or -shortest."""
    args = build_pipe_command(
        output_path=Path("out.mp4"),
        frame_size=(640, 480),
        frame_rate=25.0,
        encode_args=DEFAULT_ENCODE_ARGS,
    )
    assert args[:5] == ["ffmpeg", "-y", "-nostdin", "-v", "error"]
    assert args[args.index("-video_size") + 1] == "640x480"
    assert args[args.index("-framerate") + 1] == "25.0"
    assert args[args.index("-i") + 1] == "pipe:0"
    assert args[args.index("-map") + 1] == "0:v:0"
    assert args.count("-map") == 1
    assert "-shortest" not in args
    assert "-filter_complex" not in args
    assert args[args.index("-c:v") + 1] == "libx264"
    assert args[-1] == "out.mp4"


def test_build_pipe_command_single_audio_source():
    """A single audio source must be seeked with -ss and padded with silence (apad) so
    -shortest trims the output to the video's duration, not the audio's."""
    args = build_pipe_command(
        output_path=Path("out.mp4"),
        frame_size=(64, 48),
        frame_rate=10.0,
        encode_args=DEFAULT_ENCODE_ARGS,
        audio_inputs=[(Path("source.mp4"), "1.500000")],
    )
    seek = args.index("-ss")
    assert args[seek : seek + 4] == ["-ss", "1.500000", "-i", "source.mp4"]
    assert args[args.index("-filter_complex") + 1] == "[1:a:0]apad[outa]"
    assert "[outa]" in args and args[args.index("[outa]") - 1] == "-map"
    assert "-shortest" in args


def test_build_pipe_command_multiple_audio_sources():
    """Audio spanning multiple sources must be joined with the concat filter."""
    args = build_pipe_command(
        output_path=Path("out.mp4"),
        frame_size=(64, 48),
        frame_rate=10.0,
        encode_args=DEFAULT_ENCODE_ARGS,
        audio_inputs=[(Path("a.mp4"), "2.000000"), (Path("b.mp4"), "0.000000")],
    )
    assert args[args.index("-filter_complex") + 1] == "[1:a:0][2:a:0]concat=n=2:v=0:a=1,apad[outa]"
    assert "[outa]" in args and args[args.index("[outa]") - 1] == "-map"
    assert "-shortest" in args
    # Both sources are inputs with their own seek positions.
    assert args.count("-ss") == 2 and args.count("-i") == 3


def _make_source_info(
    path: Path, audio_duration_seconds: ty.Optional[float], time_base=Fraction(1, 48000)
) -> SourceInfo:
    """Create a synthetic SourceInfo with a 10 second video stream and optional audio."""
    video = VideoStreamInfo(
        index=0,
        codec_name="h264",
        profile=None,
        pix_fmt="yuv420p",
        width=64,
        height=48,
        sample_aspect_ratio=None,
        time_base=Fraction(1, 12800),
        start_time=0,
        duration=128000,
        average_rate=Fraction(10),
        frames=100,
        bit_rate=None,
    )
    audio = ()
    if audio_duration_seconds is not None:
        audio = (
            AudioStreamInfo(
                index=1,
                codec_name="aac",
                sample_rate=48000,
                channels=1,
                layout="mono",
                time_base=time_base,
                start_time=0,
                duration=round(audio_duration_seconds / time_base),
                bit_rate=None,
            ),
        )
    return SourceInfo(
        path=path,
        container_format="mp4",
        video=video,
        audio=audio,
        has_subtitles=False,
        duration=Fraction(10),
    )


def _pipe_encoder_with_sources(sources: ty.List[SourceInfo]) -> FFmpegPipeEncoder:
    stub = SimpleNamespace(sources=sources, paths=[source.path for source in sources])
    return FFmpegPipeEncoder(video_input=stub, frame_rate=10.0, output_dir=None, comp_file=None)


def _span(source_index: int, path: Path, start_seconds: float) -> EventSpan:
    timecode = FrameTimecode(
        timecode=Timecode(pts=round(start_seconds * 1e6), time_base=Fraction(1, 1000000)),
        fps=10.0,
    )
    return EventSpan(source_index=source_index, path=path, local_start=timecode, local_end=timecode)


def test_audio_inputs_skipped_when_audio_ends_before_event():
    """If the source's audio stream ends before the event starts, seeking it would make
    -shortest produce an empty output; the encoder must fall back to video-only."""
    source = _make_source_info(Path("a.mp4"), audio_duration_seconds=4.0)
    encoder = _pipe_encoder_with_sources([source])
    assert encoder._audio_inputs(_span(0, source.path, 7.0)) == []
    assert encoder._audio_inputs(_span(0, source.path, 3.0)) == [(Path("a.mp4"), "3.000000")]


def test_audio_inputs_stop_at_source_without_audio():
    """Sources after the first without an audio stream cannot be concatenated."""
    with_audio = _make_source_info(Path("a.mp4"), audio_duration_seconds=10.0)
    without_audio = _make_source_info(Path("b.mp4"), audio_duration_seconds=None)
    encoder = _pipe_encoder_with_sources([with_audio, without_audio, with_audio])
    assert encoder._audio_inputs(_span(0, with_audio.path, 2.0)) == [(Path("a.mp4"), "2.000000")]
    assert encoder._audio_inputs(_span(1, without_audio.path, 1.0)) == []


def test_output_mode_reexported_from_scanner():
    """Existing consumers import OutputMode from dvr_scan.scanner (compat re-export)."""
    from dvr_scan.scanner import OutputMode as ScannerOutputMode

    assert ScannerOutputMode is OutputMode


def test_set_output_encode_validation(traffic_camera_video, monkeypatch):
    """ENCODE mode must accept multiple inputs and combined output, but still
    requires ffmpeg to be present."""
    import dvr_scan.scanner as scanner_module

    scanner = scanner_module.MotionScanner([Path(traffic_camera_video)] * 2)
    monkeypatch.setattr(scanner_module, "is_ffmpeg_available", lambda: True)
    scanner.set_output(output_mode="encode", comp_file=Path("events.mp4"))
    with pytest.raises(ValueError):
        scanner.set_output(output_mode="ffmpeg")
    monkeypatch.setattr(scanner_module, "is_ffmpeg_available", lambda: False)
    with pytest.raises(ValueError):
        scanner.set_output(output_mode="encode")
