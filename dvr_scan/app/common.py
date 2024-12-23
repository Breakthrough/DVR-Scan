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
import sys
import tkinter as tk

import PIL
import PIL.Image
import PIL.ImageTk

import dvr_scan

SUPPORTS_RESOURCES = sys.version_info.minor >= 9
if SUPPORTS_RESOURCES:
    import importlib.resources as resources


def register_icon(root: tk.Tk):
    if SUPPORTS_RESOURCES:
        # On Windows we always want a path so we can load the .ICO with `iconbitmap`.
        # On other systems, we can just use the PNG logo directly with `iconphoto`.
        if os.name == "nt":
            icon_path = resources.files(dvr_scan).joinpath("dvr-scan.ico")
            with resources.as_file(icon_path) as icon_path:
                root.iconbitmap(default=icon_path)
            return
        icon = PIL.Image.open(resources.open_binary(dvr_scan, "dvr-scan.png"))
        root.iconphoto(True, PIL.ImageTk.PhotoImage(icon))
