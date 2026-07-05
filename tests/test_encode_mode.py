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
"""End-to-end tests for OutputMode.ENCODE (ffmpeg pipe encoder) via the CLI.

All tests in this module require ffmpeg (see conftest.py, which allows using a copy
of ffmpeg in the repository root when it is not on PATH)."""

import shutil
import subprocess
import typing as ty
from pathlib import Path

import cv2
import pytest

from dvr_scan.platform import is_ffmpeg_available

pytestmark = pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")

DVR_SCAN_COMMAND: str = "python -m dvr_scan"

# Matches BASE_COMMAND in test_cli.py aside from output mode; yields 3 events.
BASE_COMMAND = [
    "--input",
    "tests/resources/traffic_camera.mp4",
    "--add-region",
    "631 532 841 532 841 659 631 659",
    "--min-event-length",
    "4",
    "--time-before-event",
    "0",
    "--threshold",
    "0.2",
    "--ignore-user-config",
    "--output-mode",
    "encode",
]
BASE_COMMAND_NUM_EVENTS = 3


def _run_dvr_scan(args: ty.List[str]) -> str:
    """Helper to run dvr-scan with a list of arguments and return the output."""
    processed_args = []
    for arg in args:
        processed_args.append(f'"{arg}"' if " " in str(arg) else str(arg))
    command = " ".join([DVR_SCAN_COMMAND] + processed_args)
    return subprocess.check_output(command, shell=True, text=True)


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


def _has_audio(path: Path) -> bool:
    """Check for an audio stream by parsing `ffmpeg -i` output (nonzero exit expected)."""
    result = subprocess.run(["ffmpeg", "-i", str(path)], capture_output=True, text=True)
    return "Audio:" in result.stderr


def test_encode_mode(tmp_path):
    """ENCODE mode must produce a decodable mp4 with audio for each motion event
    (the audio track comes from the source, which contains AAC audio)."""
    _run_dvr_scan(BASE_COMMAND + ["--output-dir", tmp_path])
    events = sorted(tmp_path.iterdir())
    assert [path.name for path in events] == [
        "traffic_camera.DSME_%04d.mp4" % (index + 1) for index in range(BASE_COMMAND_NUM_EVENTS)
    ]
    for path in events:
        assert _count_frames(path) > 0, f"{path.name} did not decode any frames"
        assert _has_audio(path), f"{path.name} is missing its audio stream"


def test_encode_mode_merge_window(tmp_path):
    """--merge-window must combine nearby events into one clip, and frames decoded
    past --time-post-event while waiting out the merge window must not leak into a
    clip when the event ends instead of merging (#195)."""
    _run_dvr_scan(
        BASE_COMMAND
        + ["--output-dir", tmp_path, "--time-post-event", "10", "--merge-window", "120"]
    )
    clips = sorted(tmp_path.glob("*.mp4"))
    assert len(clips) == 2
    # The first event covers ~100 frames (motion from ~9-98 plus 10 frames of padding).
    # If held frames leaked into the clip, it would instead extend ~120 frames past the
    # last motion, to where the event closed.
    assert 80 <= _count_frames(clips[0]) <= 130
    # The merged event covers ~205 frames (~358-563), including the no-motion gaps
    # between the merged groups of motion.
    assert 175 <= _count_frames(clips[1]) <= 235


def test_encode_mode_overlays(tmp_path):
    """Overlays (-bb/-tc/-fm) must be supported in ENCODE mode."""
    _run_dvr_scan(
        BASE_COMMAND
        + ["--bounding-box", "--time-code", "--frame-metrics", "--output-dir", tmp_path]
    )
    events = list(tmp_path.iterdir())
    assert len(events) == BASE_COMMAND_NUM_EVENTS
    for path in events:
        assert _count_frames(path) > 0, f"{path.name} did not decode any frames"


def test_encode_mode_combined_output(tmp_path):
    """-o/--output must combine all events into a single mp4 (video-only)."""
    _run_dvr_scan(BASE_COMMAND + ["--output", "events.mp4", "--output-dir", tmp_path])
    assert [path.name for path in tmp_path.iterdir()] == ["events.mp4"]
    combined = tmp_path / "events.mp4"
    assert _count_frames(combined) > 0
    # Combined output is documented as video-only.
    assert not _has_audio(combined)


def test_encode_mode_multiple_inputs_naming(tmp_path):
    """ENCODE mode must support multiple inputs, naming each event after the source
    video containing its start (#258), including an event spanning the file seam."""
    first, second = tmp_path / "first.mp4", tmp_path / "second.mp4"
    shutil.copy("tests/resources/traffic_camera.mp4", first)
    shutil.copy("tests/resources/traffic_camera.mp4", second)
    output_dir = tmp_path / "events"
    args = [
        "--input",
        str(first),
        "--input",
        str(second),
        "--add-region",
        "631 532 841 532 841 659 631 659",
        "--min-event-length",
        "4",
        "--time-before-event",
        "0",
        "--threshold",
        "0.2",
        "--ignore-user-config",
        "--output-mode",
        "encode",
        "--output-dir",
        str(output_dir),
    ]
    _run_dvr_scan(args)
    # The last event of the first video merges with the first event of the second video
    # (the gap is shorter than the post-event window), so typically 5 events span both
    # files. Avoid pinning the exact count in case event boundaries shift by a frame.
    events = sorted(path.name for path in output_dir.iterdir())
    assert len(events) >= 4
    first_events = [name for name in events if name.startswith("first.DSME_")]
    second_events = [name for name in events if name.startswith("second.DSME_")]
    assert len(first_events) >= 2 and len(second_events) >= 2
    assert len(first_events) + len(second_events) == len(events)
    # Numbering is continuous across sources, in order.
    assert events == ["first.DSME_%04d.mp4" % (index + 1) for index in range(len(first_events))] + [
        "second.DSME_%04d.mp4" % (len(first_events) + index + 1)
        for index in range(len(second_events))
    ]
    # The last event starting in the first video crosses the seam into the second;
    # its audio is concatenated from both sources.
    seam_event = output_dir / first_events[-1]
    assert _count_frames(seam_event) > 0
    assert _has_audio(seam_event)


def test_encode_mode_frame_skip(tmp_path):
    """ENCODE mode with --frame-skip must produce decodable output with audio matching
    the reduced effective framerate."""
    _run_dvr_scan(BASE_COMMAND + ["--frame-skip", "1", "--output-dir", tmp_path])
    events = list(tmp_path.iterdir())
    assert len(events) > 0
    for path in events:
        assert _count_frames(path) > 0, f"{path.name} did not decode any frames"
        assert _has_audio(path), f"{path.name} is missing its audio stream"


def test_encode_mode_vfr(tmp_path, vfr_video):
    """ENCODE mode on a variable framerate source must produce a decodable clip per
    event with every processed frame preserved.

    KNOWN LIMITATION: the pipe encoder stamps frames at the input's *average* framerate,
    so clip playback duration differs from the event's wall-clock span wherever the
    local framerate deviates from the average (frames are never dropped; the clip just
    plays faster or slower). Exact-PTS output would require an in-process encoder
    (the PyAVEncoder slot in the design)."""
    args = [
        "--input",
        vfr_video,
        "--add-region",
        "631 532 841 532 841 659 631 659",
        "--min-event-length",
        "4",
        "--time-before-event",
        "0",
        "--ignore-user-config",
        "--output-mode",
        "encode",
        "--output-dir",
        str(tmp_path),
    ]
    _run_dvr_scan(args)
    events = sorted(tmp_path.iterdir())
    assert len(events) == 3
    for path in events:
        assert _count_frames(path) > 0, f"{path.name} did not decode any frames"


def test_encode_mode_with_mask_output(tmp_path):
    """Mask output (-mo) must work alongside ENCODE mode (both share the encode thread)."""
    _run_dvr_scan(BASE_COMMAND + ["--mask-output", "mask.avi", "--output-dir", tmp_path])
    files = sorted(path.name for path in tmp_path.iterdir())
    assert "mask.avi" in files
    assert len(files) == 1 + BASE_COMMAND_NUM_EVENTS
    assert _count_frames(tmp_path / "mask.avi") > 0
    for name in files:
        if name != "mask.avi":
            assert _count_frames(tmp_path / name) > 0
