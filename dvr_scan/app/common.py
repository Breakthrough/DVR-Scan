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

import importlib.resources as resources
import os
import tkinter as tk
import tkinter.ttk as ttk
import typing as ty
import webbrowser

import PIL
import PIL.Image
import PIL.ImageTk

import dvr_scan
from dvr_scan.app.about_window import show_about
from dvr_scan.app.startup import ADVANCED, WIZARD
from dvr_scan.platform import log_folder, open_path

PADDING = 8
SETTING_INPUT_WIDTH = 12
MAX_THRESHOLD = 255.0

HELP_GUIDE_URL = "www.dvr-scan.com/guide"
DISCORD_URL = "https://discord.gg/69kf6f2Exb"

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


def fit_window_to_screen(
    window: ty.Union[tk.Tk, tk.Toplevel], margin_x: int = 40, margin_y: int = 120
) -> bool:
    """Shrink `window`'s initial size so it fits on screen when the size its contents request
    is larger (e.g. the Advanced Mode window's thumbnail list on a small laptop display). Resizable
    content with a grid weight absorbs the difference. The margins leave room for window
    decorations and the taskbar, which Tk cannot query portably. Returns True if the window
    geometry was changed."""
    window.update_idletasks()
    req_width, req_height = window.winfo_reqwidth(), window.winfo_reqheight()
    max_width = max(window.winfo_screenwidth() - margin_x, 1)
    max_height = max(window.winfo_screenheight() - margin_y, 1)
    if req_width <= max_width and req_height <= max_height:
        return False
    window.geometry(f"{min(req_width, max_width)}x{min(req_height, max_height)}")
    return True


def add_startup_mode_menu(
    parent: tk.Menu, variable: tk.StringVar, command: ty.Callable[[], None]
) -> tk.Menu:
    """Add a `Startup Mode` cascade to `parent` with Scan Wizard / Advanced Mode radio
    buttons bound to `variable` ("wizard" or "advanced"). `command` runs after each
    selection. Shared by the Advanced Mode window and the Scan Wizard so both menus stay
    in sync."""
    menu = tk.Menu(parent, tearoff=0)
    menu.add_radiobutton(
        label="Scan Wizard", underline=5, variable=variable, value=WIZARD, command=command
    )
    menu.add_radiobutton(
        label="Advanced Mode", underline=0, variable=variable, value=ADVANCED, command=command
    )
    # Underline "M": "S" collides with Start Scan / Sort in the File menus.
    parent.add_cascade(label="Startup Mode", underline=8, menu=menu)
    return menu


def fill_help_menu(menu: tk.Menu, root: tk.Misc):
    """Append the Help entries shared by every window (guide, Discord, logs, About) to
    `menu`. `root` is the window the About dialog is shown over."""
    menu.add_command(
        label="Help Guide", underline=0, command=lambda: webbrowser.open_new_tab(HELP_GUIDE_URL)
    )
    menu.add_command(
        label="Discord", underline=0, command=lambda: webbrowser.open_new_tab(DISCORD_URL)
    )
    menu.add_separator()
    menu.add_command(label="Open Logs", underline=5, command=lambda: open_path(log_folder()))
    menu.add_command(label="About DVR-Scan", underline=0, command=lambda: show_about(root))


def show_modal(window: tk.Toplevel, parent: tk.Misc):
    """Show `window` as a modal dialog over `parent` (the grab blocks input to other
    windows until `hide_modal`). Returns immediately: `wait_window` only returns once the
    window is destroyed, so waiting here would leave a nested event loop running for each
    time a reusable dialog is opened."""
    window.transient(parent)
    window.deiconify()
    window.focus()
    window.grab_set()


def hide_modal(window: tk.Toplevel, focus: tk.Misc):
    """Hide a dialog shown with `show_modal` (keeping it for reuse), returning focus to
    `focus`."""
    window.withdraw()
    window.grab_release()
    focus.focus()


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
