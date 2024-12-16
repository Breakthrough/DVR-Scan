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

"""Infrastructure script to run after generating an EXE release."""

import glob
import os
import shutil
from pathlib import Path


def finalize_exe_distribution():
    print("Finalizing EXE distribution.")
    DIST_PATH = "dist/dvr-scan/"
    BASE_PATH = DIST_PATH + "_internal/"

    # TODO: See if some these can be excluded in the .spec file.
    DIRECTORY_GLOBS = [
        "altgraph-*.dist-info",
        "certifi",
        "imageio",
        "imageio_ffmpeg",
        "importlib_metadata-*.dist-info",
        "matplotlib",
        "PyQt5",
        "pip-*.dist-info",
        "psutil",
        "pyinstaller-*.dist-info",
        "setuptools-*.dist-info",
        "tcl8",
        "pywin32_system32",
        "wheel-*.dist-info",
        "win32",
        "wx",
    ]
    FILE_GLOBS = [
        "_bz2.pyd",
        "_decimal.pyd",
        "_elementtree.pyd",
        "_hashlib.pyd",
        "_lzma.pyd",
        "_multiprocessing.pyd",
        "d3dcompiler*.dll",
        "kiwisolver.*.pyd",
        "libopenblas64_*",  # There seems to be a second copy of this currently.
        "libEGL.dll",
        "libGLESv2.dll",
        "opengl32sw.dll",
        "Qt5*.dll",
        "wxbase*.dll",
        "wxmsw315u*.dll",
    ]

    for dir_glob in DIRECTORY_GLOBS:
        for dir_path in glob.glob(os.path.join(BASE_PATH, dir_glob)):
            shutil.rmtree(dir_path)

    for file_glob in FILE_GLOBS:
        for file_path in glob.glob(os.path.join(BASE_PATH, file_glob)):
            os.remove(file_path)

    shutil.copytree("dvr_scan/docs", Path(DIST_PATH).joinpath("docs"), dirs_exist_ok=True)

    EXE_ASSETS = [
        "dist/README.txt",
        "dvr_scan/LICENSE",
        "dvr-scan.cfg",
    ]
    for asset in EXE_ASSETS:
        shutil.copy(asset, DIST_PATH)


if __name__ == "__main__":
    finalize_exe_distribution()
