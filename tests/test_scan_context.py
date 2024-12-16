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

PTS_EVENT_TOLERANCE = 1

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


def test_scan_context(traffic_camera_video):
    """Test functionality of MotionScanner with default parameters (DetectorType.MOG2)."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_detection_params()
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS, EVENT_FRAME_TOLERANCE)


def test_scan_context_use_pts(traffic_camera_video):
    """Test scanner 'use_pts' option to change how timekeeping is done."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_detection_params()
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0, use_pts=True)
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS, PTS_EVENT_TOLERANCE)


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
    for frame_skip in range(1, 6):
        scanner = MotionScanner([traffic_camera_video], frame_skip=frame_skip)
        scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
        scanner.set_event_params(min_event_len=4, time_pre_event=6)
        event_list = scanner.scan().event_list
        event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
        # The start times should not differ from the ground truth (non-frame-skipped) by the amount
        # of frames that we are skipping. End times can vary more since the default value of
        # time_post_event is relatively large.
        assert all(
            [
                abs(x[0] - y[0]) <= frame_skip
                for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_PRE_5)
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
                for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_POST_40)
            ]
        ), "Comparison failure when frame_skip = %d" % (frame_skip)
        # The calculated end times must always be >= the ground truth's frame number, otherwise
        # we may be discarding frames containing motion due to skipping them.
        assert all(
            [x[1] >= y[1] for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_POST_40)]
        ), "Comparison failure when frame_skip = %d" % (frame_skip)


def test_decode_corrupt_video(corrupt_video):
    """Ensure we can process a video with a single bad frame."""
    scanner = MotionScanner([corrupt_video])
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
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS[1:2], EVENT_FRAME_TOLERANCE)


def test_start_duration(traffic_camera_video):
    """Test basic functionality of MotionScanner with start and duration defined."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0)
    scanner.set_video_time(start_time=200, duration=300)
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    # The set duration should only cover the middle event.
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS[1:2], EVENT_FRAME_TOLERANCE)
