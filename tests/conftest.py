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

import pytest

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
