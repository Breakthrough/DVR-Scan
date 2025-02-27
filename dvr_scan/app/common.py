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

import PIL
import PIL.Image
import PIL.ImageTk

import dvr_scan


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
