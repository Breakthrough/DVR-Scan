# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2014-2023 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""``dvr_scan.opencv_loader`` Module

Ensures required DLL files can be loaded by Python when importing OpenCV, and provides
better error messaging in cases where the module isn't installed.
"""

import os
import sys

# On Windows, make sure we include any required DLL paths.
if os.name == 'nt':
    # If we're running a frozen version of the app, the EXE path should include all required DLLs.
    # TODO(v1.6): This path might need to be updated with the latest version of Pyinstaller.
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        os.add_dll_directory(os.path.abspath(os.path.dirname(sys.executable)))
    # If CUDA is installed, include those DLLs in the search paths.
    if 'CUDA_PATH' in os.environ and os.path.exists(os.environ['CUDA_PATH']):
        os.add_dll_directory(os.path.abspath(os.path.join(os.environ['CUDA_PATH'], 'bin')))

# OpenCV is a required package, but we don't have it as an explicit dependency since we
# need to support both opencv-python and opencv-python-headless. Include some additional
# context with the exception if this is the case.
try:
    import cv2 as _
except ModuleNotFoundError as ex:
    raise ModuleNotFoundError(
        "OpenCV could not be found, try installing opencv-python:\n\npip install opencv-python",
        name='cv2',
    ) from ex
