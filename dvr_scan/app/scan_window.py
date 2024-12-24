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

TITLE = "Scanning..."

logger = getLogger("dvr_scan")


class ScanWindow:
    def __init__(self, root: tk.Tk, on_destroyed: ty.Callable[[], None]):
        self._root = tk.Toplevel(master=root)
        self._root.withdraw()
        self._root.title(TITLE)
        self._root.resizable(True, True)
        self._root.minsize(320, 240)

        # Widgets
        self._scan_thread = threading.Thread(target=self._do_scan)
        self._stop_scan = threading.Event()
        self._paused = threading.Event()
        self._state_lock = threading.Lock()
        self._on_destroyed = on_destroyed

        self._progress = tk.IntVar(self._root, value=0)
        self._progress_bar = ttk.Progressbar(self._root, variable=self._progress, maximum=10)

        # Layout
        self._root.columnconfigure(0, weight=1)
        self._root.columnconfigure(1, weight=1)
        self._progress_bar.grid(sticky=tk.NSEW, row=0, columnspan=2)
        self._root.bind("<<ProgressUpdate>>", lambda _: self._on_progress())
        self._root.bind("<<ScanComplete>>", lambda _: self._on_complete())
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

    def _on_complete(self):
        logger.debug("scan completed")
        self._stop_button["state"] = tk.DISABLED
        self._close_button["state"] = tk.NORMAL

    def _destroy(self):
        self._root.after(10, self.stop)
        with self._state_lock:
            self._root.destroy()
            self._root = None
            self._on_destroyed()

    def prompt_stop(self):
        if self._stop_scan.is_set():
            return
        if messagebox.askyesno(
            title="Stop scan?",
            message="Are you sure you want to stop the current scan?",
            icon=messagebox.WARNING,
        ):
            self._destroy()

    def stop(self):
        if not self._stop_scan.is_set():
            self._stop_scan.set()
            self._scan_thread.join()

    def _on_progress(self):
        self._progress.set(self._progress.get() + 1)

    def show(self):
        logger.debug("starting scan thread showing scan window.")
        self._scan_thread.start()
        self._root.focus()
        self._root.grab_set()
        self._root.deiconify()
        self._root.wait_window()

    def _do_scan(self):
        complete = True
        for _ in range(10):
            if self._stop_scan.is_set():
                complete = False
                logger.debug("stop event set")
                break
            logger.debug("ping...")
            with self._state_lock:
                if self._root is None:
                    logger.debug("root was destroyed, bailing")
                    return
                self._root.event_generate("<<ProgressUpdate>>")
            time.sleep(0.3)
        logger.debug("scan complete" if complete else "scan NOT complete")
        self._root.event_generate("<<ScanComplete>>")
