#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2026 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""Tests for the thumbnail imaging helpers and the background loader's lifecycle (with
Tk-free fakes); the Tk wiring itself is verified manually in the GUI."""

import shutil
import threading
import time
import weakref

import numpy as np

from dvr_scan.app.thumbnails import (
    FILMSTRIP_GAP,
    PLACEHOLDER_COLOR,
    THUMBNAIL_HEIGHT,
    ThumbnailLoader,
    filmstrip_image,
    frame_to_image,
    placeholder_image,
)


def test_frame_to_image_scales_to_height_preserving_aspect():
    # 160x90 (w x h) BGR frame; a 54px-tall thumbnail keeps the 16:9 ratio -> 96px wide.
    frame = np.zeros((90, 160, 3), dtype=np.uint8)
    image = frame_to_image(frame, height=54)
    assert image.size == (96, 54)
    assert image.mode == "RGB"


def test_frame_to_image_converts_bgr_to_rgb():
    # Uniform frame with distinct channels: B=10, G=20, R=30 -> RGB pixel (30, 20, 10).
    frame = np.empty((20, 20, 3), dtype=np.uint8)
    frame[:, :, 0] = 10
    frame[:, :, 1] = 20
    frame[:, :, 2] = 30
    image = frame_to_image(frame, height=10)
    assert image.getpixel((0, 0)) == (30, 20, 10)


def test_frame_to_image_default_height():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    image = frame_to_image(frame)
    assert image.height == THUMBNAIL_HEIGHT


def test_frame_to_image_non_default_height():
    # 100x100 (square) frame at a non-default height stays square.
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    image = frame_to_image(frame, height=27)
    assert image.size == (27, 27)


def test_placeholder_image_is_16_by_9():
    image = placeholder_image(height=54)
    assert image.size == (96, 54)
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == PLACEHOLDER_COLOR


def test_placeholder_image_custom_height():
    image = placeholder_image(height=27)
    assert image.height == 27


def test_filmstrip_image_concatenates_frames():
    # Three 100x100 (square) frames at height=10 -> three 10px-wide cells plus 2 gaps.
    frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(3)]
    image = filmstrip_image(frames, height=10)
    expected_width = 3 * 10 + 2 * FILMSTRIP_GAP
    assert image.size == (expected_width, 10)
    assert image.mode == "RGB"


def test_filmstrip_image_empty_falls_back_to_placeholder():
    image = filmstrip_image([], height=54)
    assert image.size == placeholder_image(height=54).size


def test_pad_right_adds_transparent_margin():
    import PIL.Image

    from dvr_scan.app.thumbnails import pad_right

    image = PIL.Image.new("RGB", (10, 4), PLACEHOLDER_COLOR)
    padded = pad_right(image, 8)
    assert padded.size == (18, 4)
    assert padded.mode == "RGBA"
    # Original pixels kept, margin fully transparent.
    assert padded.getpixel((0, 0))[:3] == PLACEHOLDER_COLOR
    assert padded.getpixel((17, 0))[3] == 0
    # Zero margin is a no-op (same object, no mode change).
    assert pad_right(image, 0) is image


# --- ThumbnailLoader lifecycle (Tk-free fakes) ---------------------------------------------


class _FakeRoot:
    """Records `after` / `after_cancel` calls instead of scheduling anything."""

    def __init__(self):
        self.scheduled = []
        self.cancelled = []

    def after(self, _ms, func):
        self.scheduled.append(func)
        return f"after#{len(self.scheduled)}"

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)


class _FakeWidget:
    def __init__(self, root: _FakeRoot):
        self._fake_root = root
        self.exists = True

    def nametowidget(self, name):
        assert name == "."
        return self._fake_root

    def winfo_exists(self):
        return self.exists


def _wait_for(event: threading.Event):
    assert event.wait(timeout=10.0), "timed out waiting for the loader worker"


def test_loader_polls_on_root_and_cancel_cancels_pending_poll():
    """The poll loop is scheduled on the root (not the row widget, which may be destroyed
    first) and cancelled with the loader, so no callback fires on a destroyed widget."""
    root = _FakeRoot()
    loader = ThumbnailLoader(_FakeWidget(root))
    loader.submit("row-0", lambda: None)
    assert len(root.scheduled) == 1
    loader.cancel()
    assert root.cancelled == ["after#1"]
    # A late poll after cancellation is a no-op and does not reschedule.
    root.scheduled[0]()
    assert len(root.scheduled) == 1


def test_loader_drain_stops_when_widget_destroyed():
    root = _FakeRoot()
    widget = _FakeWidget(root)
    loader = ThumbnailLoader(widget)
    loader.submit("row-0", lambda: None)
    widget.exists = False
    root.scheduled[0]()
    assert len(root.scheduled) == 1
    loader.cancel()


def test_loader_finish_runs_on_exit_after_last_job():
    exited = threading.Event()
    exit_threads = []
    done = []

    def on_exit():
        exit_threads.append(threading.current_thread())
        exited.set()

    loader = ThumbnailLoader(_FakeWidget(_FakeRoot()), on_exit=on_exit)
    loader.submit("row-0", lambda: done.append(0))
    loader.submit("row-1", lambda: done.append(1))
    loader.finish()
    _wait_for(exited)
    assert done == [0, 1]
    # Runs on the worker thread (which then exits), not the caller's.
    assert exit_threads[0] is not threading.current_thread()
    loader._thread.join(timeout=10.0)
    assert not loader._thread.is_alive()
    # Submitting after finish() is ignored.
    loader.submit("row-2", lambda: done.append(2))
    assert loader._pending == 2


def test_loader_cancel_runs_on_exit_and_skips_remaining_jobs():
    started = threading.Event()
    release = threading.Event()
    exited = threading.Event()
    done = []

    def slow():
        started.set()
        _wait_for(release)
        done.append("slow")

    loader = ThumbnailLoader(_FakeWidget(_FakeRoot()), on_exit=exited.set)
    loader.submit("row-0", slow)
    loader.submit("row-1", lambda: done.append("skipped"))
    _wait_for(started)
    loader.cancel()
    release.set()
    _wait_for(exited)
    assert done == ["slow"]


def test_loader_without_jobs_runs_on_exit_immediately():
    for stop in ("finish", "cancel"):
        exits = []
        loader = ThumbnailLoader(_FakeWidget(_FakeRoot()), on_exit=lambda e=exits: e.append(1))
        getattr(loader, stop)()
        # Idempotent: on_exit runs once.
        loader.finish()
        loader.cancel()
        assert exits == [1]


class _Provider:
    def __call__(self):
        return None


def test_idle_worker_does_not_keep_last_provider_alive():
    """An idle worker blocked on the next job must not hold the last provider (which may
    keep a video open) via stale locals."""
    loader = ThumbnailLoader(_FakeWidget(_FakeRoot()))
    provider = _Provider()
    ref = weakref.ref(provider)
    loader.submit("row-0", provider)
    del provider
    # Wait until the result is posted (the worker then blocks waiting for more jobs).
    assert loader._results.get(timeout=10.0) == ("row-0", None)
    deadline = time.monotonic() + 10.0
    while ref() is not None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ref() is None
    loader.cancel()


# --- Event table thumbnails release the source video --------------------------------------


def test_event_frame_providers_release_closes_video(tmp_path, traffic_camera_video):
    """Once released, the shared input is closed: on Windows an open file can't be
    renamed, which is how a user noticed the leak."""
    from scenedetect import FrameTimecode

    from dvr_scan.app.scan_window import _event_frame_providers
    from dvr_scan.scanner import MotionEvent

    source = tmp_path / "source.mp4"
    shutil.copyfile(traffic_camera_video, source)
    event = MotionEvent(start=FrameTimecode(10, 25.0), end=FrameTimecode(40, 25.0))
    providers, release = _event_frame_providers([str(source)], [event])
    frames = providers[0]()
    assert frames
    del frames
    release()
    source.rename(tmp_path / "renamed.mp4")
