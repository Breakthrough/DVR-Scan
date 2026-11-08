#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2026 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""Tests for the pure helpers used by the Windows release scripts in scripts/.

These do not require Advanced Installer, 7-Zip, msiexec, or a frozen build.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "scripts"))

from common import (  # noqa: E402
    display_version,
    manifest_name,
    msi_name,
    read_version,
    zip_name,
)
from validate_release import parse_version_output  # noqa: E402

SAMPLE_VERSION_OUTPUT = """\
DVR-Scan 2.0
------------------------------------------------
Copyright (C) 2026 Brandon Castellano
< https://www.dvr-scan.com >

System Info
------------------------------------------------
OS:      Windows-11-10.0.26200-SP0
Python:  CPython 3.13.5
Arch:    64bit + WindowsPE

Packages
------------------------------------------------
av               18.0.0
cv2              4.11.0
dvr_scan         2.0
moviepy          Not Installed
numpy            2.4.2
platformdirs     4.9.2
PIL              12.2.0
scenedetect      0.7.2
screeninfo       Not Installed
tqdm             4.67.3

Features
------------------------------------------------
ffmpeg           9.0.2
PyAV             Installed
tkinter          Installed
"""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2.0", "2.0"),
        ("2.0.1", "2.0.1"),
        ("2.1-dev0", "2.1"),
        ("2.1.dev0", "2.1"),
        ("2.0-rc1", "2.0"),
    ],
)
def test_display_version(raw: str, expected: str):
    assert display_version(raw) == expected


def test_artifact_names():
    assert msi_name("2.0") == "dvr-scan-2.0-win64.msi"
    assert zip_name("2.0") == "dvr-scan-2.0-win64.zip"
    assert manifest_name("2.0.1") == "dvr-scan-2.0.1-win64.manifest.json"


def test_read_version_matches_init():
    text = (REPO_DIR / "dvr_scan" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
    assert match is not None
    assert read_version() == match.group(1)


def test_parse_version_output():
    header, packages, features = parse_version_output(SAMPLE_VERSION_OUTPUT)
    assert header == "2.0"
    assert packages == {
        "av": "18.0.0",
        "cv2": "4.11.0",
        "dvr_scan": "2.0",
        "moviepy": "Not Installed",
        "numpy": "2.4.2",
        "platformdirs": "4.9.2",
        "PIL": "12.2.0",
        "scenedetect": "0.7.2",
        "screeninfo": "Not Installed",
        "tqdm": "4.67.3",
    }
    assert features == {"ffmpeg": "9.0.2", "PyAV": "Installed", "tkinter": "Installed"}


def test_parse_version_output_dev_header():
    header, packages, _ = parse_version_output(SAMPLE_VERSION_OUTPUT.replace("2.0", "2.0-dev0", 1))
    assert header == "2.0-dev0"
    assert display_version(header) == "2.0"
    assert packages["dvr_scan"] == "2.0"


def test_parse_version_output_without_features():
    text = SAMPLE_VERSION_OUTPUT.split("\nFeatures\n", 1)[0]
    header, packages, features = parse_version_output(text)
    assert header == "2.0"
    assert packages["tqdm"] == "4.67.3"
    assert features == {}
