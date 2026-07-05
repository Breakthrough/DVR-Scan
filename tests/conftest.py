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
"""DVR-Scan Test Configuration

This file includes all pytest configuration for running DVR-Scan's tests.

"""

import os
import shutil
from pathlib import Path

import pytest


def pytest_configure(config):
    """Allow ffmpeg-gated tests to run on machines where ffmpeg is not on PATH but a
    copy exists in the repository root (as shipped with the Windows build)."""
    repo_root = Path(__file__).resolve().parent.parent
    ffmpeg_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if shutil.which("ffmpeg") is None and (repo_root / ffmpeg_name).exists():
        os.environ["PATH"] = str(repo_root) + os.pathsep + os.environ.get("PATH", "")


#
# Helper Functions
#


def get_absolute_path(relative_path: str) -> str:
    """Returns the absolute path to a (relative) path of a file that
    should exist within the tests/ directory.

    Throws FileNotFoundError if the file could not be found.
    """
    abs_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(
            "Test video file (%s) must be present to run test case!" % relative_path
        )
    return abs_path


#
# Test Case Fixtures
#


@pytest.fixture
def traffic_camera_video() -> str:
    """Returns path to traffic_camera.mp4 video."""
    return get_absolute_path("resources/traffic_camera.mp4")


@pytest.fixture
def corrupt_video() -> str:
    """Returns path to issue62.mp4 video."""
    return get_absolute_path("resources/issue62.mp4")


@pytest.fixture
def delayed_start_video() -> str:
    """Returns path to haze.mp4, which has a nonzero video stream start time (1.075s)."""
    return get_absolute_path("resources/haze.mp4")


@pytest.fixture
def vfr_video() -> str:
    """Returns path to traffic_camera_vfr.mp4, a variable framerate re-encode of
    traffic_camera.mp4 where the first 288 frames play at 25 fps and the remainder
    at 12.5 fps. Generated with:

    ffmpeg -i traffic_camera.mp4
      -vf "setpts='if(lt(N,288),N/25/TB,(288/25+(N-288)/12.5)/TB)'"
      -fps_mode vfr -c:v libx264 -preset veryfast -crf 23 -an traffic_camera_vfr.mp4
    """
    return get_absolute_path("resources/traffic_camera_vfr.mp4")
