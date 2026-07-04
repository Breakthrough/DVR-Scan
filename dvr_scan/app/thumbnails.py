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

"""Shared helpers for decoding and showing small video/event thumbnails.

Decoding a frame is too slow to do on the UI thread, so rows are shown with a placeholder
image and the real thumbnail is produced on a background worker thread (`ThumbnailLoader`).
Results are handed back to the UI thread via a queue that is drained from a Tk `after`
loop, so no Tk call is ever made off the UI thread. By default the loader drives
`ttk.Treeview` rows, but any widget that addresses rows by id can be targeted via a custom
`apply_image` callback (see `VideoList` in `video_list.py`).
"""

import queue
import threading
import tkinter as tk
import tkinter.ttk as ttk
import typing as ty
from logging import getLogger

import cv2
import numpy as np
import PIL.Image
import PIL.ImageTk

logger = getLogger("dvr_scan")

# Fixed thumbnail height in pixels; width is derived from each frame's aspect ratio.
THUMBNAIL_HEIGHT = 54
# Extra vertical room so the image is not clipped by the row border.
ROW_PADDING = 4
ROW_HEIGHT = THUMBNAIL_HEIGHT + ROW_PADDING
# Style applied to treeviews that show thumbnails (inherits from the base "Treeview").
THUMBNAIL_STYLE = "Thumbnail.Treeview"
# Background color (RGB) of the "loading" placeholder frame.
PLACEHOLDER_COLOR = (43, 43, 43)
# How often the UI thread drains finished thumbnails, in milliseconds.
POLL_INTERVAL_MS = 50

# Number of frames sampled across each video/event to form the preview filmstrip.
FILMSTRIP_FRAMES = 4
# Gap (px) and its color between adjacent frames in the strip.
FILMSTRIP_GAP = 2
FILMSTRIP_GAP_COLOR = (20, 20, 20)
# Nominal per-frame width (16:9), used to size the placeholder and column before any
# real frame (whose true aspect ratio may differ) has been decoded.
_NOMINAL_FRAME_WIDTH = round(THUMBNAIL_HEIGHT * 16 / 9)
FILMSTRIP_WIDTH = FILMSTRIP_FRAMES * _NOMINAL_FRAME_WIDTH + (FILMSTRIP_FRAMES - 1) * FILMSTRIP_GAP


def frame_to_image(frame_bgr: np.ndarray, height: int = THUMBNAIL_HEIGHT) -> PIL.Image.Image:
    """Convert a decoded BGR frame (as returned by OpenCV) into an RGB `PIL.Image`
    scaled to `height` pixels tall, preserving aspect ratio. Pure CPU and Tk-free, so
    it is safe to call from a worker thread."""
    source_height, source_width = frame_bgr.shape[:2]
    width = max(1, round(source_width * (height / source_height)))
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    image = PIL.Image.fromarray(rgb)
    return image.resize((width, height), PIL.Image.LANCZOS)


def filmstrip_image(
    frames: ty.Sequence[np.ndarray], height: int = THUMBNAIL_HEIGHT
) -> PIL.Image.Image:
    """Compose frames sampled across time into a single horizontal RGB strip (a mini
    contact sheet), each frame scaled to `height` and separated by a thin gap. Falls
    back to a placeholder if `frames` is empty. Tk-free; safe on a worker thread."""
    images = [frame_to_image(frame, height) for frame in frames]
    if not images:
        return placeholder_image(height)
    total_width = sum(image.width for image in images) + FILMSTRIP_GAP * (len(images) - 1)
    strip = PIL.Image.new("RGB", (total_width, height), FILMSTRIP_GAP_COLOR)
    offset = 0
    for image in images:
        strip.paste(image, (offset, 0))
        offset += image.width + FILMSTRIP_GAP
    return strip


def placeholder_image(height: int = THUMBNAIL_HEIGHT) -> PIL.Image.Image:
    """A neutral 16:9 "loading" frame shown until a row's real thumbnail is ready."""
    width = max(1, round(height * 16 / 9))
    return PIL.Image.new("RGB", (width, height), PLACEHOLDER_COLOR)


def filmstrip_placeholder(height: int = THUMBNAIL_HEIGHT) -> PIL.Image.Image:
    """A neutral strip-width "loading" image, sized so the preview column does not
    resize when the real filmstrip swaps in."""
    return PIL.Image.new("RGB", (FILMSTRIP_WIDTH, height), PLACEHOLDER_COLOR)


def to_photo(image: PIL.Image.Image) -> PIL.ImageTk.PhotoImage:
    """Wrap a `PIL.Image` as a Tk image. Must be called on the UI thread."""
    return PIL.ImageTk.PhotoImage(image)


def configure_thumbnail_rows(style_name: str = THUMBNAIL_STYLE) -> str:
    """Register the thumbnail treeview style (taller rows) and return its name."""
    ttk.Style().configure(style_name, rowheight=ROW_HEIGHT)
    return style_name


# A provider samples one row's frames on the worker thread, returning a list of BGR
# frames (composed into a filmstrip) or None if none are available (e.g. the video
# could not be opened or seeked). An empty list is treated the same as None.
FrameProvider = ty.Callable[[], ty.Optional[ty.List[np.ndarray]]]


# Applies a finished thumbnail to row `iid`, returning True if the row still exists (and
# the photo was set) or False if it has since been removed. The loader keeps a reference
# to photos it successfully applied so Tk does not garbage-collect them.
ApplyImage = ty.Callable[[str, PIL.ImageTk.PhotoImage], bool]


class ThumbnailLoader:
    """Decodes thumbnails on a single background thread and swaps them in once ready.
    Jobs may be submitted incrementally (e.g. as videos are added) and are processed in
    submission order, which the event-table provider relies on for forward-only seeking.
    The loader owns the resulting `PhotoImage`s so Tk does not garbage-collect them while
    they are displayed.

    By default it drives `ttk.Treeview` rows (setting each row's `image`), but any widget
    that lays out rows by `iid` can be targeted by passing a custom `apply_image`."""

    def __init__(
        self,
        widget: tk.Widget,
        *,
        height: int = THUMBNAIL_HEIGHT,
        poll_interval_ms: int = POLL_INTERVAL_MS,
        apply_image: ty.Optional[ApplyImage] = None,
    ):
        self._widget = widget
        self._apply_image = apply_image if apply_image is not None else self._apply_to_tree
        self._height = height
        self._poll_interval_ms = poll_interval_ms
        self._jobs: "queue.Queue[ty.Optional[ty.Tuple[str, FrameProvider]]]" = queue.Queue()
        self._results: "queue.Queue[ty.Tuple[str, ty.Optional[PIL.Image.Image]]]" = queue.Queue()
        self._photos: ty.Dict[str, PIL.ImageTk.PhotoImage] = {}
        self._thread: ty.Optional[threading.Thread] = None
        self._cancelled = False
        self._poller_active = False
        self._pending = 0

    def submit(self, iid: str, provider: FrameProvider):
        """Queue a thumbnail to be decoded for row `iid`. Safe to call repeatedly as
        rows are added; starts the worker and UI poller on first use. A cancelled loader
        cannot be reused; construct a fresh instance instead."""
        if self._cancelled:
            return
        self._pending += 1
        self._jobs.put((iid, provider))
        if self._thread is None:
            self._thread = threading.Thread(target=self._work, daemon=True)
            self._thread.start()
        if not self._poller_active:
            self._poller_active = True
            self._widget.after(self._poll_interval_ms, self._drain)

    def cancel(self):
        """Stop loading and drop references. Call when the rows are cleared or the
        owning widget is destroyed so pending swaps don't target deleted rows.
        Idempotent; the early return on `_cancelled` (in `_drain`) also discards any
        results the worker enqueued before it observed the cancel."""
        if self._cancelled:
            return
        self._cancelled = True
        self._photos.clear()
        self._jobs.put(None)

    def _work(self):
        while True:
            job = self._jobs.get()
            if job is None or self._cancelled:
                return
            iid, provider = job
            image: ty.Optional[PIL.Image.Image] = None
            try:
                frames = provider()
                if frames:
                    image = filmstrip_image(frames, self._height)
            except Exception as ex:  # noqa: BLE001 - a bad frame must not kill the worker.
                logger.debug(f"failed to generate thumbnail for {iid}: {ex}")
            self._results.put((iid, image))

    def _apply_to_tree(self, iid: str, photo: PIL.ImageTk.PhotoImage) -> bool:
        """Default `apply_image`: set the image on a `ttk.Treeview` row, skipping rows that
        have since been deleted."""
        tree = ty.cast(ttk.Treeview, self._widget)
        if not tree.exists(iid):
            return False
        tree.item(iid, image=photo)
        return True

    def _drain(self):
        if self._cancelled or not self._widget.winfo_exists():
            self._poller_active = False
            return
        try:
            while True:
                iid, image = self._results.get_nowait()
                self._pending -= 1
                if image is not None:
                    photo = to_photo(image)
                    if self._apply_image(iid, photo):
                        self._photos[iid] = photo
        except queue.Empty:
            pass
        if self._pending > 0:
            self._widget.after(self._poll_interval_ms, self._drain)
        else:
            self._poller_active = False
