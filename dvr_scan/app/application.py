#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2014-2024 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#

import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.scrolledtext
from logging import getLogger

from dvr_scan.app.common import register_icon

WINDOW_TITLE = "DVR-Scan"

logger = getLogger("dvr_scan")


class Application:
    def __init__(self):
        self._root = tk.Tk()

    def run(self):
        # Withdraw root window until we're done adding everything to avoid visual flicker.
        self._root.withdraw()
        self._root.option_add("*tearOff", False)
        self._root.title(WINDOW_TITLE)
        register_icon(self._root)
        self._root.resizable(True, True)
        self._root.minsize(width=320, height=240)
        tk.Label(self._root, text="testing").grid(row=0, column=0)
        tk.Label(self._root, text="testing").grid(row=1, column=0)
        tk.Label(self._root, text="testing").grid(row=0, column=1)
        tk.Label(self._root, text="testing").grid(row=1, column=1)

        logger.debug("starting main loop")
        self._root.deiconify()
        self._root.focus()
        self._root.grab_release()
        self._root.mainloop()
