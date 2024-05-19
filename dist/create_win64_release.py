# -*- coding: utf-8 -*-
import glob
import os
import shutil
import sys
sys.path.append(os.path.abspath("."))


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



def write_version_file():

    import dvr_scan
    VERSION = dvr_scan.__version__

    with open("dist/.version_info", "wb") as f:
        v = VERSION.split(".")
        assert len(v) <= 3

        if len(v) == 3:
            (maj, min, pat) = int(v[0]), int(v[1]), int(v[2])
        else:
            (maj, min, pat) = int(v[0]), int(v[1]), 0

        f.write(f"""# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
# filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
# Set not needed items to zero 0.
filevers=(0, {maj}, {min}, {pat}),
prodvers=(0, 1, 6, 1),
# Contains a bitmask that specifies the valid bits 'flags'r
mask=0x3f,
# Contains a bitmask that specifies the Boolean attributes of the file.
flags=0x0,
# The operating system for which this file was designed.
# 0x4 - NT and there is no need to change it.
OS=0x4,
# The general type of file.
# 0x1 - the file is an application.
fileType=0x1,
# The function of the file.
# 0x0 - the function is not defined for this fileType
subtype=0x0,
# Creation date and time stamp.
date=(0, 0)
),
  kids=[
StringFileInfo(
  [
  StringTable(
    u'040904B0',
    [StringStruct(u'CompanyName', u'github.com/Breakthrough'),
    StringStruct(u'FileDescription', u'dvr-scan.readthedocs.io'),
    StringStruct(u'FileVersion', u'{VERSION}'),
    StringStruct(u'InternalName', u'DVR-Scan'),
    StringStruct(u'LegalCopyright', u'Copyright © 2024 Brandon Castellano'),
    StringStruct(u'OriginalFilename', u'dvr-scan.exe'),
    StringStruct(u'ProductName', u'DVR-Scan'),
    StringStruct(u'ProductVersion', u'{VERSION}')])
  ]),
VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
""".encode())
