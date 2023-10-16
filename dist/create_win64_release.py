# -*- coding: utf-8 -*-
import glob
import os
import shutil

DIST_PATH = "dist/dvr-scan/"
BASE_PATH = DIST_PATH + "_internal/"

# TODO: See if some these can be excluded in the .spec file.
DIRECTORY_GLOBS = [
    'altgraph-*.dist-info',
    'certifi',
    'imageio',
    'imageio_ffmpeg',
    'importlib_metadata-*.dist-info',
    'matplotlib',
    'PIL',
    'PyQt5',
    'pip-*.dist-info',
    'psutil',
    'pyinstaller-*.dist-info',
    'setuptools-*.dist-info',
    'tcl8',
    'wheel-*.dist-info',
    'wx',
]

FILE_GLOBS = [
    '_bz2.pyd',
    '_decimal.pyd',
    '_elementtree.pyd',
    '_hashlib.pyd',
    '_lzma.pyd',
    '_multiprocessing.pyd',
    'd3dcompiler*.dll',
    'kiwisolver.*.pyd',
    'libopenblas64_*',  # There seems to be a second copy of this currently.
    'libEGL.dll',
    'libGLESv2.dll',
    'opengl32sw.dll',
    'Qt5*.dll',
    'wxbase*.dll',
    'wxmsw315u*.dll',
]

for dir_glob in DIRECTORY_GLOBS:
    for dir_path in glob.glob(os.path.join(BASE_PATH, dir_glob)):
        shutil.rmtree(dir_path)

for file_glob in FILE_GLOBS:
    for file_path in glob.glob(os.path.join(BASE_PATH, file_glob)):
        os.remove(file_path)

# TODO: See if the following can be added to COLLECT instead of including
# these files as part of the .spec file Analysis step.

for f in glob.glob(os.path.join(BASE_PATH, "dvr-scan/*")):
    shutil.move(f, DIST_PATH)

os.rmdir(os.path.join(BASE_PATH, "dvr-scan"))
