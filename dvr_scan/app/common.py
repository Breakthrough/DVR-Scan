#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2024 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visi

import importlib.resources as resources
import os
import tkinter as tk
import tkinter.ttk as ttk
import typing as ty

import PIL
import PIL.Image
import PIL.ImageTk

import dvr_scan

# Hover-darken factor for menubar headings: multiply each RGB channel of the bar background
# to derive the `activebackground`. Below 1.0 darkens; ~0.85 reads clearly but stays subtle.
_MENUBAR_HOVER_FACTOR = 0.85


def register_icon(root: tk.Tk):
    # On Windows we always want a path so we can load the .ICO with `iconbitmap`.
    # On other systems, we can just use the PNG logo directly with `iconphoto`.
    if os.name == "nt":
        icon_path = resources.files(dvr_scan).joinpath("dvr-scan.ico")
        with resources.as_file(icon_path) as icon_path:
            root.iconbitmap(default=icon_path)
        return
    icon = PIL.Image.open(resources.open_binary(dvr_scan, "dvr-scan.png"))
    root.iconphoto(True, PIL.ImageTk.PhotoImage(icon))


def _darken(widget: tk.Widget, color: str, factor: float = _MENUBAR_HOVER_FACTOR) -> str:
    """Return `color` darkened by `factor` (per channel), as a #rrggbb string. Used to
    derive a hover background from the bar's base background."""
    red, green, blue = (int((channel // 256) * factor) for channel in widget.winfo_rgb(color))
    return f"#{red:02x}{green:02x}{blue:02x}"


class MenuBar:
    """A custom menubar built from `tk.Menubutton` headings so the top-level menus get a
    real hover highlight. The native Windows menubar (`toplevel["menu"] = ...`) exposes no
    styling hooks, so its hover is invisibly flat on Windows 11; a row of menubuttons lets
    us set `activebackground` for a clear highlight.

    Drop-in replacement for the native menubar: grid `.frame` as the window's top row, then
    populate the `tk.Menu` returned by `add_menu()` exactly like a native cascade menu
    (`add_command`, `add_separator`, `entryconfigure`, ...).

    On non-Windows platforms the native menubar is kept (macOS expects the global menu bar):
    `add_menu()` returns a real cascade menu and `.frame` is None, so call sites stay
    identical apart from gridding `.frame` only when it exists."""

    def __init__(self, master: tk.Misc):
        self._native: ty.Optional[tk.Menu] = None
        self.frame: ty.Optional[tk.Frame] = None
        self._background = ""
        self._hover = ""
        if os.name != "nt":
            self._native = tk.Menu(master)
            master["menu"] = self._native
            return
        self._background = ttk.Style().lookup("TFrame", "background") or "SystemButtonFace"
        self.frame = tk.Frame(master, background=self._background)
        self._hover = _darken(self.frame, self._background)

    def add_menu(self, label: str, underline: ty.Optional[int] = None) -> tk.Menu:
        """Add a top-level heading and return its (empty) dropdown menu to populate."""
        if self._native is not None:
            menu = tk.Menu(self._native, tearoff=0)
            self._native.add_cascade(
                menu=menu, label=label, underline=underline if underline is not None else -1
            )
            return menu
        button = tk.Menubutton(
            self.frame,
            text=label,
            underline=underline if underline is not None else -1,
            relief=tk.FLAT,
            borderwidth=0,
            takefocus=False,
            background=self._background,
            activebackground=self._hover,
            padx=8,
            pady=2,
            direction="below",
        )
        # Drive the hover highlight explicitly rather than relying on the Menubutton's
        # built-in "active" state: that state desyncs when the window loses focus (e.g. when
        # the menu posts or on alt-tab), leaving the highlight stuck off. `activebackground`
        # is kept so the heading also stays lit while its dropdown is posted.
        button.bind("<Enter>", lambda _: button.configure(background=self._hover))
        button.bind("<Leave>", lambda _: button.configure(background=self._background))
        menu = tk.Menu(button, tearoff=0)
        button["menu"] = menu
        button.pack(side=tk.LEFT)
        return menu
