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
"""DVR-Scan Region Editor handles detection region input and processing.

Regions are represented as a set of closed polygons defined by lists of points.

*NOTE*: The region editor is being transitioned to an offical GUI for DVR-Scan.
During this period, there may still be some keyboard/CLI interaction required to
run the program. Usability and accessibility bugs will be prioritized over feature
development.

The code in this module covers *all* the current UI logic, and consequently is not
well organized. This should be resolved as we develop the UI further and start to
better separate the CLI from the GUI. To facilitate this, a separate entry-point
for the GUI will be developed, and the region editor functionality will be deprecated.
"""

import os
import os.path
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.scrolledtext
import tkinter.ttk as ttk
import typing as ty
import webbrowser

import PIL
import PIL.Image
import PIL.ImageTk

import dvr_scan
from dvr_scan.app.common import SUPPORTS_RESOURCES
from dvr_scan.platform import get_system_version_info

if SUPPORTS_RESOURCES:
    import importlib.resources as resources

TITLE = "About DVR-Scan"
COPYRIGHT = (
    f"DVR-Scan {dvr_scan.__version__}\n\nCopyright © Brandon Castellano.\nAll rights reserved."
)


class AboutWindow:
    def __init__(self):
        self._version_info: ty.Optional[str] = None
        self._about_image: PIL.Image = None
        self._about_image_tk: PIL.ImageTk.PhotoImage = None

    def show(self, root: tk.Tk):
        window = tk.Toplevel(master=root)
        window.withdraw()
        window.title(TITLE)
        window.resizable(True, True)

        if SUPPORTS_RESOURCES:
            app_logo = PIL.Image.open(resources.open_binary(dvr_scan, "dvr-scan-logo.png"))
            self._about_image = app_logo.crop((8, 8, app_logo.width - 132, app_logo.height - 8))
            self._about_image_tk = PIL.ImageTk.PhotoImage(self._about_image)
            canvas = tk.Canvas(
                window, width=self._about_image.width, height=self._about_image.height
            )
            canvas.grid()
            canvas.create_image(0, 0, anchor=tk.NW, image=self._about_image_tk)

        ttk.Separator(window, orient=tk.HORIZONTAL).grid(row=1, sticky="ew", padx=16.0)
        ttk.Label(
            window,
            text=COPYRIGHT,
        ).grid(row=2, sticky="nw", padx=24.0, pady=24.0)

        # TODO: These should be buttons not labels.
        website_link = ttk.Label(
            window, text="www.dvr-scan.com", cursor="hand2", foreground="medium blue"
        )
        website_link.grid(row=2, sticky="ne", padx=24.0, pady=24.0)
        website_link.bind("<Button-1>", lambda _: webbrowser.open_new_tab("www.dvr-scan.com"))

        about_tabs = ttk.Notebook(window)
        version_tab = ttk.Frame(about_tabs)
        version_area = tkinter.scrolledtext.ScrolledText(
            version_tab, wrap=tk.NONE, width=40, height=1
        )
        # TODO: See if we can add another button that will copy debug logs.
        if not self._version_info:
            self._version_info = get_system_version_info()
        version_area.insert(tk.INSERT, self._version_info)
        version_area.grid(sticky="nsew")
        version_area.config(state="disabled")
        version_tab.columnconfigure(0, weight=1)
        version_tab.rowconfigure(0, weight=1)
        tk.Button(
            version_tab,
            text="Copy to Clipboard",
            command=lambda: root.clipboard_append(self._version_info),
        ).grid(row=1, column=0)

        license_tab = ttk.Frame(about_tabs)
        scrollbar = tk.Scrollbar(license_tab, orient=tk.HORIZONTAL)
        license_area = tkinter.scrolledtext.ScrolledText(
            license_tab, wrap=tk.NONE, width=40, xscrollcommand=scrollbar.set, height=1
        )
        license_area.insert(tk.INSERT, dvr_scan.get_license_info())
        license_area.grid(sticky="nsew")
        scrollbar.config(command=license_area.xview)
        scrollbar.grid(row=1, sticky="swe")
        license_area.config(state="disabled")
        license_tab.columnconfigure(0, weight=1)
        license_tab.rowconfigure(0, weight=1)

        # TODO: Add tab that has some useful links like submitting bug report, etc
        about_tabs.add(version_tab, text="Version Info")
        about_tabs.add(license_tab, text="License Info")

        about_tabs.grid(
            row=0, column=1, rowspan=4, padx=(0.0, 16.0), pady=(16.0, 16.0), sticky="nsew"
        )
        window.update()
        if self._about_image is not None:
            window.columnconfigure(0, minsize=self._about_image.width)
            window.rowconfigure(0, minsize=self._about_image.height)
        else:
            window.columnconfigure(0, minsize=200)
            window.rowconfigure(0, minsize=100)
        # minsize includes padding
        window.columnconfigure(1, weight=1, minsize=100)
        window.rowconfigure(3, weight=1)

        window.minsize(width=window.winfo_reqwidth(), height=window.winfo_reqheight())
        # can we query widget height?

        root.grab_release()
        if os == "nt":
            root.attributes("-disabled", True)

        window.transient(root)
        window.focus()
        window.grab_set()

        def dismiss():
            window.grab_release()
            window.destroy()
            if os == "nt":
                root.attributes("-disabled", False)
            root.grab_set()
            root.focus()

        window.protocol("WM_DELETE_WINDOW", dismiss)
        window.attributes("-topmost", True)
        window.bind("<Escape>", lambda _: window.destroy())
        window.bind("<Destroy>", lambda _: dismiss())

        window.deiconify()
        window.wait_window()
