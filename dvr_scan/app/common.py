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

import ctypes
import importlib.resources as resources
import os
import time
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
_MENUBAR_POLL_MS = 25
_MENUBAR_REOPEN_GUARD_SEC = 0.08


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
    (`add_command`, `add_separator`, `entryconfigure`, ...). Underlined mnemonics (`Alt+F`,
    `Alt+H`, ...) and `F10` are bound on the owning window so the custom bar stays
    reachable by keyboard. While any top-level menu is posted on Windows (which runs inside
    Win32's modal `TrackPopupMenu` loop and blocks normal `<Enter>` events on sibling
    widgets), a short `after` poll tracks the pointer so hovering another heading switches
    the open menu like a native menu bar.

    On non-Windows platforms the native menubar is kept (macOS expects the global menu bar):
    `add_menu()` returns a real cascade menu and `.frame` is None, so call sites stay
    identical apart from gridding `.frame` only when it exists."""

    def __init__(self, master: tk.Misc):
        self._master = master
        self._native: ty.Optional[tk.Menu] = None
        self.frame: ty.Optional[tk.Frame] = None
        self._background = ""
        self._hover = ""
        self._menus: ty.List[ty.Tuple[tk.Menubutton, tk.Menu]] = []
        self._posted_button: ty.Optional[tk.Menubutton] = None
        self._pending_switch: ty.Optional[ty.Tuple[tk.Menubutton, tk.Menu]] = None
        self._poll_id: ty.Optional[str] = None
        self._last_unpost: ty.Tuple[ty.Optional[tk.Menubutton], float] = (None, 0.0)
        if os.name != "nt":
            self._native = tk.Menu(master)
            master["menu"] = self._native
            return
        self._background = ttk.Style().lookup("TFrame", "background") or "SystemButtonFace"
        self.frame = tk.Frame(master, background=self._background)
        self.frame.bind("<Destroy>", self._cancel_hover_poll, add="+")
        self._hover = _darken(self.frame, self._background)
        toplevel = master.winfo_toplevel()
        toplevel.bind("<F10>", lambda _: self._post_index(0, select_first=True), add="+")

    def _can_post(self) -> bool:
        toplevel = self._master.winfo_toplevel()
        if not toplevel.winfo_exists() or not toplevel.winfo_viewable():
            return False
        grab = toplevel.grab_current()
        return grab is None or grab == toplevel

    def _button_at_pointer(self) -> ty.Tuple[ty.Optional[tk.Menubutton], ty.Optional[tk.Menu]]:
        if self.frame is None or not self.frame.winfo_exists():
            return None, None
        px, py = self.frame.winfo_pointerxy()
        for button, menu in self._menus:
            if not button.winfo_exists() or str(button["state"]) == "disabled":
                continue
            bx, by = button.winfo_rootx(), button.winfo_rooty()
            bw, bh = button.winfo_width(), button.winfo_height()
            if bx <= px < bx + bw and by <= py < by + bh:
                return button, menu
        return None, None

    def _sync_backgrounds(self):
        if self.frame is None or not self.frame.winfo_exists():
            return
        hovered, _ = self._button_at_pointer()
        for button, _ in self._menus:
            if not button.winfo_exists():
                continue
            active = button is self._posted_button or (
                self._posted_button is None and button is hovered
            )
            button.configure(background=self._hover if active else self._background)

    def _on_button_enter(self, button: tk.Menubutton):
        if self._posted_button is None and button.winfo_exists():
            button.configure(background=self._hover)

    def _on_button_leave(self, button: tk.Menubutton):
        if self._posted_button is None and button.winfo_exists():
            button.configure(background=self._background)

    def _dismiss_active_menu(self):
        if os.name == "nt":
            ctypes.windll.user32.EndMenu()

    def _cancel_hover_poll(self, _event=None):
        if self._poll_id is not None and self.frame is not None:
            try:
                self.frame.after_cancel(self._poll_id)
            except tk.TclError:
                pass
        self._poll_id = None

    def _poll_hover(self):
        self._poll_id = None
        if self._posted_button is None or self.frame is None or not self.frame.winfo_exists():
            return
        target_btn, target_menu = self._button_at_pointer()
        if target_btn is not None and target_btn is not self._posted_button:
            self._pending_switch = (target_btn, target_menu)
            self._dismiss_active_menu()
            return
        self._poll_id = self.frame.after(_MENUBAR_POLL_MS, self._poll_hover)

    def _on_button_press(self, button: tk.Menubutton, menu: tk.Menu) -> str:
        # Clicking an open heading closes Win32 `TrackPopupMenu` first and then delivers
        # `<Button-1>` to the heading; skip re-posting so a second click toggles it closed.
        last_btn, last_time = self._last_unpost
        if button is last_btn and (time.monotonic() - last_time) < _MENUBAR_REOPEN_GUARD_SEC:
            self._last_unpost = (None, 0.0)
            return "break"
        self._post_button_menu(button, menu)
        return "break"

    def _post_button_menu(
        self, button: tk.Menubutton, menu: tk.Menu, select_first: bool = False
    ) -> ty.Optional[str]:
        if not self._can_post() or str(button["state"]) == "disabled":
            return None
        current_btn: ty.Optional[tk.Menubutton] = button
        current_menu = menu
        first = select_first
        while current_btn is not None:
            self._pending_switch = None
            self._posted_button = current_btn
            self._sync_backgrounds()
            self._cancel_hover_poll()
            if self.frame is not None:
                self._poll_id = self.frame.after(_MENUBAR_POLL_MS, self._poll_hover)
            x = current_btn.winfo_rootx()
            y = current_btn.winfo_rooty() + current_btn.winfo_height()
            entry = 0 if (first and current_menu.index(tk.END) is not None) else ""
            current_menu.tk.call("tk_popup", current_menu._w, x, y, entry)
            self._cancel_hover_poll()
            self._posted_button = None
            if self.frame is None or not self.frame.winfo_exists():
                return "break"
            if self._pending_switch is not None and self._can_post():
                current_btn, current_menu = self._pending_switch
                self._pending_switch = None
                first = False
                continue
            self._pending_switch = None
            self._last_unpost = (current_btn, time.monotonic())
            current_btn = None
        self._sync_backgrounds()
        return "break"

    def _post_index(self, index: int, select_first: bool = False) -> ty.Optional[str]:
        if 0 <= index < len(self._menus):
            button, menu = self._menus[index]
            return self._post_button_menu(button, menu, select_first=select_first)
        return None

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
        menu = tk.Menu(button, tearoff=0)
        button["menu"] = menu
        # Handle posting and hover highlight explicitly: Tk's built-in Menubutton bindings
        # desync hover state on focus loss and cannot switch headings on hover while Win32's
        # modal popup loop is running.
        button.bind("<Button-1>", lambda _, b=button, m=menu: self._on_button_press(b, m))
        button.bind("<ButtonRelease-1>", lambda _: "break")
        button.bind("<B1-Motion>", lambda _: "break")
        button.bind("<Enter>", lambda _, b=button: self._on_button_enter(b))
        button.bind("<Leave>", lambda _, b=button: self._on_button_leave(b))
        button.pack(side=tk.LEFT)
        self._menus.append((button, menu))
        if underline is not None and 0 <= underline < len(label):
            char = label[underline]
            if char.isalpha():
                toplevel = self._master.winfo_toplevel()
                for seq in (f"<Alt-{char.lower()}>", f"<Alt-{char.upper()}>"):
                    toplevel.bind(
                        seq,
                        lambda _, b=button, m=menu: self._post_button_menu(b, m, select_first=True),
                        add="+",
                    )
        return menu
