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
import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
import typing as ty
from logging import getLogger

from dvr_scan.shared import ScanSettings, init_scanner

TITLE = "Scanning..."

logger = getLogger("dvr_scan")


class ScanWindow:
    def __init__(self, root: tk.Tk, settings: ScanSettings, on_destroyed: ty.Callable[[], None]):
        self._root = tk.Toplevel(master=root)
        self._root.withdraw()
        self._root.title(TITLE)
        self._root.resizable(True, True)
        self._root.minsize(320, 240)
        self._scanner = init_scanner(settings)
        self._scanner.set_callbacks(
            scan_started=self._on_scan_started,
            processed_frame=self._on_processed_frame,
        )

        # Widgets
        self._scan_thread = threading.Thread(target=self._do_scan)
        self._state_lock = threading.Lock()
        self._on_destroyed = on_destroyed

        self._progress = tk.IntVar(self._root, value=0)
        self._progress_bar = ttk.Progressbar(self._root, variable=self._progress, maximum=10)

        # Layout
        self._root.columnconfigure(0, weight=1)
        self._root.columnconfigure(1, weight=1)
        self._progress_bar.grid(sticky=tk.NSEW, row=0, columnspan=2)
        self._root.minsize(width=self._root.winfo_reqwidth(), height=self._root.winfo_reqheight())

        self._root.bind("<<Shutdown>>", self.stop)
        self._root.protocol("WM_DELETE_WINDOW", self.prompt_stop)

        self._stop_button = tk.Button(self._root, text="Stop", command=self.prompt_stop)
        self._stop_button.grid(row=1, column=0)

        self._close_button = tk.Button(
            self._root, text="Close", command=self._destroy, state=tk.DISABLED
        )
        self._close_button.grid(row=1, column=1)

        self._prompt_shown = False

        self._scan_started = threading.Event()
        self._expected_num_frames = 0
        self._num_events = 0
        self._frames_processed = 0

    def _update(self):
        if self._scan_started.is_set():
            self._progress_bar = ttk.Progressbar(
                self._root, variable=self._progress, maximum=self._expected_num_frames
            )
            self._progress_bar.grid(sticky=tk.NSEW, row=0, columnspan=2)
            self._scan_started.clear()
        with self._state_lock:
            self._progress.set(self._frames_processed)
        self._root.after(100, self._update)

    def _on_complete(self):
        logger.debug("scan completed")
        self._stop_button["state"] = tk.DISABLED
        self._close_button["state"] = tk.NORMAL

    def _destroy(self):
        logger.debug("scheduling stop")
        with self._state_lock:
            logger.debug("destroying root")
            self._root.destroy()
            self._root = None
            self._on_destroyed()
        self.stop()
        logger.debug("root destroyed")

    def prompt_stop(self):
        if self._scanner.is_stopped():
            return
        if messagebox.askyesno(
            title="Stop scan?",
            message="Are you sure you want to stop the current scan?",
            icon=messagebox.WARNING,
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
        self._root.focus()
        self._root.grab_set()
        self._root.deiconify()
        self._root.after(10, self._update)
        self._root.wait_window()

    def _on_scan_started(self, num_frames: int):
        self._expected_num_frames = num_frames
        self._scan_started.set()

    def _on_processed_frame(self, num_events: int):
        # TODO: See if we can get the estimated time remaining from the tqdm progress bar.
        with self._state_lock:
            self._num_events = num_events
            self._frames_processed += 1

    def _do_scan(self):
        self._scanner.scan()
        # TODO: Handle scan completion.
