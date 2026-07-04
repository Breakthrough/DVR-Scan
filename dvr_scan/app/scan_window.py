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

import threading
import time
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
import traceback
import typing as ty
from logging import getLogger
from pathlib import Path

from scenedetect import FrameTimecode
from tqdm import tqdm

from dvr_scan.app.thumbnails import (
    FILMSTRIP_FRAMES,
    FILMSTRIP_WIDTH,
    THUMBNAIL_STYLE,
    FrameProvider,
    ThumbnailLoader,
    configure_thumbnail_rows,
    filmstrip_placeholder,
    to_photo,
)
from dvr_scan.platform import open_path
from dvr_scan.report import TIMECODE_PRECISION, write_events_csv
from dvr_scan.scanner import DetectionResult, MotionEvent
from dvr_scan.shared import ScanSettings, init_scanner
from dvr_scan.video_joiner import BackendUnavailable, VideoJoiner

TITLE = "Scanning..."

logger = getLogger("dvr_scan")

UI_UPDATE_RATE_MS = 50
STATS_UPDATE_RATE_NS = 250 * (1000 * 1000)

# Keep the on-screen event table in sync with the saved CSV report's timecode precision.
EVENT_TABLE_PRECISION = TIMECODE_PRECISION
# Event table data columns: (column id, heading, width). The thumbnail occupies the
# tree (#0) column shown alongside these.
EVENT_TABLE_COLUMNS = (
    ("event", "Event", 80),
    ("start", "Start Time", 120),
    ("end", "End Time", 120),
    ("duration", "Duration", 120),
)
# Preview (#0) column wide enough for the filmstrip plus a little padding.
PREVIEW_COLUMN_WIDTH = FILMSTRIP_WIDTH + 12


def launch_scan(
    root: tk.Tk,
    settings: ScanSettings,
    on_closed: ty.Callable[[], None],
    padding: int,
) -> ty.Optional["ScanWindow"]:
    """Create a `ScanWindow` for `settings`. Shows an error message and returns None
    if the configured input mode is unavailable on this system. The caller must call
    `show()` on the returned window to start the scan."""
    try:
        return ScanWindow(root, settings, on_closed, padding)
    except BackendUnavailable:
        messagebox.showerror(
            title="Input Mode Unavailable",
            message=f"The specified input mode ({settings.get('input-mode')}) "
            "is not available on this system.",
        )
        return None


class ScanProgressView:
    """Progress display for a single scan, embeddable in any container. Owns the
    scanner, its worker thread, and the periodic UI update loop. The scan results
    (`result`, `error`, `was_stopped`) and summary stats are exposed once the scan
    finishes; the owner is notified via the `on_finished` callback, which always fires
    exactly once on the UI thread. Presentation of the result is the owner's job - this
    view shows no dialogs."""

    def __init__(
        self,
        parent: tk.Widget,
        settings: ScanSettings,
        on_finished: ty.Callable[[], None],
        padding: int,
    ):
        self.frame = ttk.Frame(parent)
        self._on_finished = on_finished
        self._finished_notified = False

        # Source paths, exposed so a results table can seek them for event thumbnails.
        self.input_paths: ty.List[str] = [str(path) for path in settings.get("input")]
        self._scanner = init_scanner(settings)
        self._scanner.set_callbacks(
            scan_started=self._on_scan_started,
            processed_frame=self._on_processed_frame,
        )
        self._open_on_completion = (
            settings.get("output-dir") if settings.get("open-output-dir") else None
        )
        self._scan_thread = threading.Thread(target=self._do_scan)

        # Scan outcome, populated by the worker thread before `_scan_finished` is set.
        self.result: ty.Optional[DetectionResult] = None
        self.error: ty.Optional[Exception] = None

        # Widgets
        self._progress = tk.IntVar(self.frame, value=0)
        self._progress_bar = ttk.Progressbar(self.frame, variable=self._progress, maximum=10)
        self._events_label = tk.Label(self.frame)
        self._elapsed_label = tk.Label(self.frame)
        self._remaining_label = tk.Label(self.frame)
        self._processed_label = tk.Label(self.frame)
        self._speed_label = tk.Label(self.frame)
        self._total_label = tk.Label(self.frame)

        # Layout
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)
        self.frame.rowconfigure(2, weight=1)
        self.frame.rowconfigure(3, weight=32)
        self.frame.rowconfigure(4, weight=1)
        self.frame.rowconfigure(5, weight=1)
        self._events_label.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW, pady=(padding, 0))
        self._progress_bar.grid(sticky=tk.NSEW, row=1, columnspan=2, pady=padding, padx=padding)
        self._remaining_label.grid(row=2, column=0, columnspan=2, sticky=tk.NSEW)
        self._processed_label.grid(row=4, column=0, sticky=tk.NW, padx=padding)
        self._speed_label.grid(row=4, column=1, sticky=tk.NE, padx=padding)
        self._total_label.grid(row=5, column=0, sticky=tk.NW, padx=padding)
        self._elapsed_label.grid(row=5, column=1, sticky=tk.NE, padx=padding)

        self._scan_started = threading.Event()
        self._scan_finished = threading.Event()
        self._start_time = 0.0
        self._last_stats_update_ns = 0
        self._expected_num_frames = 0
        self._padding = padding

        # Summary stats, also used to populate the owner's report.
        self.num_events = 0
        self.frames_processed = 0
        self.elapsed = "00:00"
        self.rate = "N/A"
        self._remaining = "N/A"

    @property
    def was_stopped(self) -> bool:
        return self._scanner.is_stopped()

    def start(self):
        """Begin scanning in a worker thread and start updating the UI."""
        logger.debug("starting scan thread")
        self._scan_thread.start()
        self.frame.after(10, self._update_continuous)

    def stop(self):
        """Signal the scan to stop and wait for the worker thread to exit."""
        if not self._scanner.is_stopped():
            logger.debug("stopping scan thread")
            self._scanner.stop()
            self._scan_thread.join()

    def _update(self) -> bool:
        """Refresh the progress UI. Returns True to keep updating, False once the scan
        has finished (after notifying the owner exactly once)."""
        if self._scan_finished.is_set():
            self._progress.set(self._expected_num_frames)
            self._elapsed_label["text"] = f"Elapsed: {self.elapsed}"
            self._remaining_label["text"] = "\n"
            self._processed_label["text"] = f"Processed: {self.frames_processed} frames"
            self._speed_label["text"] = f"Rate: {self.rate} FPS"
            if not self._finished_notified:
                self._finished_notified = True
                self._on_finished()
            return False

        if self._scan_started.is_set():
            self._progress_bar = ttk.Progressbar(
                self.frame,
                variable=self._progress,
                maximum=self._expected_num_frames,
            )
            self._progress_bar.grid(
                sticky=tk.NSEW,
                row=1,
                columnspan=2,
                padx=self._padding,
                pady=self._padding,
            )
            self._scan_started.clear()

        # Frames processed is updated from the worker thread, but we don't care about stale values.
        self._progress.set(self.frames_processed)
        self._events_label["text"] = f"Events Found: {self.num_events}"
        self._elapsed_label["text"] = f"Elapsed: {self.elapsed}"
        self._remaining_label["text"] = f"Time Remaining:\n{self._remaining}"
        self._processed_label["text"] = f"Processed: {self.frames_processed:4} frames"
        self._total_label["text"] = f"Total: {self._expected_num_frames} frames"
        self._speed_label["text"] = f"Rate: {self.rate} FPS"
        return True

    def _update_continuous(self):
        if self._update():
            self.frame.after(UI_UPDATE_RATE_MS, self._update_continuous)

    def _on_scan_started(self, num_frames: int):
        # We've now seeked to the start of the motion detection area and are processing frames.
        # We also have an *estimate* of how many frames we'll be processing.
        self._expected_num_frames = num_frames
        self._scan_started.set()
        # We set start time here to avoid including seek time in the overall FPS calculation.
        self._start_time = time.time()

    def _on_processed_frame(self, progress_bar: tqdm, num_events: int):
        self.num_events = num_events
        self.frames_processed += 1
        curr = time.time_ns()
        # Update internal state used for UI labels using the progress bar in the scanner.
        if (curr - self._last_stats_update_ns) > STATS_UPDATE_RATE_NS:
            self._last_stats_update_ns = curr
            format_dict = progress_bar.format_dict
            format_dict.update(bar_format="{elapsed} {remaining} {rate_fmt}")
            values = tqdm.format_meter(**format_dict).strip().split(" ")
            # We have to filter out empty entries after we split by spaces because the meter format
            # adds padding spaces to align numbers.
            values = list(filter(bool, values))
            if len(values) == 4:
                (self.elapsed, self._remaining, self.rate, _unit) = values

    def _do_scan(self):
        # We'll handle any errors in the main Tkinter thread via the on_finished callback.
        try:
            self.result = self._scanner.scan()
            if self.result is not None:
                self.frames_processed = self.result.num_frames
        except Exception as ex:  # noqa: BLE001
            self.error = ex
        finally:
            try:
                self._finalize_stats()
            finally:
                # Set last, and unconditionally, so the UI never polls forever even if
                # computing the final stats above raises.
                self._scan_finished.set()

    def _finalize_stats(self):
        """Compute final summary stats; runs once the scan thread is done."""
        elapsed = time.time() - self._start_time
        self.elapsed = (
            FrameTimecode(elapsed, 1000.0)
            .get_timecode(precision=0, use_rounding=True)
            .removeprefix("00:")
        )
        # TODO: This rate will always be a tiny bit slower than the one shown in stdout since we
        # use different timers. This can be fixed if we add a callback to the MotionScanner that
        # we can use to access the progress bar the scanner created.
        self.rate = (
            "%.2f" % (float(self.frames_processed) / elapsed) if self.frames_processed else "N/A"
        )
        # Open the output folder on a successful scan. On error, or if the user stopped the scan,
        # we don't open the window.
        if self._open_on_completion and not self._scanner.is_stopped() and self.error is None:
            logger.debug("scan complete, opening output folder")
            open_path(self._open_on_completion)


class ScanWindow:
    """Modal window that runs a scan from the classic (advanced) UI, showing progress
    and then a Stop/Close control. On a successful scan a report can be saved to disk."""

    def __init__(
        self, root: tk.Tk, settings: ScanSettings, on_destroyed: ty.Callable[[], None], padding: int
    ):
        self._root = tk.Toplevel(master=root)
        self._root.withdraw()
        self._root.title(TITLE)
        self._root.resizable(True, True)
        self._on_destroyed = on_destroyed
        self._padding = padding
        self._results_table: ty.Optional[ttk.Frame] = None
        self._view = ScanProgressView(self._root, settings, self._on_finished, padding)

        self._root.bind("<<Shutdown>>", self.stop)
        self._root.protocol("WM_DELETE_WINDOW", self.prompt_stop)

        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        self._view.frame.grid(row=0, column=0, sticky=tk.NSEW)

        buttons = tk.Frame(self._root)
        buttons.rowconfigure(0, weight=1)
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        buttons.columnconfigure(2, weight=1)
        self._stop_button = tk.Button(buttons, text="Stop", command=self.prompt_stop)
        self._save_button = tk.Button(
            buttons, text="Save Report...", command=self._on_save_report, state=tk.DISABLED
        )
        self._close_button = tk.Button(
            buttons, text="Close", command=self._destroy, state=tk.DISABLED
        )
        self._stop_button.grid(row=0, column=0, pady=padding, sticky=tk.NSEW, padx=padding)
        self._save_button.grid(row=0, column=1, pady=padding, sticky=tk.NSEW, padx=padding)
        self._close_button.grid(row=0, column=2, pady=padding, sticky=tk.NSEW, padx=padding)
        buttons.grid(row=1, column=0, sticky=tk.NSEW)

    def _on_finished(self):
        if self._view.error is not None:
            formatted_exception = "\n".join(traceback.format_exception(self._view.error))
            logger.critical(f"error during scan:\n{formatted_exception}")
            messagebox.showerror(
                "Scan Error",
                "Error during scanning. See log messages for more info."
                f"\nSummary: {self._view.error}",
                parent=self._root,
            )
            self._destroy()
            return
        logger.debug("scan complete")
        self._stop_button["state"] = tk.DISABLED
        self._close_button["state"] = tk.NORMAL
        # A report is only meaningful for a completed scan that produced an event list.
        if self._view.result is not None and not self._view.was_stopped:
            self._save_button["state"] = tk.NORMAL
            self._show_results(self._view.result.event_list)

    def _show_results(self, event_list: ty.List[MotionEvent]):
        """Swap the progress view for a table of detected events with thumbnails."""
        self._view.frame.grid_remove()
        table = build_event_table(self._root, self._view.input_paths, event_list)
        table.grid(row=0, column=0, sticky=tk.NSEW, padx=self._padding, pady=(self._padding, 0))
        self._results_table = table
        self._root.minsize(width=520, height=360)

    def _on_save_report(self):
        if self._view.result is None:
            return
        save_report(self._root, self._view.result.event_list)

    def _destroy(self):
        logger.info("Stopping current scan.")
        self._root.grab_release()
        self._root.destroy()
        self._on_destroyed()
        # TODO: If there's a long running task this could hang the GUI, see if we can schedule this
        # to occur in the parent.
        self.stop()
        logger.debug("root destroyed")

    def prompt_stop(self):
        if prompt_stop_scan(self._view, self._root):
            self._destroy()

    def stop(self, *_args):
        self._view.stop()

    def show(self):
        logger.debug("showing scan window")
        self._view.start()
        self._root.deiconify()
        self._root.focus()
        self._root.grab_set()
        self._root.wait_window()


def prompt_stop_scan(view: ScanProgressView, parent: tk.Misc) -> bool:
    """Ask the user to confirm stopping an in-progress scan. Returns True only if the
    user confirmed; a scan that is already stopped needs no action and returns False."""
    if view.was_stopped:
        return False
    return messagebox.askyesno(
        title="Stop scan?",
        message="Are you sure you want to stop the current scan?",
        icon=messagebox.WARNING,
        parent=parent,
    )


def _event_frame_providers(
    input_paths: ty.List[str], event_list: ty.List[MotionEvent]
) -> ty.List[FrameProvider]:
    """Build one frame provider per event, each sampling FILMSTRIP_FRAMES frames spread
    across the event for a filmstrip preview. All providers share a single `VideoJoiner`
    opened lazily on the worker thread; since `VideoJoiner.seek` is forward-only and the
    `ThumbnailLoader` runs providers in submission (ascending event) order, and frames
    within each event are sampled in ascending order, every seek moves forward - so this
    works for single- and multi-video inputs alike."""
    joiner: ty.Optional[VideoJoiner] = None

    def make(event: MotionEvent) -> FrameProvider:
        def provide():
            nonlocal joiner
            if joiner is None:
                joiner = VideoJoiner([Path(path) for path in input_paths], backend="opencv")
            start = event.start.get_frames()
            span = max(0, event.end.get_frames() - start)
            frames = []
            for index in range(FILMSTRIP_FRAMES):
                target = start + int(span * (index + 0.5) / FILMSTRIP_FRAMES)
                joiner.seek(FrameTimecode(target, joiner.framerate))
                frame = joiner.read()
                # VideoJoiner.read() yields the frame, or None once the stream is exhausted.
                if frame is not None:
                    frames.append(frame)
            return frames or None

        return provide

    return [make(event) for event in event_list]


def build_event_table(
    parent: tk.Widget, input_paths: ty.List[str], event_list: ty.List[MotionEvent]
) -> ttk.Frame:
    """A scrollable table of motion events, one row each, with a thumbnail (decoded off
    the UI thread from the source video) in the tree column. Shared by the wizard report
    panel and the classic `ScanWindow`."""
    configure_thumbnail_rows()
    container = ttk.Frame(parent)
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)

    table = ttk.Treeview(
        container,
        columns=[col for col, _, _ in EVENT_TABLE_COLUMNS],
        show="tree headings",
        style=THUMBNAIL_STYLE,
    )
    table.heading("#0", text="Preview")
    table.column(
        "#0",
        width=PREVIEW_COLUMN_WIDTH,
        minwidth=PREVIEW_COLUMN_WIDTH,
        stretch=False,
        anchor=tk.CENTER,
    )
    for col, heading, width in EVENT_TABLE_COLUMNS:
        table.heading(col, text=heading)
        table.column(col, width=width, anchor=tk.CENTER, stretch=True)

    placeholder = to_photo(filmstrip_placeholder())
    loader = ThumbnailLoader(table)
    # Keep the placeholder and loader (which owns the decoded PhotoImages) alive for as
    # long as the table is displayed; Tk only stores image names, not Python references.
    container.thumbnail_placeholder = placeholder
    container.thumbnail_loader = loader

    providers = _event_frame_providers(input_paths, event_list)
    for index, (event, provider) in enumerate(zip(event_list, providers, strict=True)):
        duration = event.end - event.start
        iid = table.insert(
            "",
            tk.END,
            image=placeholder,
            values=(
                index + 1,
                event.start.get_timecode(precision=EVENT_TABLE_PRECISION),
                event.end.get_timecode(precision=EVENT_TABLE_PRECISION),
                duration.get_timecode(precision=EVENT_TABLE_PRECISION),
            ),
        )
        loader.submit(iid, provider)

    scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=table.yview)
    table.configure(yscrollcommand=scroll.set)
    table.grid(row=0, column=0, sticky=tk.NSEW)
    scroll.grid(row=0, column=1, sticky=tk.NS)
    return container


def save_report(parent: tk.Misc, event_list: ty.List[MotionEvent]):
    """Prompt for a path and write `event_list` to a CSV report file."""
    save_path = tkinter.filedialog.asksaveasfilename(
        title="Save Report...",
        filetypes=[("CSV File", "*.csv")],
        defaultextension=".csv",
        confirmoverwrite=True,
        parent=parent,
    )
    if not save_path:
        return
    logger.debug(f"saving report to {save_path}")
    with open(save_path, "w", newline="") as file:
        write_events_csv(file, event_list)
