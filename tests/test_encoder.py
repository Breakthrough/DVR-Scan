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
    _video_encode_args,
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


def test_mask_writer_ffmpeg(tmp_path):
    """Non-AVI mask output pipes frames through ffmpeg using encode_args (#275)."""
    from dvr_scan.platform import is_ffmpeg_available

    if not is_ffmpeg_available():
        pytest.skip("ffmpeg not available")
    writer = MaskWriter(
        path=Path("mask.mp4"),
        fourcc=FOURCC,
        frame_rate=FRAME_RATE,
        output_dir=tmp_path,
    )
    for i in range(3):
        writer.write_frame(_make_frame(), _tc(i / FRAME_RATE))
    writer.write_frame(_make_frame(size=(32, 24)), _tc(0.3))
    writer.close()
    mask_file = tmp_path / "mask.mp4"
    assert mask_file.exists()
    assert _count_frames(mask_file) == 3


def _probe_video(path: Path) -> ty.Tuple[str, int, int]:
    """(pix_fmt, width, height) of the first video stream of `path`."""
    import av

    with av.open(str(path)) as container:
        codec = container.streams.video[0].codec_context
        return (codec.pix_fmt, codec.width, codec.height)


def _require_ffmpeg():
    from dvr_scan.platform import is_ffmpeg_available

    if not is_ffmpeg_available():
        pytest.skip("ffmpeg not available")


def test_mask_writer_ffmpeg_odd_size(tmp_path):
    """Mask frames with odd dimensions (e.g. from -df 3) must encode as 4:2:0 MP4, padded
    to even dimensions."""
    _require_ffmpeg()
    writer = MaskWriter(
        path=Path("mask.mp4"),
        fourcc=FOURCC,
        frame_rate=FRAME_RATE,
        output_dir=tmp_path,
    )
    for i in range(3):
        writer.write_frame(_make_frame(size=(63, 47)), _tc(i / FRAME_RATE))
    writer.close()
    assert _probe_video(tmp_path / "mask.mp4") == ("yuv420p", 64, 48)


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


def test_build_pipe_command_pix_fmt():
    """Output defaults to 4:2:0 (players often can't decode the 4:4:4 that ffmpeg picks
    for the bgr24 pipe), but a user-specified pixel format must be kept."""
    args = build_pipe_command(Path("out.mp4"), (640, 480), 25.0, DEFAULT_ENCODE_ARGS)
    assert args[args.index("-pix_fmt", args.index("pipe:0")) + 1] == "yuv420p"
    # Even frame size and no user filters: no pad filter needed.
    assert "-vf" not in args
    args = build_pipe_command(Path("out.mp4"), (640, 480), 25.0, "-c:v libx264 -pix_fmt yuv444p")
    output_args = args[args.index("pipe:0") :]
    assert output_args.count("-pix_fmt") == 1
    assert output_args[output_args.index("-pix_fmt") + 1] == "yuv444p"


def test_build_pipe_command_odd_size_padded():
    """Odd frame sizes (e.g. -df 3 or region crops) must be padded to even dimensions,
    appending to any user-specified video filter (which may itself change the size)."""
    args = build_pipe_command(Path("out.mp4"), (427, 241), 25.0, DEFAULT_ENCODE_ARGS)
    assert args[args.index("-vf") + 1] == "pad=ceil(iw/2)*2:ceil(ih/2)*2"
    args = build_pipe_command(Path("out.mp4"), (640, 480), 25.0, "-c:v libx264 -vf hflip")
    assert args.count("-vf") == 1
    assert args[args.index("-vf") + 1] == "hflip,pad=ceil(iw/2)*2:ceil(ih/2)*2"


def test_pipe_encoder_yuv420p_odd_size(tmp_path):
    """ENCODE output must be yuv420p, and odd-sized frames must still encode."""
    _require_ffmpeg()
    encoder = FFmpegPipeEncoder(
        video_input=SimpleNamespace(sources=[], paths=[Path("odd.mp4")]),
        frame_rate=FRAME_RATE,
        output_dir=tmp_path,
        comp_file=Path("events.mp4"),
    )
    for i in range(5):
        encoder.write_frame(_make_frame(size=(65, 49)), _tc(i / FRAME_RATE))
    encoder.finish_event(_event(1, 0.0, 0.5))
    encoder.close()
    assert _probe_video(tmp_path / "events.mp4") == ("yuv420p", 66, 50)
    assert _count_frames(tmp_path / "events.mp4") == 5


def _beep_onset(path: Path) -> float:
    """Time in seconds (from the start of the output) where the first audio stream of
    `path` first becomes loud."""
    import av

    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        sample_rate = stream.sample_rate
        frames = list(container.decode(stream))
        start = float(frames[0].pts * frames[0].time_base)
        samples = np.concatenate([np.abs(frame.to_ndarray()).max(axis=0) for frame in frames])
    loud = np.nonzero(samples > 0.5 * samples.max())[0]
    return start + loud[0] / sample_rate


def test_video_encode_args_filter_complex_skips_pad():
    """A filter graph cannot be combined with -vf, so no pad filter is added for it."""
    args = _video_encode_args("-c:v libx264 -filter_complex [0:v]hflip[v] -map [v]", (321, 241))
    assert "-vf" not in args
    assert args[:2] == ["-pix_fmt", "yuv420p"]


def test_pipe_encoder_audio_container_start_offset(tmp_path):
    """Audio must stay aligned for inputs with a nonzero container start time (e.g. DVR
    .ts files). ffmpeg already offsets input seeks by the container start time, so it
    must not be added again (it was, shifting audio by +2s here).

    audio_start_offset.mp4: 4s of 64x48 video at 10 fps with a 1 kHz tone from 1.5s to
    2.0s (otherwise silent), remuxed with -output_ts_offset 2 so the video starts at 2.0s
    and the AAC audio (with its priming samples) at 1.936s. Generated with:

        ffmpeg -f lavfi -i testsrc2=s=64x48:r=10:d=4 -f lavfi -i sine=f=1000:sample_rate=16000:d=4
            -filter:a "volume='between(t,1.5,2.0)':eval=frame" -c:v libx264 -pix_fmt yuv420p
            -g 10 -crf 30 -c:a aac -b:a 32k -ac 1 base.mp4
        ffmpeg -i base.mp4 -c copy -output_ts_offset 2 audio_start_offset.mp4
    """
    _require_ffmpeg()
    from dvr_scan.video_input import open_input

    video = open_input([Path(__file__).parent / "resources" / "audio_start_offset.mp4"])
    assert video.sources[0].start_time is not None
    assert abs(float(video.sources[0].start_time) - 1.936) < 0.01
    encoder = FFmpegPipeEncoder(
        video_input=video, frame_rate=10.0, output_dir=tmp_path, comp_file=None
    )
    # Event covering 1.0s - 2.5s of the input: the tone should start 0.5s into the clip.
    event_start = 1.0
    for i in range(15):
        encoder.write_frame(_make_frame(size=(64, 48)), _tc(event_start + i / 10.0))
    encoder.finish_event(_event(1, event_start, event_start + 1.5))
    encoder.close()
    output = tmp_path / "audio_start_offset.DSME_0001.mp4"
    assert abs(_beep_onset(output) - 0.5) < 0.05


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


def _patch_ffmpeg_available(monkeypatch, available: bool):
    """Patch the ffmpeg check in every module that imported it by name. init_scanner()
    decides the fallback in dvr_scan.shared, but MotionScanner.set_output() and the
    encoders re-check through their own imports, so patching only one module makes the
    outcome depend on whether the machine running the tests has ffmpeg on PATH."""
    import dvr_scan.encoder as encoder_module
    import dvr_scan.scanner as scanner_module
    import dvr_scan.shared as shared

    for module in (shared, scanner_module, encoder_module):
        monkeypatch.setattr(module, "is_ffmpeg_available", lambda: available)


def test_init_scanner_default_output_mode(traffic_camera_video, monkeypatch):
    """The default output mode is ENCODE when ffmpeg is available, falling back to
    OPENCV with a warning when it is not (explicitly-set modes still raise instead)."""
    import argparse

    import dvr_scan.shared as shared
    from dvr_scan.config import ConfigRegistry
    from dvr_scan.shared.settings import ScanSettings

    def make_settings() -> ScanSettings:
        return ScanSettings(
            args=argparse.Namespace(input=[Path(traffic_camera_video)]),
            config=ConfigRegistry(),
        )

    _patch_ffmpeg_available(monkeypatch, True)
    assert shared.init_scanner(make_settings()).output_mode == OutputMode.ENCODE

    _patch_ffmpeg_available(monkeypatch, False)
    assert shared.init_scanner(make_settings()).output_mode == OutputMode.OPENCV


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


def test_init_scanner_mask_output_extension(traffic_camera_video, monkeypatch):
    """Extensionless --mask-output defaults to .mp4 when ffmpeg is available and .avi otherwise."""
    import argparse

    import dvr_scan.shared as shared
    from dvr_scan.config import ConfigRegistry
    from dvr_scan.shared.settings import ScanSettings

    def make_settings() -> ScanSettings:
        return ScanSettings(
            args=argparse.Namespace(input=[Path(traffic_camera_video)], mask_output="mask"),
            config=ConfigRegistry(),
        )

    _patch_ffmpeg_available(monkeypatch, True)
    assert shared.init_scanner(make_settings())._mask_file == Path("mask.mp4")

    _patch_ffmpeg_available(monkeypatch, False)
    assert shared.init_scanner(make_settings())._mask_file == Path("mask.avi")


def test_create_video_writer_logs_error_when_not_opened(
    tmp_path: Path, monkeypatch, caplog: pytest.LogCaptureFixture
):
    """If cv2.VideoWriter fails to open, an actionable ERROR should be logged (#214)."""
    import logging

    import dvr_scan.encoder as encoder_module
    from dvr_scan.encoder import _create_video_writer

    class DummyClosedWriter:
        def isOpened(self) -> bool:
            return False

    monkeypatch.setattr(
        encoder_module.cv2, "VideoWriter", lambda *args, **kwargs: DummyClosedWriter()
    )
    caplog.set_level(logging.ERROR)
    _create_video_writer(Path("bad.avi"), tmp_path, 0, 30.0, (320, 240))
    assert "Failed to open VideoWriter" in caplog.text
