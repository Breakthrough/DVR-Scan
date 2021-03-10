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
# This software uses Numpy and OpenCV; see the LICENSE-NUMPY and
# LICENSE-OPENCV files or visit the above URL for details.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

""" DVR-Scan ScanContext Tests """

# Standard project pylint disables for unit tests using pytest.
# pylint: disable=no-self-use, protected-access, multiple-statements, invalid-name
# pylint: disable=redefined-outer-name

# DVR-Scan Library Imports
import dvr_scan
from dvr_scan.scanner import ScanContext

# ROI within the frame used for the test case (see traffic_camera.txt for details).
TRAFFIC_CAMERA_ROI = [631, 532, 210, 127]
# Pairs of frames representing event start/end times.
TRAFFIC_CAMERA_EVENTS = [
    (10, 148),
    (359, 490),
    (543, 575)
]

def test_scan_context(traffic_camera_video):
    """ Test basic functionality of ScanContext with default parameters. """

    sctx = ScanContext([traffic_camera_video])
    sctx.set_detection_params(roi=TRAFFIC_CAMERA_ROI)

    event_list = sctx.scan_motion()

    assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS)
    # Remove duration, check start/end times.
    event_list = [(event[0].frame_num, event[1].frame_num)
                  for event in event_list]
    assert all([x == y for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS)])

