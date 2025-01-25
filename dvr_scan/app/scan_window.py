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
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
import typing as ty
from logging import getLogger

from tqdm import tqdm

from dvr_scan.shared import ScanSettings, init_scanner

TITLE = "Scanning..."

logger = getLogger("dvr_scan")

UI_UPDATE_RATE_MS = 50
STATS_UPDATE_RATE_NS = 250 * (1000 * 1000)


class ScanWindow:
    def __init__(
        self, root: tk.Tk, settings: ScanSettings, on_destroyed: ty.Callable[[], None], padding: int
    ):
        self._root = tk.Toplevel(master=root)
        self._root.withdraw()
        self._root.title(TITLE)
        self._root.resizable(True, True)
        self._scanner = init_scanner(settings)
        self._scanner.set_callbacks(
            scan_started=self._on_scan_started,
            processed_frame=self._on_processed_frame,
        )

        self._root.bind("<<Shutdown>>", self.stop)
        self._root.protocol("WM_DELETE_WINDOW", self.prompt_stop)

        # Widgets
        self._scan_thread = threading.Thread(target=self._do_scan)
        self._state_lock = threading.Lock()
        self._on_destroyed = on_destroyed

        self._progress = tk.IntVar(self._root, value=0)
        self._progress_bar = ttk.Progressbar(self._root, variable=self._progress, maximum=10)
        self._elapsed_label = tk.Label(self._root)
        self._remaining_label = tk.Label(self._root)
        self._stop_button = tk.Button(self._root, text="Stop", command=self.prompt_stop)
        self._close_button = tk.Button(
            self._root, text="Close", command=self._destroy, state=tk.DISABLED
        )
        self._events_label = tk.Label(self._root)
        self._processed_label = tk.Label(self._root)
        self._speed_label = tk.Label(self._root)
        self._total_label = tk.Label(self._root)

        # Layout
        width = self._root.winfo_reqwidth()
        self._root.columnconfigure(0, weight=1, minsize=width / 2)
        self._root.columnconfigure(1, weight=1, minsize=width / 2)
        self._root.rowconfigure(0, weight=1)
        self._root.rowconfigure(1, weight=1)
        self._root.rowconfigure(2, weight=1)
        self._root.rowconfigure(3, weight=32)
        self._root.rowconfigure(4, weight=1)
        self._root.rowconfigure(5, weight=1)
        self._root.rowconfigure(6, weight=1)
        self._root.rowconfigure(7, weight=2)
        self._root.minsize(
            width=2 * self._root.winfo_reqwidth(), height=self._root.winfo_reqheight()
        )

        self._events_label.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW, pady=(padding, 0))
        self._progress_bar.grid(sticky=tk.NSEW, row=1, columnspan=2, pady=padding, padx=padding)
        self._elapsed_label.grid(row=5, column=1, sticky=tk.NE, padx=padding)
        self._remaining_label.grid(row=2, column=0, columnspan=2, sticky=tk.NSEW)
        self._processed_label.grid(row=4, column=0, sticky=tk.NW, padx=padding)
        self._total_label.grid(row=5, column=0, sticky=tk.NW, padx=padding)
        self._speed_label.grid(row=4, column=1, sticky=tk.NE, padx=padding)
        frame = tk.Frame(self._root)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        self._stop_button = tk.Button(frame, text="Stop", command=self.prompt_stop)
        self._close_button = tk.Button(
            frame, text="Close", command=self._destroy, state=tk.DISABLED
        )
        self._stop_button.grid(row=0, column=0, pady=padding, sticky=tk.NSEW, padx=padding)
        self._close_button.grid(row=0, column=1, pady=padding, sticky=tk.NSEW, padx=padding)
        frame.grid(row=7, column=0, columnspan=2, sticky=tk.NSEW)

        self._prompt_shown = False

        self._scan_started = threading.Event()
        self._scan_finished = threading.Event()
        self._expected_num_frames = 0
        self._num_events = 0
        self._frames_processed = 0
        self._elapsed = "00:00"
        self._remaining = "N/A"
        self._rate = "N/A"
        self._padding = padding
        self._last_stats_update_ns = time.time_ns()

    def _update(self):
        if self._scan_finished.is_set():
            logger.debug("scan completed")
            self._progress.set(self._expected_num_frames)
            self._elapsed_label["text"] = f"Elapsed: {self._elapsed}"
            self._remaining_label["text"] = "\n"
            self._stop_button["state"] = tk.DISABLED
            self._close_button["state"] = tk.NORMAL
            self._processed_label["text"] = f"Processed: {self._expected_num_frames} frames"
            self._speed_label["text"] = f"Rate: {self._rate} FPS"
            return False

        if self._scan_started.is_set():
            self._progress_bar = ttk.Progressbar(
                self._root,
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
        self._progress.set(self._frames_processed)
        self._events_label["text"] = f"Events Found: {self._num_events}"
        self._elapsed_label["text"] = f"Elapsed: {self._elapsed}"
        self._remaining_label["text"] = f"Time Remaining:\n{self._remaining}"
        self._processed_label["text"] = f"Processed: {self._frames_processed:4} frames"
        self._total_label["text"] = f"Total: {self._expected_num_frames} frames"
        self._speed_label["text"] = f"Rate: {self._rate} FPS"
        return True

    def _update_continuous(self):
        if self._update():
            self._root.after(UI_UPDATE_RATE_MS, self._update_continuous)

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
        if self._scanner.is_stopped():
            return
        if messagebox.askyesno(
            title="Stop scan?",
            message="Are you sure you want to stop the current scan?",
            icon=messagebox.WARNING,
            parent=self._root,
        ):
            self._destroy()

    def stop(self):
        if not self._scanner.is_stopped():
            logger.debug("stopping scan thread")
            self._scanner.stop()
            self._scan_thread.join()

    def show(self):
        logger.debug("starting scan thread showing scan window.")
        self._scan_thread.start()
        self._root.deiconify()
        self._root.focus()
        self._root.grab_set()
        self._root.after(10, self._update_continuous)
        self._root.wait_window()

    def _on_scan_started(self, num_frames: int):
        # We only get the number of frames as an event and not synchronously since we try to do as
        # much work in the worker thread as possible, including seeking to the start time.
        self._expected_num_frames = num_frames
        self._scan_started.set()

    def _on_processed_frame(self, progress_bar: tqdm, num_events: int):
        self._num_events = num_events
        self._frames_processed += 1

        curr = time.time_ns()

        if (curr - self._last_stats_update_ns) > STATS_UPDATE_RATE_NS:
            self._last_stats_update_ns = curr
            format_dict = progress_bar.format_dict
            format_dict.update(bar_format="{elapsed} {remaining} {rate_fmt}")
            values = tqdm.format_meter(**format_dict).split(" ")
            # TODO: Why do we sometimes not get enough values here? The format above should always
            # print a string similar to "NN:NN NN:NN NN.NN frames/s"
            if len(values) >= 4:
                (self._elapsed, self._remaining, self._rate, *_) = values

    def _do_scan(self):
        self._scanner.scan()
        self._scan_finished.set()
        # TODO: We need to add a hook to be called before we destroy the progress bar so we can also
        # extract the final values. We also need to verify that the scan completed or if it was
        # stopped early, or if an error occurs.
        # TODO: Figure out how to open the output directory when scanning is complete.
