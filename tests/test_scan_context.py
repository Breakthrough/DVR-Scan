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
"""DVR-Scan MotionScanner Tests

Validates functionality of the motion scanning context using various parameters.
"""

import platform
import typing as ty

import pytest

from dvr_scan.region import Point
from dvr_scan.scanner import DetectorType, MotionScanner
from dvr_scan.subtractor import SubtractorCNT, SubtractorCudaMOG2

MACHINE_ARCH = platform.machine().upper()

# On some ARM chips (e.g. Apple M1), results are slightly different, so we allow a 1 frame
# delta on the events for those platforms.
EVENT_FRAME_TOLERANCE = 1 if ("ARM" in MACHINE_ARCH or "AARCH" in MACHINE_ARCH) else 0

# Similar to ARM, the CUDA version gives slightly different results.
CUDA_EVENT_TOLERANCE = 1

# ROI within the frame used for the test case (see traffic_camera.txt for details).
TRAFFIC_CAMERA_ROI = [
    Point(631, 532),
    Point(841, 532),
    Point(841, 659),
    Point(631, 659),
]

TRAFFIC_CAMERA_EVENTS = [
    (9, 149),
    (358, 491),
    (542, 576),
]

TRAFFIC_CAMERA_EVENTS_TIME_PRE_5 = [
    (3, 149),
    (352, 491),
    (536, 576),
]

# Middle event as detected when scanning starts from a mid-video seek. The event start
# differs slightly from TRAFFIC_CAMERA_EVENTS since the background model is initialized
# from a different frame.
TRAFFIC_CAMERA_EVENTS_AFTER_SEEK = [
    (360, 491),
]

# Warming up the background model from a mid-video seek amplifies the ARM/x86 detection
# difference: the macos-14 runner detects the event start 2 frames earlier than x86.
AFTER_SEEK_FRAME_TOLERANCE = 2 if EVENT_FRAME_TOLERANCE else 0

# Last event still ends on end of video even though we specified to include 40 frames extra.
TRAFFIC_CAMERA_EVENTS_TIME_POST_40 = [
    (9, 139),
    (358, 481),
    (542, 576),
]

TRAFFIC_CAMERA_EVENTS_CNT = [
    (15, 149),
    (364, 491),
    (543, 576),
]

# Small ROI for faster test execution.
CORRUPT_VIDEO_ROI = [
    Point(0, 0),
    Point(32, 0),
    Point(32, 32),
    Point(0, 32),
]
CORRUPT_VIDEO_EVENTS = [
    (152, 366),
]


def compare_event_lists(
    a: ty.List[ty.Tuple[int, int]], b: ty.List[ty.Tuple[int, int]], tolerance: int = 0
):
    if tolerance == 0:
        assert a == b
        return
    for i, (start, end) in enumerate(a):
        start_matches = abs(start - b[i][0]) <= tolerance
        end_matches = abs(end - b[i][1]) <= tolerance
        assert start_matches and end_matches, (
            f"Event mismatch at index {i} with tolerance {tolerance}.\n"
            f"Actual = {a[i]}, Expected = {b[i]}"
        )


@pytest.mark.parametrize("input_mode", ["pyav", "opencv"])
def test_scan_context(traffic_camera_video, input_mode):
    """Test functionality of MotionScanner with default parameters (DetectorType.MOG2)."""
    scanner = MotionScanner([traffic_camera_video], input_mode=input_mode)
    scanner.set_detection_params()
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS, EVENT_FRAME_TOLERANCE)


def test_scan_context_pts_backed_events(traffic_camera_video):
    """Ensure emitted motion events carry exact PTS-backed timing information."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_detection_params()
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    event_list = scanner.scan().event_list
    assert event_list
    for event in event_list:
        assert event.start.pts is not None and event.start.time_base is not None
        assert event.end.pts is not None and event.end.time_base is not None
        assert event.end.seconds > event.start.seconds


# Expected wall-clock event start times for the VFR fixture, mapped from the CFR ground
# truth through the fixture's piecewise timing (see the vfr_video docstring in conftest).
# The tolerance covers detection window shifts, which are quantized by the average
# framerate; average-framerate timing would be off by over 4 seconds for the events in
# the slowed section.
VFR_EXPECTED_START_SECONDS = [0.4, 17.2, 31.9]
VFR_START_TOLERANCE = 0.6
# Total duration of the VFR fixture: 288 frames at 25 fps + 288 frames at 12.5 fps.
VFR_DURATION = 34.56


def check_vfr_event_starts(event_list, expected_starts_seconds):
    for event, expected_start in zip(event_list, expected_starts_seconds, strict=True):
        assert abs(event.start.seconds - expected_start) < VFR_START_TOLERANCE, (
            f"expected event start near {expected_start}s, got {event.start.seconds}s"
        )
        assert event.end.seconds > event.start.seconds


def test_scan_context_vfr(vfr_video):
    """Ensure event boundaries are correct in wall-clock time on variable framerate input.

    The fixture plays the first 288 frames of traffic_camera.mp4 at 25 fps and the rest at
    12.5 fps, so motion that occurs at source frame N >= 288 has a true presentation time of
    11.52s + (N - 288) / 12.5. Timing derived from the container's average framerate (the
    pre-v2.0 behavior) would misplace events in the slowed section by several seconds."""
    scanner = MotionScanner([vfr_video])
    scanner.set_detection_params()
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    event_list = scanner.scan().event_list
    assert len(event_list) == len(VFR_EXPECTED_START_SECONDS)
    check_vfr_event_starts(event_list, VFR_EXPECTED_START_SECONDS)


def test_scan_context_vfr_concat(vfr_video):
    """Two concatenated VFR inputs must yield the same events in each copy, with the
    second copy offset by the first file's true duration, on a monotonic timeline."""
    scanner = MotionScanner([vfr_video, vfr_video])
    scanner.set_detection_params()
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    event_list = scanner.scan().event_list
    expected_starts = VFR_EXPECTED_START_SECONDS + [
        start + VFR_DURATION for start in VFR_EXPECTED_START_SECONDS
    ]
    assert len(event_list) == len(expected_starts)
    check_vfr_event_starts(event_list, expected_starts)
    for previous, current in zip(event_list[:-1], event_list[1:], strict=True):
        assert current.start.seconds >= previous.end.seconds


@pytest.mark.parametrize("frame_skip", [1, 2])
def test_scan_context_vfr_frame_skip(vfr_video, frame_skip):
    """Frame skipping on VFR input must not shift event boundaries in wall-clock time
    (boundaries derive from each processed frame's exact PTS, not a frame counter)."""
    scanner = MotionScanner([vfr_video], frame_skip=frame_skip)
    scanner.set_detection_params()
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    event_list = scanner.scan().event_list
    assert len(event_list) == len(VFR_EXPECTED_START_SECONDS)
    check_vfr_event_starts(event_list, VFR_EXPECTED_START_SECONDS)


def test_scan_context_with_video_joiner(traffic_camera_video):
    """Ensure that concatenated inputs scan without errors (regression for #254)."""
    scanner = MotionScanner([traffic_camera_video, traffic_camera_video])
    scanner.set_detection_params()
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    scanner.scan()


@pytest.mark.skipif(not SubtractorCudaMOG2.is_available(), reason="CUDA module not available.")
def test_scan_context_cuda(traffic_camera_video):
    """Test functionality of MotionScanner with the DetectorType.MOG2_CUDA."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_detection_params(detector_type=DetectorType.MOG2_CUDA)
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    event_list = scanner.scan().event_list
    assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS)
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS, CUDA_EVENT_TOLERANCE)


@pytest.mark.skipif(not SubtractorCNT.is_available(), reason="CNT algorithm not available.")
def test_scan_context_cnt(traffic_camera_video):
    """Test basic functionality of MotionScanner using the CNT algorithm."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_detection_params(detector_type=DetectorType.CNT)
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=3, time_pre_event=0)
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS_CNT, EVENT_FRAME_TOLERANCE)


def test_pre_event_shift(traffic_camera_video):
    """Test setting time_pre_event."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=6)
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS_TIME_PRE_5, EVENT_FRAME_TOLERANCE)


def test_pre_event_shift_with_frame_skip(traffic_camera_video):
    """Test setting time_pre_event when using frame_skip."""

    def scan_events(frame_skip: int):
        scanner = MotionScanner([traffic_camera_video], frame_skip=frame_skip)
        scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
        scanner.set_event_params(min_event_len=4, time_pre_event=6)
        event_list = scanner.scan().event_list
        return [(event.start.frame_num, event.end.frame_num) for event in event_list]

    # Compare against a baseline scan without frame skipping so the only variable is the
    # skip amount (detection itself can shift by a frame or two between decoders).
    baseline = scan_events(frame_skip=0)
    for frame_skip in range(1, 6):
        event_list = scan_events(frame_skip)
        # The start times should not differ from the baseline (non-frame-skipped) by more
        # than the amount of frames we are skipping, plus one frame of slack since the
        # detection window length is quantized by the skip interval. End times can vary
        # more since the default value of time_post_event is relatively large.
        assert all(
            [
                abs(x[0] - y[0]) <= (frame_skip + 1)
                for x, y in zip(event_list, baseline, strict=True)
            ]
        ), "Comparison failure when frame_skip = %d" % (frame_skip)


def test_post_event_shift(traffic_camera_video):
    """Test setting time_post_event."""

    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0, time_post_event=40)

    event_list = scanner.scan().event_list
    assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS_TIME_POST_40)
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS_TIME_POST_40, EVENT_FRAME_TOLERANCE)


def test_post_event_shift_with_frame_skip(traffic_camera_video):
    """Test setting time_post_event."""
    for frame_skip in range(1, 6):
        scanner = MotionScanner([traffic_camera_video], frame_skip=frame_skip)
        scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
        scanner.set_event_params(min_event_len=4, time_post_event=40)
        event_list = scanner.scan().event_list
        assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS_TIME_POST_40)
        event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
        # The calculated end times should not differ by more than frame_skip from the ground truth.
        assert all(
            [
                abs(x[1] - y[1]) <= frame_skip
                for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_POST_40, strict=True)
            ]
        ), "Comparison failure when frame_skip = %d" % (frame_skip)
        # The calculated end times must always be >= the ground truth's frame number, otherwise
        # we may be discarding frames containing motion due to skipping them.
        assert all(
            [
                x[1] >= y[1]
                for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_POST_40, strict=True)
            ]
        ), "Comparison failure when frame_skip = %d" % (frame_skip)


@pytest.mark.parametrize("input_mode", ["pyav", "opencv"])
def test_decode_corrupt_video(corrupt_video, input_mode):
    """Ensure we can process a video with a single bad frame."""
    scanner = MotionScanner([corrupt_video], input_mode=input_mode)
    scanner.set_event_params(min_event_len=2)
    scanner.set_regions(regions=[CORRUPT_VIDEO_ROI])
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, CORRUPT_VIDEO_EVENTS, EVENT_FRAME_TOLERANCE)


def test_start_end_time(traffic_camera_video):
    """Test basic functionality of MotionScanner with start and stop times defined."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    scanner.set_video_time(start_time=200, end_time=500)
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    # The set duration should only cover the middle event.
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS_AFTER_SEEK, AFTER_SEEK_FRAME_TOLERANCE)


def test_start_duration(traffic_camera_video):
    """Test basic functionality of MotionScanner with start and duration defined."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    scanner.set_video_time(start_time=200, duration=300)
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    # The set duration should only cover the middle event.
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS_AFTER_SEEK, AFTER_SEEK_FRAME_TOLERANCE)
