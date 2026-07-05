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
"""DVR-Scan Video Input Tests

Validates the multi-video concatenation logic in `dvr_scan.video_input`."""

import pytest

from dvr_scan.video_input import BackendUnavailable, open_input, probe_source

TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES = 576
TRAFFIC_CAMERA_VIDEO_DURATION = 23.04
CORRUPT_VIDEO_TOTAL_FRAMES = 596

BACKENDS = ["pyav", "opencv"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_decode_single(traffic_camera_video, backend):
    """Decode a single video and validate the reported frame count and position."""
    video = open_input([traffic_camera_video], input_mode=backend)
    assert video.total_frames == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES
    while video.read(decode=False) is not False:
        pass
    assert video.frame_number == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES
    assert video.decode_failures == 0


@pytest.mark.parametrize("backend", BACKENDS)
def test_decode_multiple(traffic_camera_video, backend):
    """Decode multiple videos and validate the reported frame count."""
    splice_amount = 3
    video = open_input([traffic_camera_video] * splice_amount, input_mode=backend)
    assert video.total_frames == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES * splice_amount
    while video.read(decode=False) is not False:
        pass
    assert video.frame_number == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES * splice_amount
    assert video.decode_failures == 0


@pytest.mark.parametrize("backend", BACKENDS)
def test_seam_monotonicity(traffic_camera_video, backend):
    """Position must be strictly increasing across the file seam (regression for #254)."""
    video = open_input([traffic_camera_video] * 2, input_mode=backend)
    last_seconds = -1.0
    max_delta = 0.0
    while video.read(decode=False) is not False:
        seconds = video.position.seconds
        assert seconds > last_seconds, f"position went backwards: {seconds} <= {last_seconds}"
        if last_seconds >= 0:
            max_delta = max(max_delta, seconds - last_seconds)
        last_seconds = seconds
    # The seam should be continuous: no gap larger than a few frame durations.
    assert max_delta < 0.5, f"discontinuity across seam: {max_delta}s"
    assert last_seconds > 2 * TRAFFIC_CAMERA_VIDEO_DURATION - 1.0


@pytest.mark.parametrize("backend", BACKENDS)
def test_seek(traffic_camera_video, backend):
    """Seeking should work on the global timeline, in either direction, across sources."""
    video = open_input([traffic_camera_video] * 2, input_mode=backend)
    # Seek into the second source.
    target = TRAFFIC_CAMERA_VIDEO_DURATION + 5.0
    video.seek(target)
    assert video.read(decode=False) is not False
    assert abs(video.position.seconds - target) < 0.25
    # Seek backwards into the first source.
    video.seek(5.0)
    assert video.read(decode=False) is not False
    assert abs(video.position.seconds - 5.0) < 0.25


def test_corrupt_video_pyav(corrupt_video):
    """The PyAV input path must tolerate corrupt frames and decode the full stream."""
    video = open_input([corrupt_video], input_mode="pyav")
    num_frames = 0
    while video.read(decode=False) is not False:
        num_frames += 1
    assert num_frames == CORRUPT_VIDEO_TOTAL_FRAMES


def test_map_span(traffic_camera_video):
    """An event spanning the seam between two inputs must map to two local spans."""
    video = open_input([traffic_camera_video] * 2)
    duration = TRAFFIC_CAMERA_VIDEO_DURATION
    start = video.base_timecode + (duration - 3.0)
    end = video.base_timecode + (duration + 3.0)
    spans = video.map_span(start, end)
    assert len(spans) == 2
    assert spans[0].source_index == 0 and spans[1].source_index == 1
    assert abs(spans[0].local_start.seconds - (duration - 3.0)) < 0.01
    assert abs(spans[0].local_end.seconds - duration) < 0.01
    assert spans[1].local_start.seconds == 0.0
    assert abs(spans[1].local_end.seconds - 3.0) < 0.01
    # A span entirely within the first source maps to a single span.
    spans = video.map_span(video.base_timecode + 1.0, video.base_timecode + 2.0)
    assert len(spans) == 1 and spans[0].source_index == 0


def test_probe_source(traffic_camera_video):
    """Validate stream metadata extraction."""
    info = probe_source(traffic_camera_video)
    assert info.video.codec_name == "h264"
    assert (info.video.width, info.video.height) == (1280, 720)
    assert info.video.frames == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES
    assert float(info.video.average_rate) == 25.0
    assert abs(float(info.duration) - TRAFFIC_CAMERA_VIDEO_DURATION) < 0.1
    assert len(info.audio) == 1


def test_backend_unavailable(traffic_camera_video):
    with pytest.raises(BackendUnavailable):
        open_input([traffic_camera_video], input_mode="not_a_backend")


@pytest.mark.parametrize("backend", BACKENDS)
def test_delayed_start_normalized(delayed_start_video, backend):
    """Files with a nonzero stream start time must report the first frame at t=0
    regardless of backend (haze.mp4 has a start time of 1.075s)."""
    video = open_input([delayed_start_video], input_mode=backend)
    assert video.read(decode=False) is not False
    assert video.position.seconds < 0.1


def test_seek_backward_then_cross_seam(traffic_camera_video):
    """Crossing the seam a second time after a backward seek must not shift the
    timeline again (offset correction must be idempotent)."""
    video = open_input([traffic_camera_video] * 2)
    # Read across the seam once.
    video.seek(TRAFFIC_CAMERA_VIDEO_DURATION - 0.5)
    while video.position.seconds < TRAFFIC_CAMERA_VIDEO_DURATION + 0.5:
        assert video.read(decode=False) is not False
    first_pass = video.position.seconds
    # Seek backward before the seam and cross it again.
    video.seek(TRAFFIC_CAMERA_VIDEO_DURATION - 0.5)
    last = video.position.seconds
    while video.position.seconds < TRAFFIC_CAMERA_VIDEO_DURATION + 0.5:
        assert video.read(decode=False) is not False
        assert video.position.seconds > last
        last = video.position.seconds
    assert abs(video.position.seconds - first_pass) < 0.25
