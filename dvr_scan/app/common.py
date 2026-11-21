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
# Dominant slate-blue from the DVR-Scan logo (`docs/assets/dvr-scan.svg` and `docs/style.css`).
BRAND_COLOR = "#59606d"

HELP_GUIDE_URL = "https://www.dvr-scan.com/guide"
DISCORD_URL = "https://discord.gg/69kf6f2Exb"

# Hover-darken factor for menubar headings: multiply each RGB channel of the bar background
# to derive the `activebackground`. Below 1.0 darkens; ~0.85 reads clearly but stays subtle.
_MENUBAR_HOVER_FACTOR = 0.85
_MENUBAR_POLL_MS = 25
_MENUBAR_REOPEN_GUARD_SEC = 0.08
_TOOLTIP_MAX_WIDTH = 320
_TOOLTIP_MARGIN = 8


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


def blend_color(widget: tk.Widget, foreground: str, background: str, opacity: float) -> str:
    """Blend `foreground` toward `background` at `opacity` (1.0 = full foreground), returned
    as a #rrggbb string. Used to derive theme-aware secondary text and border colors."""
    fg = [channel // 256 for channel in widget.winfo_rgb(foreground)]
    bg = [channel // 256 for channel in widget.winfo_rgb(background)]
    blended = (int(f * opacity + b * (1.0 - opacity)) for f, b in zip(fg, bg, strict=True))
    return "#{:02x}{:02x}{:02x}".format(*blended)


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
        label="Help Guide",
        underline=0,
        accelerator="F1",
        command=lambda: webbrowser.open_new_tab(HELP_GUIDE_URL),
    )
    menu.add_command(
        label="Discord", underline=0, command=lambda: webbrowser.open_new_tab(DISCORD_URL)
    )
    menu.add_separator()
    menu.add_command(label="Open Logs", underline=5, command=lambda: open_path(log_folder()))
    menu.add_command(label="About DVR-Scan", underline=0, command=lambda: show_about(root))
    toplevel = root.winfo_toplevel()
    toplevel.bind("<F1>", lambda _: webbrowser.open_new_tab(HELP_GUIDE_URL), add="+")


def show_modal(window: tk.Toplevel, parent: tk.Misc, initial_focus: ty.Optional[tk.Misc] = None):
    """Show `window` as a modal dialog over `parent` (the grab blocks input to other
    windows until `hide_modal`). Returns immediately: `wait_window` only returns once the
    window is destroyed, so waiting here would leave a nested event loop running for each
    time a reusable dialog is opened."""
    window.transient(parent)
    window.deiconify()
    (initial_focus if initial_focus is not None else window).focus_set()
    window.grab_set()


def hide_modal(window: tk.Toplevel, focus: tk.Misc):
    """Hide a dialog shown with `show_modal` (keeping it for reuse), returning focus to
    `focus`."""
    window.withdraw()
    window.grab_release()
    focus.focus()


class Tooltip:
    """A minimal hover and keyboard-focus tooltip, e.g. to label icon-only buttons and
    explain technical settings."""

    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text = text
        self._tip: ty.Optional[tk.Toplevel] = None
        self._pointer_inside = False
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<FocusIn>", self._on_focus_in, add="+")
        widget.bind("<FocusOut>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Escape>", self._hide, add="+")
        # Tear down a visible tip if the widget is hidden (`grid_remove`) or destroyed.
        widget.bind("<Unmap>", self._on_unmap, add="+")
        widget.bind("<Destroy>", self._on_unmap, add="+")

    def _on_enter(self, _event=None):
        self._pointer_inside = True
        self._show()

    def _on_leave(self, _event=None):
        self._pointer_inside = False
        self._hide()

    def _on_focus_in(self, _event=None):
        # Only show on keyboard focus traversal: clicking a hovered button fires
        # `<ButtonPress>` (hiding the tip) and then `<FocusIn>`, which should not re-open it.
        if not self._pointer_inside:
            self._show()

    def _on_unmap(self, _event=None):
        self._pointer_inside = False
        self._hide()

    def _show(self, _event=None):
        if (
            self._tip is not None
            or not self._widget.winfo_exists()
            or not self._widget.winfo_viewable()
        ):
            return
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        tk.Label(
            self._tip,
            text=self._text,
            justify=tk.LEFT,
            foreground="#1a1a1a",
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=3,
            wraplength=_TOOLTIP_MAX_WIDTH,
        ).pack()
        self._tip.update_idletasks()
        tip_w = self._tip.winfo_reqwidth()
        tip_h = self._tip.winfo_reqheight()
        screen_w = self._widget.winfo_screenwidth()
        screen_h = self._widget.winfo_screenheight()
        x = self._widget.winfo_rootx() + min(16, self._widget.winfo_width() // 2)
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        if x + tip_w + _TOOLTIP_MARGIN > screen_w:
            x = max(_TOOLTIP_MARGIN, screen_w - tip_w - _TOOLTIP_MARGIN)
        if y + tip_h + _TOOLTIP_MARGIN > screen_h:
            y = max(_TOOLTIP_MARGIN, self._widget.winfo_rooty() - tip_h - 4)
        self._tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


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
        self._native: ty.Optional[tk.Menu] = None
        self.frame: ty.Optional[tk.Frame] = None
        self._background = ""
        self._hover = ""
        if os.name != "nt":
            self._native = tk.Menu(master)
            master["menu"] = self._native
            return
        self._toplevel = master.winfo_toplevel()
        self._menus: ty.Dict[tk.Menubutton, tk.Menu] = {}
        self._posted_button: ty.Optional[tk.Menubutton] = None
        self._pending_switch: ty.Optional[tk.Menubutton] = None
        self._poll_id: ty.Optional[str] = None
        self._last_unpost: ty.Tuple[ty.Optional[tk.Menubutton], float] = (None, 0.0)
        self._background = ttk.Style().lookup("TFrame", "background") or "SystemButtonFace"
        self.frame = tk.Frame(master, background=self._background)
        self.frame.bind("<Destroy>", self._cancel_hover_poll, add="+")
        self._hover = _darken(self.frame, self._background)
        self._toplevel.bind("<F10>", lambda _: self._post_first_menu(), add="+")

    def _can_post(self) -> bool:
        toplevel = self._toplevel
        if not toplevel.winfo_exists() or not toplevel.winfo_viewable():
            return False
        grab = toplevel.grab_current()
        return grab is None or grab == toplevel

    def _button_at_pointer(self) -> ty.Optional[tk.Menubutton]:
        px, py = self.frame.winfo_pointerxy()
        for button in self._menus:
            if str(button["state"]) == "disabled":
                continue
            bx, by = button.winfo_rootx(), button.winfo_rooty()
            bw, bh = button.winfo_width(), button.winfo_height()
            if bx <= px < bx + bw and by <= py < by + bh:
                return button
        return None

    def _sync_backgrounds(self):
        active = self._posted_button
        if active is None:
            active = self._button_at_pointer()
        for button in self._menus:
            button.configure(background=self._hover if button is active else self._background)

    def _on_button_enter(self, button: tk.Menubutton):
        if self._posted_button is None:
            button.configure(background=self._hover)

    def _on_button_leave(self, button: tk.Menubutton):
        if self._posted_button is None:
            button.configure(background=self._background)

    def _dismiss_active_menu(self):
        ctypes.windll.user32.EndMenu()

    def _cancel_hover_poll(self, _event=None):
        if self._poll_id is not None:
            try:
                self.frame.after_cancel(self._poll_id)
            except tk.TclError:
                pass
        self._poll_id = None

    def _poll_hover(self):
        self._poll_id = None
        if self._posted_button is None:
            return
        target = self._button_at_pointer()
        if target is not None and target is not self._posted_button:
            self._pending_switch = target
            self._dismiss_active_menu()
            return
        self._poll_id = self.frame.after(_MENUBAR_POLL_MS, self._poll_hover)

    def _on_button_press(self, button: tk.Menubutton) -> str:
        # Clicking an open heading closes Win32 `TrackPopupMenu` first and then delivers
        # `<Button-1>` to the heading; skip re-posting so a second click toggles it closed.
        last_btn, last_time = self._last_unpost
        if button is last_btn and (time.monotonic() - last_time) < _MENUBAR_REOPEN_GUARD_SEC:
            self._last_unpost = (None, 0.0)
        else:
            self._post_button_menu(button)
        return "break"

    def _post_button_menu(
        self, button: tk.Menubutton, select_first: bool = False
    ) -> ty.Optional[str]:
        if not self._can_post() or str(button["state"]) == "disabled":
            return None
        self._pending_switch = None
        while True:
            self._posted_button = button
            self._sync_backgrounds()
            self._cancel_hover_poll()
            self._poll_id = self.frame.after(_MENUBAR_POLL_MS, self._poll_hover)
            menu = self._menus[button]
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            entry = 0 if (select_first and menu.index(tk.END) is not None) else ""
            # `tk_popup` does not return until the menu closes.
            menu.tk_popup(x, y, entry)
            self._cancel_hover_poll()
            self._posted_button = None
            next_button, self._pending_switch = self._pending_switch, None
            if not self.frame.winfo_exists():
                return "break"
            if next_button is None or not self._can_post():
                break
            button, select_first = next_button, False
        self._last_unpost = (button, time.monotonic())
        self._sync_backgrounds()
        return "break"

    def _post_first_menu(self) -> ty.Optional[str]:
        if self._menus:
            return self._post_button_menu(next(iter(self._menus)), select_first=True)
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
        # modal popup loop is running. Returning "break" stops the `Menubutton` class
        # bindings for press, drag and release. Those bindings would post or unpost the
        # menu themselves.
        button.bind("<Button-1>", lambda _: self._on_button_press(button))
        button.bind("<ButtonRelease-1>", lambda _: "break")
        button.bind("<B1-Motion>", lambda _: "break")
        button.bind("<Enter>", lambda _: self._on_button_enter(button))
        button.bind("<Leave>", lambda _: self._on_button_leave(button))
        button.pack(side=tk.LEFT)
        self._menus[button] = menu
        if underline is not None and 0 <= underline < len(label):
            char = label[underline]
            if char.isalpha():
                for seq in (f"<Alt-{char.lower()}>", f"<Alt-{char.upper()}>"):
                    self._toplevel.bind(
                        seq,
                        lambda _: self._post_button_menu(button, select_first=True),
                        add="+",
                    )
        return menu
