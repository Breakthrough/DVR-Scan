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
"""About dialog, shared by the Help menu of every window."""

import importlib.resources as resources
import tkinter as tk
import tkinter.scrolledtext
import tkinter.ttk as ttk
import webbrowser

import PIL
import PIL.Image
import PIL.ImageTk

import dvr_scan
from dvr_scan.platform import get_system_version_info

TITLE = "About DVR-Scan"
COPYRIGHT = (
    f"DVR-Scan {dvr_scan.__version__}\n\n"
    "Copyright \N{COPYRIGHT SIGN} Brandon Castellano.\nAll rights reserved."
)
WEBSITE_URL = "https://www.dvr-scan.com/"
ISSUES_URL = "https://github.com/Breakthrough/DVR-Scan/issues"


def _allow_tab_traversal(text_widget: tk.Text):
    """Let Tab / Shift+Tab move focus out of a read-only Text widget instead of trapping focus."""

    def focus_next(event):
        target = event.widget.tk_focusNext()
        if target is not None:
            target.focus_set()
        return "break"

    def focus_prev(event):
        target = event.widget.tk_focusPrev()
        if target is not None:
            target.focus_set()
        return "break"

    text_widget.bind("<Tab>", focus_next)
    text_widget.bind("<Shift-Tab>", focus_prev)


def show_about(root: tk.Misc):
    """Show the About dialog as a modal over `root`, blocking until it is closed."""
    window = tk.Toplevel(master=root)
    window.withdraw()
    window.title(TITLE)
    window.resizable(True, True)

    app_logo = PIL.Image.open(resources.open_binary(dvr_scan, "dvr-scan-logo.png"))
    about_image = app_logo.crop((8, 8, app_logo.width - 132, app_logo.height - 8))
    # Tk keeps no reference of its own, so this local must outlive the window (it does: the
    # function blocks in `wait_window` below).
    about_image_tk = PIL.ImageTk.PhotoImage(about_image)
    bg = ttk.Style().lookup("TFrame", "background") or "SystemButtonFace"
    canvas = tk.Canvas(
        window,
        width=about_image.width,
        height=about_image.height,
        background=bg,
        highlightthickness=0,
    )
    canvas.grid(row=0, column=0, padx=8, pady=(8, 0))
    canvas.create_image(0, 0, anchor=tk.NW, image=about_image_tk)

    ttk.Separator(window, orient=tk.HORIZONTAL).grid(row=1, column=0, sticky="ew", padx=16.0)
    ttk.Label(window, text=COPYRIGHT).grid(
        row=2, column=0, sticky="nw", padx=24.0, pady=(16.0, 8.0)
    )

    links_frame = ttk.Frame(window)
    links_frame.grid(row=3, column=0, sticky="new", padx=24.0, pady=(0.0, 16.0))
    ttk.Button(
        links_frame,
        text="Website",
        command=lambda: webbrowser.open_new_tab(WEBSITE_URL),
    ).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(
        links_frame,
        text="Report Issue",
        command=lambda: webbrowser.open_new_tab(ISSUES_URL),
    ).grid(row=0, column=1)

    version_info = get_system_version_info()
    about_tabs = ttk.Notebook(window)
    version_tab = ttk.Frame(about_tabs, padding=8)
    version_area = tkinter.scrolledtext.ScrolledText(version_tab, wrap=tk.NONE, width=40, height=1)
    version_area.insert(tk.INSERT, version_info)
    version_area.grid(row=0, column=0, sticky="nsew")
    version_area.config(state="disabled")
    _allow_tab_traversal(version_area)
    version_tab.columnconfigure(0, weight=1)
    version_tab.rowconfigure(0, weight=1)

    def copy_version_info():
        root.clipboard_clear()
        root.clipboard_append(version_info)
        root.update_idletasks()
        copy_button.configure(text="Copied!")
        window.after(
            1500,
            lambda: (
                copy_button.configure(text="Copy to Clipboard")
                if copy_button.winfo_exists()
                else None
            ),
        )

    copy_button = ttk.Button(
        version_tab,
        text="Copy to Clipboard",
        command=copy_version_info,
    )
    copy_button.grid(row=1, column=0, sticky="e", pady=(8, 0))

    license_tab = ttk.Frame(about_tabs, padding=8)
    scrollbar = ttk.Scrollbar(license_tab, orient=tk.HORIZONTAL)
    license_area = tkinter.scrolledtext.ScrolledText(
        license_tab, wrap=tk.NONE, width=40, xscrollcommand=scrollbar.set, height=1
    )
    license_area.insert(tk.INSERT, dvr_scan.get_license_info())
    license_area.grid(row=0, column=0, sticky="nsew")
    scrollbar.config(command=license_area.xview)
    scrollbar.grid(row=1, column=0, sticky="swe")
    license_area.config(state="disabled")
    _allow_tab_traversal(license_area)
    license_tab.columnconfigure(0, weight=1)
    license_tab.rowconfigure(0, weight=1)

    about_tabs.add(version_tab, text="Version Info")
    about_tabs.add(license_tab, text="License Info")
    about_tabs.grid(row=0, column=1, rowspan=4, padx=(8.0, 16.0), pady=(16.0, 8.0), sticky="nsew")

    # The region editor holds a grab on its root while launched from the Advanced Mode window;
    # hand the grab to this dialog and give it back on close. (Tkinter maps Tk's "none"
    # grab status to None.)
    restore_grab = root.grab_status() is not None
    root.grab_release()
    window.transient(root)

    dismissed = False

    def dismiss():
        nonlocal dismissed
        if dismissed:
            return
        dismissed = True
        if window.winfo_exists():
            window.grab_release()
            window.destroy()
        if restore_grab and root.winfo_exists():
            root.grab_set()
        if root.winfo_exists():
            root.focus()

    close_button = ttk.Button(window, text="Close", command=dismiss)
    close_button.grid(row=4, column=0, columnspan=2, sticky="e", padx=16.0, pady=(0.0, 16.0))

    window.update_idletasks()
    window.columnconfigure(0, minsize=about_image.width)
    window.rowconfigure(0, minsize=about_image.height)
    # minsize includes padding
    window.columnconfigure(1, weight=1, minsize=100)
    window.rowconfigure(3, weight=1)
    window.minsize(width=window.winfo_reqwidth(), height=window.winfo_reqheight())

    window.protocol("WM_DELETE_WINDOW", dismiss)
    window.bind("<Escape>", lambda _: dismiss())

    window.deiconify()
    close_button.focus_set()
    window.grab_set()
    window.wait_window()
