# -*- coding: utf-8 -*-
#
#       DVR-Scan: Find & Export Motion Events in Video Footage
#   --------------------------------------------------------------
#     [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#     [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Copyright (C) 2016-2021 Brandon Castellano <http://www.bcastell.com>.
#
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file or visit one of the following pages for details:
#  - https://github.com/Breakthrough/DVR-Scan/
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
""" DVR-Scan Test Configuration

This file includes all pytest configuration for running DVR-Scan's tests.

"""

import os
import pytest

#
# Helper Functions
#


def get_absolute_path(relative_path):
    # type: (str) -> str
    """ Returns the absolute path to a (relative) path of a file that
    should exist within the tests/ directory.

    Throws FileNotFoundError if the file could not be found.
    """
    abs_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError('Test video file (%s) must be present to run test case!' %
                                relative_path)
    return abs_path


#
# Test Case Fixtures
#


@pytest.fixture
def traffic_camera_video():
    # type: () -> str
    """ Returns path to traffic_camera.mp4 video. """
    return get_absolute_path("resources/traffic_camera.mp4")


@pytest.fixture
def corrupt_video():
    # type: () -> str
    """ Returns path to issue62.mp4 video. """
    return get_absolute_path("resources/issue62.mp4")
