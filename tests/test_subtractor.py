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
"""Tests for background subtractor availability reporting."""

import importlib.metadata

import pytest

from dvr_scan import subtractor


def _installed(names):
    def version(name):
        if name in names:
            return "5.0.0.93"
        raise importlib.metadata.PackageNotFoundError(name)

    return version


@pytest.mark.parametrize(
    "installed,expected",
    [
        (set(), "pip install opencv-contrib-python`"),
        ({"opencv-contrib-python"}, "--force-reinstall --no-deps opencv-contrib-python`"),
        (
            {"opencv-contrib-python-headless"},
            "--force-reinstall --no-deps opencv-contrib-python-headless`",
        ),
        (
            {"opencv-contrib-python", "opencv-contrib-python-headless"},
            "--force-reinstall --no-deps opencv-contrib-python`",
        ),
    ],
)
def test_cnt_unavailable_message(monkeypatch, installed, expected):
    """The hint names the contrib package that is installed, and says to reinstall it
    (the regular OpenCV package overwrites the shared cv2 directory), or to install it
    when no contrib build is present."""
    monkeypatch.setattr(importlib.metadata, "version", _installed(installed))
    message = subtractor.cnt_unavailable_message()
    assert message.endswith(expected), message
    assert "CNT" in message
