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
"""Synthetic unit tests for `MotionEventTracker` (pure state machine, no video I/O)."""

import logging
import typing as ty
from fractions import Fraction

import numpy as np
import pytest
from scenedetect import FrameTimecode
from scenedetect.common import Timecode

from dvr_scan.scanner import CompletedEvent, MotionEventTracker


def _pts(seconds: float, fps: float = 10.0) -> FrameTimecode:
    """Create a microsecond PTS-backed `FrameTimecode` like `MotionScanner._presentation_time()`."""
    return FrameTimecode(
        timecode=Timecode(pts=round(seconds * 1_000_000), time_base=Fraction(1, 1_000_000)),
        fps=fps,
    )


def _make_tracker(
    *,
    fps: float = 10.0,
    threshold: float = 0.5,
    min_event_len: ty.Union[int, float, str] = 3,
    time_pre_event: ty.Union[int, float, str] = 0,
    time_post_event: ty.Union[int, float, str] = 0,
    max_event_len: ty.Optional[ty.Union[int, float, str]] = None,
    merge_window: ty.Optional[ty.Union[int, float, str]] = None,
    frame_skip: int = 0,
    max_events: int = 0,
    scan_start_time: ty.Optional[FrameTimecode] = None,
) -> MotionEventTracker:
    return MotionEventTracker(
        threshold=threshold,
        min_event_len=FrameTimecode(min_event_len, fps),
        time_pre_event=FrameTimecode(time_pre_event, fps),
        time_post_event=FrameTimecode(time_post_event, fps),
        frame_rate=fps,
        scan_start_time=scan_start_time if scan_start_time is not None else _pts(0.0, fps),
        max_event_len=FrameTimecode(max_event_len, fps) if max_event_len is not None else None,
        merge_window=FrameTimecode(merge_window, fps) if merge_window is not None else None,
        frame_skip=frame_skip,
        max_events=max_events,
    )


def _drive(
    tracker: MotionEventTracker,
    samples: ty.Sequence[ty.Tuple[FrameTimecode, float]],
    *,
    flush: bool = True,
    stop_on_max_events: bool = True,
) -> ty.Tuple[ty.List[ty.Tuple[CompletedEvent, ty.List[FrameTimecode]]], ty.List[FrameTimecode]]:
    """Feed `(timecode, score)` pairs into `tracker`, using each `timecode` as its frame payload.

    Returns `(recorded_events, orphan_frames)` where each recorded entry is
    `(CompletedEvent, emitted_frame_timecodes)` in exact encoder order.
    """
    recorded: ty.List[ty.Tuple[CompletedEvent, ty.List[FrameTimecode]]] = []
    current_frames: ty.List[FrameTimecode] = []

    for tc, score in samples:
        step = tracker.update(tc, score, frame=tc)
        current_frames.extend(step.frames_before_event)
        if step.completed_event is not None:
            recorded.append((step.completed_event, current_frames))
            current_frames = []
        current_frames.extend(step.frames_after_event)
        if stop_on_max_events and step.max_events_reached:
            break

    if flush and not tracker.max_events_reached:
        completed = tracker.finish()
        if completed is not None:
            recorded.append((completed, current_frames))
            current_frames = []

    return recorded, current_frames


def _cfr_samples(
    scores: ty.Sequence[float],
    *,
    fps: float = 10.0,
    start_seconds: float = 0.0,
    frame_skip: int = 0,
) -> ty.List[ty.Tuple[FrameTimecode, float]]:
    step = (1 + frame_skip) / fps
    return [(_pts(start_seconds + i * step, fps), score) for i, score in enumerate(scores)]


def _assert_frames_match_spans(
    recorded: ty.List[ty.Tuple[CompletedEvent, ty.List[FrameTimecode]]],
    all_timecodes: ty.Sequence[FrameTimecode],
) -> None:
    """Every event's emitted frames must be exactly the processed frames in `[start, end)`."""
    for completed, frames in recorded:
        start, end = completed.event.start, completed.event.end
        assert end.seconds >= start.seconds
        expected = [tc for tc in all_timecodes if start <= tc < end]
        assert [tc.seconds for tc in frames] == [tc.seconds for tc in expected]


# --- Basic detection and min_event_len ----------------------------------------------------


def test_single_event_meets_min_event_len():
    """A motion burst of at least `min_event_len` frames triggers one event with matching frames."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=3)
    # Motion on frames 2, 3, 4, 5 (0.2s..0.5s); quiet before and after.
    scores = [0.0, 0.0, 0.6, 0.8, 1.0, 0.7, 0.0, 0.0]
    samples = _cfr_samples(scores, fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 1
    completed, frames = recorded[0]
    assert completed.event_number == 1
    assert completed.event.start.seconds == pytest.approx(0.2)
    assert completed.event.end.seconds == pytest.approx(0.6)
    assert [tc.seconds for tc in frames] == pytest.approx([0.2, 0.3, 0.4, 0.5])
    assert tracker.events == [completed.event]
    assert not tracker.in_motion_event
    assert tracker.active_event_count == 1


def test_sub_threshold_and_short_bursts_rejected():
    """Below-threshold scores and bursts shorter than `min_event_len` produce no events."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=4)
    scores = [0.1, 0.49, 0.9, 0.8, 0.7, 0.4, 1.0, 1.0, 0.0, 0.9, 0.9, 0.9, 0.0]
    samples = _cfr_samples(scores, fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert recorded == []
    assert orphans == []
    assert tracker.events == []
    assert tracker.active_event_count == 0


def test_zero_frames_and_eof_without_motion():
    """Calling `finish()` with no frames or only idle frames is a clean no-op."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=2)
    assert tracker.finish() is None
    assert tracker.events == []

    for tc, score in _cfr_samples([0.0, 0.2, 0.1], fps=10.0):
        step = tracker.update(tc, score, frame=tc)
        assert not step.frames_before_event
        assert not step.frames_after_event
        assert step.completed_event is None
        assert not step.event_started
    assert tracker.finish() is None
    assert tracker.events == []


def test_first_frame_suppressed_override():
    """Explicit `above_threshold=False` suppresses highscore on frame 0 while preserving window."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=1)
    step = tracker.update(_pts(0.0), score=2.0, frame="f0", above_threshold=False)
    assert step.event_started
    assert step.frames_after_event == ["f0"]
    assert tracker.high_score == 0
    assert tracker.high_frame is None

    completed = tracker.finish()
    assert completed is not None
    assert completed.high_score == 0
    assert completed.high_frame is None


# --- Pre-event and post-event padding & clamping ------------------------------------------


def test_pre_event_padding_and_clamping_to_scan_start():
    """`time_pre_event` shifts start earlier and clamps to `scan_start_time` (zero or seeked)."""
    # Unclamped pre-roll (motion at 0.5..0.7s, pre=0.3s -> start=0.2s).
    tracker = _make_tracker(fps=10.0, min_event_len=2, time_pre_event=3, time_post_event=0)
    samples = _cfr_samples([0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)
    assert not orphans
    assert len(recorded) == 1
    assert recorded[0][0].event.start.seconds == pytest.approx(0.2)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.7)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])

    # Clamped at 0.0s (motion at 0.1..0.2s, pre=0.5s -> clamped to 0.0s).
    tracker_zero = _make_tracker(fps=10.0, min_event_len=2, time_pre_event=5)
    samples_zero = _cfr_samples([0.0, 1.0, 1.0, 0.0], fps=10.0)
    recorded_zero, _ = _drive(tracker_zero, samples_zero)
    assert recorded_zero[0][0].event.start.seconds == pytest.approx(0.0)
    _assert_frames_match_spans(recorded_zero, [tc for tc, _ in samples_zero])

    # Clamped at non-zero seek start (5.0s).
    tracker_seek = _make_tracker(
        fps=10.0, min_event_len=2, time_pre_event=5, scan_start_time=_pts(5.0, 10.0)
    )
    samples_seek = _cfr_samples([0.0, 1.0, 1.0, 0.0], fps=10.0, start_seconds=5.0)
    recorded_seek, _ = _drive(tracker_seek, samples_seek)
    assert recorded_seek[0][0].event.start.seconds == pytest.approx(5.0)
    _assert_frames_match_spans(recorded_seek, [tc for tc, _ in samples_seek])


def test_pre_event_clamps_to_previous_event_end():
    """Pre-event padding must never make an event overlap the end of the previous event."""
    tracker = _make_tracker(
        fps=10.0, min_event_len=2, time_pre_event=5, time_post_event=0, merge_window=1
    )
    # Event 1: motion at 0.0, 0.1 -> ends at 0.2 when 0.2 is quiet (gap 0.1 >= merge_window 0.1).
    # Event 2: motion at 0.3, 0.4 -> pre_event of 0.5s would want -0.2s, must clamp to 0.2s.
    samples = _cfr_samples([1.0, 1.0, 0.0, 1.0, 1.0, 0.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 2
    assert recorded[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.2)
    assert recorded[1][0].event.start.seconds == pytest.approx(0.2)
    assert recorded[1][0].event.end.seconds == pytest.approx(0.5)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_post_event_padding_and_eof_clamping():
    """`time_post_event` extends event end and clamps to stream end when video ends early."""
    # Enough trailing frames for full 0.3s post-event padding.
    tracker = _make_tracker(fps=10.0, min_event_len=2, time_post_event=3)
    samples = _cfr_samples([0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)
    assert not orphans
    assert len(recorded) == 1
    assert recorded[0][0].event.start.seconds == pytest.approx(0.1)
    # Last motion at 0.2s + 0.1s frame duration + 0.3s post-event = 0.6s.
    assert recorded[0][0].event.end.seconds == pytest.approx(0.6)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])

    # Stream ends after only 1 quiet frame (0.3s) during 0.5s post-event padding.
    tracker_eof = _make_tracker(fps=10.0, min_event_len=2, time_post_event=5)
    samples_eof = _cfr_samples([0.0, 1.0, 1.0, 0.0], fps=10.0)
    recorded_eof, orphans_eof = _drive(tracker_eof, samples_eof)
    assert not orphans_eof
    assert len(recorded_eof) == 1
    assert recorded_eof[0][0].event.start.seconds == pytest.approx(0.1)
    assert recorded_eof[0][0].event.end.seconds == pytest.approx(0.4)
    _assert_frames_match_spans(recorded_eof, [tc for tc, _ in samples_eof])


# --- Decoupled merge_window ---------------------------------------------------------------


def test_merge_window_auto_matches_post_event():
    """`merge_window=None` behaves identically to `merge_window == time_post_event` (#195)."""
    scores = [0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    samples = _cfr_samples(scores, fps=10.0)

    auto_recorded, _ = _drive(
        _make_tracker(fps=10.0, min_event_len=2, time_post_event=3, merge_window=None),
        samples,
    )
    explicit_recorded, _ = _drive(
        _make_tracker(fps=10.0, min_event_len=2, time_post_event=3, merge_window=3),
        samples,
    )
    assert [(c.event.start, c.event.end) for c, _ in auto_recorded] == [
        (c.event.start, c.event.end) for c, _ in explicit_recorded
    ]
    # The 2-frame quiet gap (0.3s, 0.4s) stays under the 0.3s merge window and merges on 0.5s;
    # the 4-frame quiet gap (0.6s..0.9s) reaches 0.3s at 0.8s and splits into 2 events.
    assert len(auto_recorded) == 2
    _assert_frames_match_spans(auto_recorded, [tc for tc, _ in samples])


def test_merge_window_merges_and_flushes_held_frames():
    """Motion resuming past `time_post_event` in `merge_window` merges and flushes held frames."""
    tracker = _make_tracker(fps=10.0, min_event_len=2, time_post_event=1, merge_window=5)
    # Motion at 0.0, 0.1 -> padded_end = 0.3s.
    # Quiet at 0.2 (sent immediately, < 0.3), 0.3 & 0.4 (held in merge tail, >= 0.3).
    # Motion resumes at 0.5 (0.5 - 0.1 = 0.4 < 0.5) -> held 0.3, 0.4 flushed in order!
    # Quiet at 0.6..1.1 -> closes at 1.0 (1.0 - 0.5 = 0.5 >= 0.5), padded_end = 0.7s.
    scores = [1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    samples = _cfr_samples(scores, fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 1
    completed, frames = recorded[0]
    assert completed.event.start.seconds == pytest.approx(0.0)
    assert completed.event.end.seconds == pytest.approx(0.7)
    assert [tc.seconds for tc in frames] == pytest.approx([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_merge_window_splits_and_seeds_next_event_preroll():
    """When `merge_window` expires, held merge-tail frames seed the next event's pre-roll."""
    tracker = _make_tracker(
        fps=10.0, min_event_len=2, time_pre_event=3, time_post_event=1, merge_window=4
    )
    # Event 1 motion at 0.0, 0.1 -> padded_end = 0.3s, expires at 0.5s (0.5 - 0.1 = 0.4s).
    # Held merge-tail frames: 0.3, 0.4, plus closing frame 0.5 (>= 0.3) -> seed pre-roll buffer!
    # Event 2 motion at 0.6, 0.7 -> with pre_event=0.3s, starts at 0.3s and includes 0.3, 0.4, 0.5!
    scores = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    samples = _cfr_samples(scores, fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 2
    assert recorded[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.3)
    assert recorded[1][0].event.start.seconds == pytest.approx(0.3)
    assert recorded[1][0].event.end.seconds == pytest.approx(0.9)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_post_event_greater_than_merge_window_capped_with_warning(caplog):
    """`time_post_event > merge_window` warns and caps post-event padding to `merge_window`."""
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        tracker = _make_tracker(fps=10.0, min_event_len=2, time_post_event=5, merge_window=2)
    assert "merge-window" in caplog.text

    samples = _cfr_samples([1.0, 1.0, 0.0, 0.0, 0.0, 0.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)
    assert not orphans
    assert len(recorded) == 1
    # Last motion at 0.1s + 0.1s frame + 0.2s capped post-event = 0.4s.
    assert recorded[0][0].event.end.seconds == pytest.approx(0.4)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_eof_during_merge_tail_clamps_to_post_event_padding():
    """EOF while waiting out `merge_window` past `padded_end` clamps to `padded_end`."""
    tracker = _make_tracker(fps=10.0, min_event_len=2, time_post_event=1, merge_window=100)
    # Motion at 0.0, 0.1 -> padded_end = 0.3s; quiet frames 0.2..0.7 until EOF.
    samples = _cfr_samples([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 1
    assert recorded[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.3)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


# --- max_event_length splitting -----------------------------------------------------------


def test_max_event_length_split_with_continued_motion():
    """Continuous motion past `max_event_len` splits with no padding and immediate restart."""
    tracker = _make_tracker(fps=10.0, min_event_len=2, time_post_event=5, max_event_len="0.4s")
    # 9 frames of continuous motion (0.0..0.8s) -> [0.0, 0.4), [0.4, 0.8), [0.8, 0.9).
    samples = _cfr_samples([1.0] * 9, fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 3
    spans = [(c.event.start.seconds, c.event.end.seconds) for c, _ in recorded]
    assert spans == [
        pytest.approx((0.0, 0.4)),
        pytest.approx((0.4, 0.8)),
        pytest.approx((0.8, 0.9)),
    ]
    assert recorded[1][0].event.start == recorded[0][0].event.end
    assert recorded[2][0].event.start == recorded[1][0].event.end
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_max_event_length_split_flushes_merge_tail_when_motion_resumes():
    """Resuming motion on the split frame flushes held merge-tail frames into the ending event."""
    tracker = _make_tracker(
        fps=10.0, min_event_len=2, time_post_event=1, merge_window=10, max_event_len="0.5s"
    )
    # Motion 0.0, 0.1 -> padded_end = 0.3s.
    # Quiet 0.2 (emitted), 0.3 & 0.4 (held in merge tail).
    # Motion resumes at 0.5 -> exceeds max_event_len=0.5s (0.5 + 0.1 > 0.0 + 0.5)!
    # Held frames 0.3, 0.4 flush BEFORE event 1 completes as [0.0, 0.5),
    # and frame 0.5 starts event 2 in frames_after_event!
    samples = _cfr_samples([1.0, 1.0, 0.0, 0.0, 0.0, 1.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 2
    assert recorded[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.5)
    assert [tc.seconds for tc in recorded[0][1]] == pytest.approx([0.0, 0.1, 0.2, 0.3, 0.4])
    assert recorded[1][0].event.start.seconds == pytest.approx(0.5)
    assert recorded[1][0].event.end.seconds == pytest.approx(0.6)
    assert [tc.seconds for tc in recorded[1][1]] == pytest.approx([0.5])


def test_max_event_length_split_without_motion_clamps_correctly():
    """A split on a quiet frame ends at `min(timecode, padded_end)` without starting a new event."""
    # Subcase A: split occurs BEFORE padded_end -> ends at timecode (0.3s < padded_end 0.7s).
    tracker_early = _make_tracker(
        fps=10.0, min_event_len=2, time_post_event=5, max_event_len="0.3s"
    )
    samples_early = _cfr_samples([1.0, 1.0, 0.0, 0.0], fps=10.0)
    recorded_early, orphans_early = _drive(tracker_early, samples_early)
    assert not orphans_early
    assert len(recorded_early) == 1
    assert recorded_early[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded_early[0][0].event.end.seconds == pytest.approx(0.3)
    _assert_frames_match_spans(recorded_early, [tc for tc, _ in samples_early])

    # Subcase B: split occurs AFTER padded_end (during merge tail) -> ends at padded_end (0.3s).
    tracker_late = _make_tracker(
        fps=10.0, min_event_len=2, time_post_event=1, merge_window=10, max_event_len="0.5s"
    )
    samples_late = _cfr_samples([1.0, 1.0, 0.0, 0.0, 0.0, 0.0], fps=10.0)
    recorded_late, orphans_late = _drive(tracker_late, samples_late)
    assert not orphans_late
    assert len(recorded_late) == 1
    assert recorded_late[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded_late[0][0].event.end.seconds == pytest.approx(0.3)
    _assert_frames_match_spans(recorded_late, [tc for tc, _ in samples_late])


def test_max_event_length_bounds_pre_roll():
    """When `time_pre_event >= max_event_len`, pre-roll is trimmed so the event fits the limit."""
    tracker = _make_tracker(
        fps=10.0, min_event_len=2, time_pre_event="1.0s", time_post_event=0, max_event_len="0.3s"
    )
    # Quiet 0.0..0.4s, motion at 0.5, 0.6s -> triggers on 0.6s (step ends at 0.7s).
    # Unbounded pre-roll would start at 0.0s, but max_event_len=0.3s trims start to 0.4s.
    samples = _cfr_samples([0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 1
    assert recorded[0][0].event.start.seconds == pytest.approx(0.4)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.7)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


# --- max_events early stop ----------------------------------------------------------------


def test_max_events_stops_after_limit():
    """`max_events` sets `max_events_reached` on the limiting event and ignores further frames."""
    tracker = _make_tracker(fps=10.0, min_event_len=2, time_post_event=0, max_events=1)
    # Two distinct motion bursts; only the first should be emitted.
    samples = _cfr_samples([1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0], fps=10.0)
    # Drive ALL samples without breaking early to verify tracker ignores post-limit frames too.
    recorded, orphans = _drive(tracker, samples, stop_on_max_events=False)

    assert tracker.max_events_reached
    assert not orphans
    assert len(recorded) == 1
    assert recorded[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.2)
    assert tracker.finish() is None


def test_max_events_stops_on_split():
    """Hitting `max_events` on a `max_event_len` split does not start or score a next event."""
    tracker = _make_tracker(
        fps=10.0, min_event_len=2, time_post_event=1, max_event_len="0.3s", max_events=1
    )
    samples = _cfr_samples([1.0, 2.0, 1.0, 9.0, 9.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples, stop_on_max_events=False)

    assert tracker.max_events_reached
    assert not tracker.in_motion_event
    assert not orphans
    assert len(recorded) == 1
    completed, frames = recorded[0]
    assert completed.event.start.seconds == pytest.approx(0.0)
    assert completed.event.end.seconds == pytest.approx(0.3)
    assert completed.high_score == pytest.approx(2.0)
    assert [tc.seconds for tc in frames] == pytest.approx([0.0, 0.1, 0.2])
    # Peak state must stay cleanly reset after stopping on a split.
    assert tracker.high_score == 0
    assert tracker.high_frame is None


def test_eof_flush_does_not_set_max_events_reached():
    """Completing the Nth event at EOF via `finish()` must not flag early `max_events_reached`."""
    tracker = _make_tracker(fps=10.0, min_event_len=2, time_post_event=0, max_events=1)
    samples = _cfr_samples([1.0, 1.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 1
    assert not tracker.max_events_reached


# --- VFR and frame_skip -------------------------------------------------------------------


def test_vfr_merge_window_and_boundaries_use_pts():
    """Non-uniform frame intervals measure merge gaps and event spans in wall-clock PTS seconds."""
    # Average fps = 10.0, but actual frame timestamps have irregular intervals:
    # Burst 1 at 0.0, 0.05, 0.10 (20 fps), quiet at 0.50 (gap 0.40s < 1.0s),
    # resumes at 0.90 (gap 0.80s < 1.0s).
    # Quiet at 2.10 (gap 1.20s >= 1.0s) closes event 1 at 0.90 + 0.20 + 0.10 = 1.20s.
    # Burst 2 at 5.00, 5.40, 5.80 (2.5 fps), quiet at 7.00 (gap 1.20s >= 1.0s).
    vfr_samples = [
        (_pts(0.00, 10.0), 1.0),
        (_pts(0.05, 10.0), 1.0),
        (_pts(0.10, 10.0), 1.0),
        (_pts(0.50, 10.0), 0.0),
        (_pts(0.90, 10.0), 1.0),
        (_pts(2.10, 10.0), 0.0),
        (_pts(5.00, 10.0), 1.0),
        (_pts(5.40, 10.0), 1.0),
        (_pts(5.80, 10.0), 1.0),
        (_pts(7.00, 10.0), 0.0),
    ]
    tracker = _make_tracker(
        fps=10.0, min_event_len=3, time_pre_event=0, time_post_event="0.2s", merge_window="1.0s"
    )
    recorded, orphans = _drive(tracker, vfr_samples)

    assert not orphans
    assert len(recorded) == 2
    # Event 1 merged across the 0.80s VFR gap and ended at 0.90 + 0.20 + 0.10 = 1.20s.
    assert recorded[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded[0][0].event.end.seconds == pytest.approx(1.2)
    # Event 2 reflects true VFR PTS (5.6..6.1s, not frame-count-derived timestamps).
    assert recorded[1][0].event.start.seconds == pytest.approx(5.6)
    assert recorded[1][0].event.end.seconds == pytest.approx(6.1)
    assert [tc.seconds for tc in recorded[0][1]] == pytest.approx([0.0, 0.05, 0.1, 0.5, 0.9])


def test_frame_skip_scales_window_and_frame_step():
    """`frame_skip` scales the processed-frame window and accounts for skipped frames."""
    # fps=10, frame_skip=1 -> processed frames every 0.2s (frame_step=0.2s).
    # min_event_len=4 source frames -> 4 // 2 = 2 processed frames.
    tracker = _make_tracker(
        fps=10.0,
        min_event_len=4,
        time_pre_event=0,
        time_post_event=2,
        max_event_len="0.6s",
        frame_skip=1,
    )
    # Processed frames at 0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2.
    # Trigger at 0.4s: start_event_shift = (0 + 2 * 2) * 0.1 = 0.4s -> start = 0.1s.
    # At 0.6s: 0.6 + 0.2 > 0.1 + 0.6 -> splits! Event 1 = [0.1, 0.6), Event 2 starts at 0.6.
    # At 1.0s: quiet (1.0 - 0.8 >= 0.2), padded_end = 0.8 + 0.2 + 0.2 = 1.2s.
    # Frame 1.0 < 1.2 -> included in Event 2 before closing!
    samples = _cfr_samples([0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0], fps=10.0, frame_skip=1)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 2
    assert recorded[0][0].event.start.seconds == pytest.approx(0.1)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.6)
    assert recorded[1][0].event.start.seconds == pytest.approx(0.6)
    assert recorded[1][0].event.end.seconds == pytest.approx(1.2)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


# --- Per-event highscore tracking & reset -------------------------------------------------


def test_highscore_tracks_peak_and_resets_between_events():
    """Each event captures its own peak score and a copy of its peak frame, resetting afterwards."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=2, time_post_event=0)
    f0 = np.full((2, 2, 3), 10, dtype=np.uint8)
    f1 = np.full((2, 2, 3), 20, dtype=np.uint8)
    f2 = np.full((2, 2, 3), 30, dtype=np.uint8)
    f3 = np.full((2, 2, 3), 40, dtype=np.uint8)
    f4 = np.full((2, 2, 3), 50, dtype=np.uint8)

    # Event 1 peaks at score 5.0 (f1); Event 2 peaks at score 2.0 (f3) (lower than Event 1!).
    inputs = [
        (_pts(0.0), 1.0, f0),
        (_pts(0.1), 5.0, f1),
        (_pts(0.2), 0.0, f2),  # closes Event 1
        (_pts(0.3), 2.0, f3),
        (_pts(0.4), 1.5, f4),
        (_pts(0.5), 0.0, f2),  # closes Event 2
    ]
    completed_events: ty.List[CompletedEvent] = []
    for tc, score, arr in inputs:
        step = tracker.update(tc, score, frame=arr)
        if step.completed_event is not None:
            completed_events.append(step.completed_event)

    # Mutate original arrays after processing to confirm tracker copied them.
    f1[:] = 0
    f3[:] = 0

    assert len(completed_events) == 2
    assert completed_events[0].high_score == pytest.approx(5.0)
    assert np.all(completed_events[0].high_frame == 20)
    assert completed_events[1].high_score == pytest.approx(2.0)
    assert np.all(completed_events[1].high_frame == 40)
    assert tracker.high_score == 0
    assert tracker.high_frame is None


def test_highscore_discarded_for_rejected_burst():
    """A high-scoring burst shorter than `min_event_len` must not pollute the next event (#268)."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=3, time_post_event=0)
    # 2-frame spike with score 99.0 is rejected when frame 2 drops below threshold.
    samples = [
        (_pts(0.0), 99.0, "spike0"),
        (_pts(0.1), 50.0, "spike1"),
        (_pts(0.2), 0.0, "quiet"),
        (_pts(0.3), 1.0, "ev0"),
        (_pts(0.4), 2.5, "ev1"),
        (_pts(0.5), 1.2, "ev2"),
        (_pts(0.6), 0.0, "end"),
    ]
    completed: ty.List[CompletedEvent] = []
    for tc, score, label in samples:
        step = tracker.update(tc, score, frame=label)
        if step.completed_event is not None:
            completed.append(step.completed_event)

    assert len(completed) == 1
    assert completed[0].high_score == pytest.approx(2.5)
    assert completed[0].high_frame == "ev1"
    assert tracker.high_score == 0
    assert tracker.high_frame is None


def test_highscore_split_attributes_split_frame_to_next_event():
    """On a `max_event_len` split, the split frame's score counts toward the new event."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=2, max_event_len="0.3s")
    inputs = [
        (_pts(0.0), 1.0, "f0"),
        (_pts(0.1), 3.0, "f1"),
        (_pts(0.2), 2.0, "f2"),
        # Split happens at 0.3s with huge score 99.0 -> must belong to Event 2, not Event 1!
        (_pts(0.3), 99.0, "f3"),
        (_pts(0.4), 1.0, "f4"),
    ]
    completed: ty.List[CompletedEvent] = []
    for tc, score, label in inputs:
        step = tracker.update(tc, score, frame=label)
        if step.completed_event is not None:
            completed.append(step.completed_event)
    final = tracker.finish()
    assert final is not None
    completed.append(final)

    assert len(completed) == 2
    assert completed[0].high_score == pytest.approx(3.0)
    assert completed[0].high_frame == "f1"
    assert completed[1].high_score == pytest.approx(99.0)
    assert completed[1].high_frame == "f3"


def test_scan_only_mode_tracks_high_frame_without_buffering_payload():
    """Passing `frame=None` with `high_frame=...` emits no buffered frames but tracks peak frame."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=2, time_post_event=0)
    steps = [
        tracker.update(_pts(0.0), 1.0, frame=None, high_frame="img0"),
        tracker.update(_pts(0.1), 4.0, frame=None, high_frame="img1"),
        tracker.update(_pts(0.2), 0.0, frame=None, high_frame="img2"),
    ]
    assert all(not s.frames_before_event and not s.frames_after_event for s in steps)
    completed = steps[2].completed_event
    assert completed is not None
    assert completed.high_score == pytest.approx(4.0)
    assert completed.high_frame == "img1"


# --- EOF flush ----------------------------------------------------------------------------


def test_eof_flush_while_active_in_motion():
    """EOF while actively detecting motion flushes the event ending at `last_frame + frame_step`."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=2, time_post_event=5)
    samples = _cfr_samples([0.0, 1.0, 2.0, 1.5], fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 1
    completed, frames = recorded[0]
    assert completed.event.start.seconds == pytest.approx(0.1)
    assert completed.event.end.seconds == pytest.approx(0.4)
    assert completed.high_score == pytest.approx(2.0)
    assert [tc.seconds for tc in frames] == pytest.approx([0.1, 0.2, 0.3])
    assert not tracker.in_motion_event
    assert tracker.high_score == 0
    assert tracker.high_frame is None


# --- Buffer release, boundaries, and state invariants -------------------------------------


def test_buffers_released_on_finish_max_events_and_clear_buffers():
    """Frame buffers must be released on finish(), max_events stop, and clear_buffers()."""
    # Idle finish() clears pre-event buffered frames.
    idle_tracker = _make_tracker(fps=10.0, min_event_len=3, time_pre_event=3)
    for tc, score in _cfr_samples([0.0, 0.0, 0.0], fps=10.0):
        idle_tracker.update(tc, score, frame=tc)
    assert idle_tracker._buffered_frames
    assert idle_tracker.finish() is None
    assert idle_tracker._buffered_frames == []
    assert idle_tracker._post_motion_frames == []

    # Active finish() during merge tail clears held post-motion frames.
    active_tracker = _make_tracker(fps=10.0, min_event_len=2, time_post_event=1, merge_window=10)
    for tc, score in _cfr_samples([1.0, 1.0, 0.0, 0.0, 0.0], fps=10.0):
        active_tracker.update(tc, score, frame=tc)
    assert active_tracker._post_motion_frames
    assert active_tracker.finish() is not None
    assert active_tracker._buffered_frames == []
    assert active_tracker._post_motion_frames == []

    # max_events stop via merge-window close releases held frames rather than seeding pre-roll.
    close_tracker = _make_tracker(
        fps=10.0, min_event_len=2, time_post_event=1, merge_window=3, max_events=1
    )
    for tc, score in _cfr_samples([1.0, 1.0, 0.0, 0.0, 0.0], fps=10.0):
        close_tracker.update(tc, score, frame=tc)
    assert close_tracker.max_events_reached
    assert close_tracker._buffered_frames == []
    assert close_tracker._post_motion_frames == []

    # max_events stop via quiet max_event_len split releases held frames too.
    split_tracker = _make_tracker(
        fps=10.0,
        min_event_len=2,
        time_post_event=1,
        merge_window=10,
        max_event_len="0.5s",
        max_events=1,
    )
    for tc, score in _cfr_samples([1.0, 1.0, 0.0, 0.0, 0.0, 0.0], fps=10.0):
        split_tracker.update(tc, score, frame=tc)
    assert split_tracker.max_events_reached
    assert split_tracker._buffered_frames == []
    assert split_tracker._post_motion_frames == []

    # clear_buffers() drops buffered frames while preserving high_score / high_frame.
    cancel_tracker = _make_tracker(fps=10.0, min_event_len=3, time_pre_event=2)
    cancel_tracker.update(_pts(0.0), 0.0, frame="f0")
    cancel_tracker.update(_pts(0.1), 4.5, frame="f1")
    assert cancel_tracker._buffered_frames
    cancel_tracker.clear_buffers()
    assert cancel_tracker._buffered_frames == []
    assert cancel_tracker._post_motion_frames == []
    assert cancel_tracker.high_score == pytest.approx(4.5)
    assert cancel_tracker.high_frame == "f1"


def test_exact_threshold_boundary():
    """`score == threshold` triggers motion while strictly lower scores do not."""
    tracker = _make_tracker(fps=10.0, threshold=0.5, min_event_len=2, time_post_event=0)
    samples = _cfr_samples([0.499999, 0.5, 0.5, 0.499999], fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 1
    assert recorded[0][0].event.start.seconds == pytest.approx(0.1)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.3)
    assert recorded[0][0].high_score == pytest.approx(0.5)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_default_scan_start_time_is_zero():
    """Omitting `scan_start_time` defaults to `FrameTimecode(0, frame_rate)`."""
    tracker = MotionEventTracker(
        threshold=0.5,
        min_event_len=FrameTimecode(2, 10.0),
        time_pre_event=FrameTimecode(5, 10.0),
        time_post_event=FrameTimecode(0, 10.0),
        frame_rate=10.0,
    )
    samples = _cfr_samples([0.0, 1.0, 1.0, 0.0], fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 1
    assert recorded[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.3)
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_quiet_max_event_length_split_during_merge_tail_seeds_next_preroll():
    """Held merge-tail frames after a quiet `max_event_len` split seed the next event's pre-roll."""
    tracker = _make_tracker(
        fps=10.0,
        min_event_len=2,
        time_pre_event=3,
        time_post_event=1,
        merge_window=10,
        max_event_len="0.5s",
    )
    # Event 1 motion at 0.0, 0.1 -> padded_end = 0.3s.
    # Quiet 0.2 (emitted), 0.3 & 0.4 (held in merge tail).
    # Quiet 0.5 hits max_event_len (0.5 + 0.1 > 0.5) -> Event 1 ends at 0.3s, held frames
    # 0.3, 0.4 seed _buffered_frames and 0.5 is appended to _buffered_frames.
    # Motion at 0.6, 0.7 -> Event 2 starts at 0.3s with pre-roll frames 0.3, 0.4, 0.5, and
    # quiet 0.8 hits max_event_len (0.3 + 0.5 = 0.8s) so Event 2 ends at 0.8s.
    scores = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0]
    samples = _cfr_samples(scores, fps=10.0)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 2
    assert recorded[0][0].event.start.seconds == pytest.approx(0.0)
    assert recorded[0][0].event.end.seconds == pytest.approx(0.3)
    assert recorded[1][0].event.start.seconds == pytest.approx(0.3)
    assert recorded[1][0].event.end.seconds == pytest.approx(0.8)
    assert [tc.seconds for tc in recorded[1][1]] == pytest.approx([0.3, 0.4, 0.5, 0.6, 0.7])
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_max_event_length_floored_to_frame_step():
    """`max_event_len < frame_step` floors to `frame_step` so events cover at least one step."""
    # fps=10, frame_skip=1 -> frame_step = 0.2s, while requested max_event_len = 0.05s.
    tracker = _make_tracker(
        fps=10.0,
        min_event_len=1,
        time_pre_event=0,
        time_post_event=0,
        max_event_len="0.05s",
        frame_skip=1,
    )
    samples = _cfr_samples([1.0, 1.0, 1.0], fps=10.0, frame_skip=1)
    recorded, orphans = _drive(tracker, samples)

    assert not orphans
    assert len(recorded) == 3
    for completed, frames in recorded:
        assert completed.event.end.seconds - completed.event.start.seconds == pytest.approx(0.2)
        assert len(frames) == 1
    _assert_frames_match_spans(recorded, [tc for tc, _ in samples])


def test_end_before_start_clamped_in_finish_event():
    """Non-monotonic timestamps yielding `end < start` clamp event end to start."""
    tracker = _make_tracker(fps=10.0, min_event_len=1, time_pre_event=0, time_post_event=0)
    # Start event at 1.0s, then supply an out-of-order earlier frame at 0.5s before EOF.
    tracker.update(_pts(1.0), 1.0, frame="f0")
    tracker.update(_pts(0.5), 1.0, frame="f1")
    completed = tracker.finish()

    assert completed is not None
    assert completed.event.start.seconds == pytest.approx(1.0)
    assert completed.event.end == completed.event.start


def test_active_event_count_while_in_progress():
    """`active_event_count` reflects completed events plus any active or split event."""
    tracker = _make_tracker(
        fps=10.0, min_event_len=2, time_post_event=1, merge_window=2, max_event_len="0.4s"
    )
    assert tracker.active_event_count == 0
    tracker.update(_pts(0.0), 1.0)
    assert tracker.active_event_count == 0
    tracker.update(_pts(0.1), 1.0)  # Event 1 starts
    assert tracker.in_motion_event
    assert tracker.active_event_count == 1
    tracker.update(_pts(0.2), 1.0)
    tracker.update(_pts(0.3), 1.0)
    tracker.update(_pts(0.4), 1.0)  # Splits: Event 1 ends, Event 2 starts immediately
    assert tracker.in_motion_event
    assert len(tracker.events) == 1
    assert tracker.active_event_count == 2
    tracker.update(_pts(0.5), 0.0)  # In Event 2 merge window
    assert tracker.active_event_count == 2
    tracker.update(_pts(0.6), 0.0)
    tracker.update(_pts(0.7), 0.0)  # Event 2 closes
    assert not tracker.in_motion_event
    assert tracker.active_event_count == 2


def test_events_property_returns_copy():
    """Mutating the list returned by `tracker.events` must not mutate internal tracker state."""
    tracker = _make_tracker(fps=10.0, min_event_len=1, time_post_event=0)
    tracker.update(_pts(0.0), 1.0)
    tracker.update(_pts(0.1), 0.0)

    snapshot = tracker.events
    assert len(snapshot) == 1
    snapshot.clear()
    assert len(tracker.events) == 1
    assert tracker.active_event_count == 1
