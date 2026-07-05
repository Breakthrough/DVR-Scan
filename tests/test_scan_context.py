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

import logging
import platform
import re
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

# Ground truth with time_post_event=10 and merge_window=120: the last two baseline
# events are separated by ~102 frames without motion so they merge, while the first
# stays separate (~260 frame gap). Each event ends 10 frames after its last motion.
TRAFFIC_CAMERA_EVENTS_MERGE_120_POST_10 = [
    (9, 109),
    (358, 563),
]

# Ground truth with time_post_event=10 and merging following it (merge_window auto):
# gaps in motion longer than 10 frames split the baseline events further apart.
TRAFFIC_CAMERA_EVENTS_POST_10 = [
    (9, 30),
    (50, 109),
    (358, 387),
    (394, 417),
    (428, 451),
    (542, 563),
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


def test_merge_window(traffic_camera_video):
    """Groups of motion closer together than merge_window must merge into the same
    event, with time_post_event only padding the end of each event (#195)."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(
        min_event_len=4, time_pre_event=0, time_post_event=10, merge_window=120
    )
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS_MERGE_120_POST_10, EVENT_FRAME_TOLERANCE)


def test_merge_window_auto_matches_post_event(traffic_camera_video):
    """The default merge window (auto) must merge based on time_post_event, matching
    the behavior of previous versions (#195)."""

    def scan_events(merge_window):
        scanner = MotionScanner([traffic_camera_video])
        scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
        scanner.set_event_params(
            min_event_len=4, time_pre_event=0, time_post_event=10, merge_window=merge_window
        )
        event_list = scanner.scan().event_list
        return [(event.start.frame_num, event.end.frame_num) for event in event_list]

    auto = scan_events("auto")
    assert auto == scan_events(10)
    compare_event_lists(auto, TRAFFIC_CAMERA_EVENTS_POST_10, EVENT_FRAME_TOLERANCE)


def test_post_event_padding_with_merge_window(traffic_camera_video):
    """time_post_event must pad each event's end without affecting merging, clamped
    to the end of the video (#72)."""

    def scan_events(time_post_event):
        scanner = MotionScanner([traffic_camera_video])
        scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
        scanner.set_event_params(
            min_event_len=4,
            time_pre_event=0,
            time_post_event=time_post_event,
            merge_window=120,
        )
        event_list = scanner.scan().event_list
        return [(event.start.frame_num, event.end.frame_num) for event in event_list]

    short, long = scan_events(5), scan_events(25)
    # Padding must not change how events merge, nor their start times.
    assert len(short) == len(TRAFFIC_CAMERA_EVENTS_MERGE_120_POST_10)
    assert [event[0] for event in short] == [event[0] for event in long]
    # The first event ends exactly 20 frames later with 20 extra frames of padding,
    # while the final event's padding is clamped to the end of the video.
    assert long[0][1] - short[0][1] == 20
    assert short[-1][1] <= long[-1][1] <= 576


def test_post_event_capped_to_merge_window(traffic_camera_video, caplog):
    """A time_post_event larger than the merge window must be capped to it, with a
    warning, so padded events can never overlap the next event's motion."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0, time_post_event=40, merge_window=10)
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        event_list = scanner.scan().event_list
    assert "merge-window" in caplog.text
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS_POST_10, EVENT_FRAME_TOLERANCE)


def test_merge_window_end_of_video(traffic_camera_video):
    """When the video ends while still within the merge window, the final event's end
    must be clamped to the post-event padding, not the end of the video."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(
        min_event_len=4, time_pre_event=0, time_post_event=5, merge_window=100000
    )
    event_list = scanner.scan().event_list
    event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
    compare_event_lists(event_list, [(9, 558)], EVENT_FRAME_TOLERANCE)


def test_merge_window_with_frame_skip(traffic_camera_video):
    """Merging behavior must be stable when frame skipping is used."""
    for frame_skip in range(1, 6):
        scanner = MotionScanner([traffic_camera_video], frame_skip=frame_skip)
        scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
        scanner.set_event_params(
            min_event_len=4, time_pre_event=0, time_post_event=10, merge_window=120
        )
        event_list = scanner.scan().event_list
        event_list = [(event.start.frame_num, event.end.frame_num) for event in event_list]
        compare_event_lists(event_list, TRAFFIC_CAMERA_EVENTS_MERGE_120_POST_10, frame_skip + 1)


def test_scan_context_vfr_merge_window(vfr_video):
    """Merge window gaps must be measured in wall-clock (PTS) time on VFR input: the
    motion gap between the last two events is ~8.2s of wall-clock time in the slowed
    section, but only ~6.1s when derived from the container's average framerate."""

    def scan_events(merge_window):
        scanner = MotionScanner([vfr_video])
        scanner.set_detection_params()
        scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
        scanner.set_event_params(
            min_event_len=4, time_pre_event=0, time_post_event="0.4s", merge_window=merge_window
        )
        return scanner.scan().event_list

    # A 7 second window must NOT merge the last two events (their gap only appears
    # shorter than that when measured with the average framerate).
    event_list = scan_events("7s")
    assert len(event_list) == 3
    check_vfr_event_starts(event_list, VFR_EXPECTED_START_SECONDS)
    # A 10 second window must merge them.
    event_list = scan_events("10s")
    assert len(event_list) == 2
    check_vfr_event_starts(event_list, VFR_EXPECTED_START_SECONDS[:2])


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


def test_max_events(traffic_camera_video):
    """Setting max_events must end the scan as soon as that many events are found (#261)."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    scanner.set_event_params(min_event_len=4, time_pre_event=0, max_events=1)
    result = scanner.scan()
    assert len(result.event_list) == 1
    # Reaching max_events counts as a completed scan, not an interrupted one, so the
    # GUI still presents results (is_stopped() gates result presentation).
    assert not scanner.is_stopped()
    # The scan must have ended early: the first event ends less than halfway through
    # the video (see TRAFFIC_CAMERA_EVENTS), so most frames should remain unprocessed.
    assert result.num_frames < 576


def test_highscore_resets_between_events(traffic_camera_video, tmp_path, caplog):
    """The per-event high score must be reset after every event even when thumbnails
    are disabled, so debug output and thumbnails reflect each event (#267)."""

    def scan_high_scores(thumbnails: bool) -> ty.List[float]:
        scanner = MotionScanner([traffic_camera_video])
        scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
        scanner.set_event_params(min_event_len=4, time_pre_event=0)
        if thumbnails:
            scanner.set_output(output_dir=tmp_path)
            scanner.set_thumbnail_params(thumbnails="highscore")
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="dvr_scan"):
            result = scanner.scan()
        assert len(result.event_list) == len(TRAFFIC_CAMERA_EVENTS)
        # The candidate state must not persist once the scan completes.
        assert scanner._highscore == 0
        assert scanner._highframe is None
        scores = [
            float(match.group(1))
            for match in (
                re.search(r"high score (\d+(?:\.\d+)?)", record.getMessage())
                for record in caplog.records
            )
            if match is not None
        ]
        assert len(scores) == len(result.event_list)
        return scores

    scores_without_thumbnails = scan_high_scores(thumbnails=False)
    scores_with_thumbnails = scan_high_scores(thumbnails=True)
    # Scores must be tracked per-event, not as a running maximum across the scan,
    # regardless of whether thumbnails are enabled.
    assert scores_without_thumbnails == pytest.approx(scores_with_thumbnails)
    # One thumbnail must be written per detected event.
    assert len(list(tmp_path.glob("*.jpg"))) == len(TRAFFIC_CAMERA_EVENTS)


def test_highscore_discarded_for_rejected_events(traffic_camera_video):
    """Motion spikes that never become events must not leave a stale thumbnail
    candidate behind for the next event (#268)."""
    scanner = MotionScanner([traffic_camera_video])
    scanner.set_regions(regions=[TRAFFIC_CAMERA_ROI])
    # Use a min_event_len longer than the scanned duration so motion is detected but
    # no event can ever be confirmed, then stop scanning inside the motion-free gap
    # after the first motion spike (see TRAFFIC_CAMERA_EVENTS).
    scanner.set_event_params(min_event_len=500, time_pre_event=0)
    scanner.set_video_time(end_time=200)
    result = scanner.scan()
    assert not result.event_list
    assert scanner._highscore == 0
    assert scanner._highframe is None
