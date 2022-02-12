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
from dvr_scan.scanner import ScanContext

# ROI within the frame used for the test case (see traffic_camera.txt for details).
TRAFFIC_CAMERA_ROI = [631, 532, 210, 127]

TRAFFIC_CAMERA_EVENTS = [
    (9, 148),
    (358, 490),
    (542, 576),
]

TRAFFIC_CAMERA_EVENTS_TIME_PRE_5 = [
    (3, 148),
    (352, 490),
    (536, 576),
]

TRAFFIC_CAMERA_EVENTS_TIME_POST_40 = [
    (9, 138),
    (358, 480),
    (542, 576),                        # Last event still ends on end of video.
]

TRAFFIC_CAMERA_EVENTS_CNT = [
                              # Even though the first frame contains motion, the first frame we can actually detect it on is
                              # the first frame.
    (1, 148),
    (364, 490),
    (543, 576),
]

# Small ROI for quicker processing
CORRUPT_VIDEO_ROI = [0, 0, 32, 32]
CORRUPT_VIDEO_EVENTS = [
    (153, 364),
]


def test_scan_context(traffic_camera_video):
    """ Test basic functionality of ScanContext with default parameters. """

    sctx = ScanContext([traffic_camera_video])
    sctx.set_detection_params(roi=TRAFFIC_CAMERA_ROI)
    sctx.set_event_params(min_event_len=4, time_pre_event=0)

    event_list = sctx.scan_motion()

    assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS)
    # Remove duration, check start/end times.
    event_list = [(event[0].frame_num, event[1].frame_num) for event in event_list]
    assert event_list == TRAFFIC_CAMERA_EVENTS

    # TODO(v1.0): Add check for duration (should be end - start + 1).


def test_scan_context_cnt(traffic_camera_video):
    """ Test basic functionality of ScanContext using the CNT algorithm. """

    sctx = ScanContext([traffic_camera_video])
    sctx.set_detection_params(roi=TRAFFIC_CAMERA_ROI)
    sctx.set_event_params(min_event_len=3, time_pre_event=0)

    event_list = sctx.scan_motion(method='cnt')

    assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS_CNT)
    # Remove duration, check start/end times.
    event_list = [(event[0].frame_num, event[1].frame_num) for event in event_list]
    assert event_list == TRAFFIC_CAMERA_EVENTS_CNT


def test_pre_event_shift(traffic_camera_video):
    """ Test setting time_pre_event. """

    sctx = ScanContext([traffic_camera_video])
    sctx.set_detection_params(roi=TRAFFIC_CAMERA_ROI)
    sctx.set_event_params(min_event_len=4, time_pre_event=6)

    event_list = sctx.scan_motion()

    assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS_TIME_PRE_5)
    event_list = [(event[0].frame_num, event[1].frame_num) for event in event_list]
    assert all([x == y for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_PRE_5)])


def test_pre_event_shift_with_frame_skip(traffic_camera_video):
    """ Test setting time_pre_event when using frame_skip. """
    for frame_skip in range(1, 3):

        sctx = ScanContext([traffic_camera_video], frame_skip=frame_skip)
        sctx.set_detection_params(roi=TRAFFIC_CAMERA_ROI)
        sctx.set_event_params(min_event_len=4, time_pre_event=6)

        event_list = sctx.scan_motion()

        assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS_TIME_PRE_5)
        event_list = [(event[0].frame_num, event[1].frame_num) for event in event_list]
        # The results should not differ from the ground truth (non-frame-skipped) by the amount
        # of frames that we are skipping.
        assert all([
            abs(x[0] - y[0]) <= frame_skip and abs(x[1] - y[1]) <= frame_skip
            for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_PRE_5)
        ])


def test_post_event_shift(traffic_camera_video):
    """ Test setting time_post_event. """

    sctx = ScanContext([traffic_camera_video])
    sctx.set_detection_params(roi=TRAFFIC_CAMERA_ROI)
    sctx.set_event_params(min_event_len=4, time_pre_event=0, time_post_event=40)

    event_list = sctx.scan_motion()

    assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS_TIME_POST_40)
    event_list = [(event[0].frame_num, event[1].frame_num) for event in event_list]
    assert all([x == y for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_POST_40)])


def test_post_event_shift_with_frame_skip(traffic_camera_video):
    """ Test setting time_post_event. """
    for frame_skip in range(1, 3):

        sctx = ScanContext([traffic_camera_video], frame_skip=frame_skip)

        sctx = ScanContext([traffic_camera_video], frame_skip=1)
        sctx.set_detection_params(roi=TRAFFIC_CAMERA_ROI)
        sctx.set_event_params(min_event_len=4, time_pre_event=0, time_post_event=40)

        event_list = sctx.scan_motion()

        assert len(event_list) == len(TRAFFIC_CAMERA_EVENTS_TIME_POST_40)
        event_list = [(event[0].frame_num, event[1].frame_num) for event in event_list]
        # The results should not differ from the ground truth (non-frame-skipped) by the amount
        # of frames that we are skipping.
        assert all([
            abs(x[0] - y[0]) <= frame_skip and abs(x[1] - y[1]) <= frame_skip
            for x, y in zip(event_list, TRAFFIC_CAMERA_EVENTS_TIME_POST_40)
        ])


def test_decode_corrupt_video(corrupt_video):
    """Ensure we can process a video with a single bad frame."""
    sctx = ScanContext([corrupt_video])
    sctx.set_detection_params(roi=CORRUPT_VIDEO_ROI)

    event_list = sctx.scan_motion()

    assert len(event_list) == len(CORRUPT_VIDEO_EVENTS)
    event_list = [(event[0].frame_num, event[1].frame_num) for event in event_list]
    assert all([x == y for x, y in zip(event_list, CORRUPT_VIDEO_EVENTS)])
