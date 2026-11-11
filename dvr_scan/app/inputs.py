#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2024 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""Input video metadata and file helpers shared by both advanced mode and wizard."""

import dataclasses
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import typing as ty
from datetime import datetime
from logging import getLogger
from pathlib import Path

from scenedetect import FrameTimecode, VideoOpenFailure, open_video

from dvr_scan.app.thumbnails import FILMSTRIP_FRAMES

logger = getLogger("dvr_scan")

# TODO: More extensions.
VIDEO_FILETYPES = [("Video", "*.mp4"), ("Video", "*.avi"), ("Other", "*")]


@dataclasses.dataclass
class VideoInfo:
    """Display metadata for one input video. Strings are pre-formatted for direct display."""

    path: str
    name: str
    duration: str
    framerate: str
    resolution: str
    date: str


def parse_resolution(text: str) -> ty.Optional[ty.Tuple[int, int]]:
    """Parse a `VideoInfo.resolution` string ("W x H") into (w, h), or None if invalid."""
    try:
        width, height = str(text).split("x")
        return (int(width), int(height))
    except ValueError:
        return None


def probe_video(path: str) -> ty.Optional[VideoInfo]:
    """Open `path` and extract display metadata (duration, framerate, resolution, creation
    date), returning a `VideoInfo` or None if the video could not be opened. Errors are
    logged by `open_video`; callers decide how to surface a failure to the user."""
    try:
        video = open_video(path, backend="opencv")  # logs errors on failure
    except VideoOpenFailure:
        return None
    try:
        # On Windows, ctime is creation time. On other systems, it may be the last
        # metadata change time.
        create_time = datetime.fromtimestamp(Path(path).stat().st_ctime)
        create_time_str = create_time.strftime("%Y-%m-%d %H:%M:%S")
    except OSError as ex:
        logger.debug(f"Failed to stat {path}: {ex}")
        create_time_str = "N/A"
    return VideoInfo(
        path=str(Path(video.path).absolute()),
        name=Path(video.path).name,
        duration=video.duration.get_timecode(),
        framerate=f"{float(video.frame_rate):g}",
        resolution=f"{video.frame_size[0]} x {video.frame_size[1]}",
        date=create_time_str,
    )


def sample_video_frames(path: str, count: int = FILMSTRIP_FRAMES) -> ty.Optional[list]:
    """Open `path` and decode `count` frames spread evenly across its duration, returning
    them as a list of BGR arrays (for a filmstrip preview), or None on failure. Runs on a
    `ThumbnailLoader` worker thread, so it must not touch Tk. The transient VideoStream is
    released by GC once sampling is done (a short-lived handle, not a retained one)."""
    try:
        video = open_video(path, backend="opencv")
    except VideoOpenFailure:
        return None
    total_frames = video.duration.frame_num
    frames = []
    for index in range(count):
        # Sample at evenly spaced midpoints; the last avoids the exact final frame, which
        # can fail to decode. For an unknown/zero-length duration, fall back to frame 0.
        if total_frames > 0:
            target = int(total_frames * (index + 0.5) / count)
            video.seek(FrameTimecode(target, video.frame_rate))
        frame = video.read()
        # VideoStream.read() returns False (not None) when no frame is available.
        if frame is not False:
            frames.append(frame)
        if total_frames <= 0:
            break
    return frames or None


def ask_video_paths(parent: ty.Optional[tk.Misc] = None) -> ty.List[str]:
    """Prompt for one or more video files, returning the chosen paths (empty if cancelled)."""
    options = {"title": "Open video(s)...", "filetypes": VIDEO_FILETYPES, "multiple": True}
    if parent is not None:
        options["parent"] = parent
    return list(tkinter.filedialog.askopenfilename(**options) or ())


def probe_videos(
    paths: ty.Iterable[str], parent: ty.Optional[tk.Misc] = None
) -> ty.List[VideoInfo]:
    """Probe each of `paths`, returning the metadata of those that could be opened. Missing
    files are logged, and a single warning dialog is shown if any path failed."""
    infos = []
    failed = False
    for path in paths:
        if not Path(path).exists():
            logger.error(f"File does not exist: {path}")
            failed = True
            continue
        info = probe_video(path)
        if info is None:
            failed = True
            continue
        infos.append(info)
    if failed:
        options = {"parent": parent} if parent is not None else {}
        tkinter.messagebox.showwarning(
            "Video Open Failure", "Failed to open one or more videos.", **options
        )
    return infos


def handle_drop(
    widget: tk.Misc,
    data: str,
    add_video: ty.Callable[[str], None],
    load_config: ty.Optional[ty.Callable[[str], bool]] = None,
):
    """Handle a `<<Drop>>` event's `data`: a Tcl list of paths (paths with spaces are
    wrapped in braces). Videos are passed to `add_video`. Config files are passed to
    `load_config` until one loads successfully: loading a config reinitializes the whole
    UI, so only one wins and the rest are ignored (as are all of them without
    `load_config`). Items that are not files are ignored."""
    config_loaded = False
    for path_str in widget.tk.splitlist(data):
        path = Path(path_str)
        if not path.is_file():
            logger.info(f"Ignoring dropped item (not a file): {path}")
        elif path.suffix.lower() != ".cfg":
            add_video(str(path))
        elif load_config is None or config_loaded:
            logger.warning(f"Ignoring dropped config file: {path}")
        else:
            config_loaded = load_config(str(path))
