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
"""DVR-Scan VideoJoiner Tests"""

from dvr_scan.video_joiner import VideoJoiner

TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES = 576
CORRUPT_VIDEO_TOTAL_FRAMES = 596


def test_decode_single(traffic_camera_video):
    """Test VideoJoiner with a single video as input."""
    video = VideoJoiner([traffic_camera_video])
    assert video.total_frames == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES
    while video.read(False) is True:
        pass
    assert video.position.get_frames() == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES
    assert video.decode_failures == 0


def test_decode_multiple(traffic_camera_video):
    """Test VideoJoiner with multiple videos as inputs."""
    splice_amount = 3
    video = VideoJoiner([traffic_camera_video] * splice_amount)
    assert video.total_frames == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES * splice_amount
    while video.read(False) is not None:
        pass
    assert video.position.get_frames() == TRAFFIC_CAMERA_VIDEO_TOTAL_FRAMES * splice_amount
    assert video.decode_failures == 0
