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

from pathlib import Path

import cv2
import numpy as np
from scenedetect import FrameTimecode

from dvr_scan.encoder import (
    EventContext,
    FFmpegCopyEncoder,
    FFmpegExtractEncoder,
    MaskWriter,
    OpenCVEncoder,
    OutputMode,
    get_encoder_type,
)

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


def test_output_mode_reexported_from_scanner():
    """Existing consumers import OutputMode from dvr_scan.scanner (compat re-export)."""
    from dvr_scan.scanner import OutputMode as ScannerOutputMode

    assert ScannerOutputMode is OutputMode
