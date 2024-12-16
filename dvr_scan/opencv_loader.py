#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""``dvr_scan.opencv_loader`` Module

Ensures required DLL files can be loaded by Python when importing OpenCV, and provides
better error messaging in cases where the module isn't installed.
"""

import importlib
import importlib.util
import os

# On Windows, make sure we include any required DLL paths.
if os.name == "nt":
    # If CUDA is installed, include those DLLs in the search paths.
    CUDA_PATH = os.environ["CUDA_PATH"] if "CUDA_PATH" in os.environ else None
    if CUDA_PATH and os.path.exists(CUDA_PATH):
        CUDA_BIN_PATH = os.path.abspath(os.path.join(CUDA_PATH, "bin"))
        os.add_dll_directory(CUDA_BIN_PATH)

# OpenCV is a required package, but we don't have it as an explicit dependency since we
# need to support both opencv-python and opencv-python-headless. Include some additional
# context with the exception if this is the case.

if not importlib.util.find_spec("cv2"):
    raise ModuleNotFoundError(
        "OpenCV could not be found, try installing opencv-python:\n\npip install opencv-python",
        name="cv2",
    )
