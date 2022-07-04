# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Copyright (C) 2014-2022 Brandon Castellano <http://www.bcastell.com>.
# PySceneDetect is licensed under the BSD 2-Clause License; see the
# included LICENSE file, or visit one of the above pages for details.
#
"""DVR-Scan CLI Tests"""

# Standard project pylint disables for unit tests using pytest.
# pylint: disable=no-self-use, protected-access, multiple-statements, invalid-name
# pylint: disable=redefined-outer-name, wrong-import-order, unused-import, ungrouped-imports

# Import the OpenCV loader first as PySceneDetect tries to import it.
from dvr_scan import opencv_loader

import os
import subprocess
from typing import List

import pytest
from scenedetect.video_splitter import is_ffmpeg_available

from dvr_scan.motion_detector import MotionDetectorCNT, MotionDetectorCudaMOG2

DVR_SCAN_COMMAND: List[str] = 'python -m dvr_scan'.split(' ')
ALL_BG_SUBTRACTORS: List[str] = ['mog', 'mog_cuda', 'cnt']
BASE_OUTPUT_NAME: str = 'traffic_camera'
# Should yield 3 events with all detector types.
BASE_COMMAND = [
    '--input',
    'tests/resources/traffic_camera.mp4',
    '--region-of-interest',
    '631,532, 210,127',
    '--min-event-length',
    '4',
    '--time-before-event',
    '0',
]
BASE_COMMAND_NUM_EVENTS = 3

TEST_CONFIG_FILE = """
region-of-interest = 631,532 210,127
min-event-length = 4
time-before-event = 0
"""


def test_info_commands():
    """Test information commands (e.g. -h/--help)."""
    assert subprocess.call(DVR_SCAN_COMMAND + ['--help']) == 0
    assert subprocess.call(DVR_SCAN_COMMAND + ['--version']) == 0
    assert subprocess.call(DVR_SCAN_COMMAND + ['--license']) == 0


def test_scan_only(tmp_path):
    """Test -so/--scan-only."""
    output = subprocess.check_output(
        args=DVR_SCAN_COMMAND + BASE_COMMAND + [
            '--output-dir',
            tmp_path,
            '--scan-only',
        ],
        text=True)
    # Make sure the correct # of events were detected.
    assert 'Detected %d motion events in input.' % (BASE_COMMAND_NUM_EVENTS) in output
    # Make sure we didn't create a directory since we shouldn't write any files.
    assert len(os.listdir(tmp_path)) == 0


def test_mog(tmp_path):
    """Test -b/--bg-subtractor MOG (the default)."""
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
    ]) == 0
    # Make sure the correct # of events were detected.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS


@pytest.mark.skipif(not MotionDetectorCNT.is_available(), reason="CNT not available")
def test_cnt(tmp_path):
    """Test -b/--bg-subtractor CNT."""
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--bg-subtractor',
        'cnt',
    ]) == 0
    # Make sure the correct # of events were detected.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS


@pytest.mark.skipif(not MotionDetectorCudaMOG2.is_available(), reason="MOG_CUDA not available")
def test_mog_cuda(tmp_path):
    """Test -b/--bg-subtractor MOG_CUDA."""
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--bg-subtractor',
        'mog_cuda',
    ]) == 0
    # Make sure the correct # of events were detected.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS


def test_overlays(tmp_path):
    """Test overlays -bb/--bounding-box and -tc/--timecode."""
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--bounding-box',
        '--time-code',
    ]) == 0
    # Make sure the correct # of events were detected.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS


def test_mask_output(tmp_path):
    """Test mask output -mo/--mask-output."""
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--scan-only',
        '--mask-output',
        'mask.avi',
    ]) == 0
    # Make sure only the mask file was created since we also used --scan-only.
    assert os.listdir(tmp_path) == ['mask.avi']


def test_config_file(tmp_path):
    """Test using a config file to set the same parameters as in BASE_COMMAND."""
    cfg_path = os.path.join(tmp_path, 'config.cfg')
    with open(cfg_path, 'w') as f:
        f.write(TEST_CONFIG_FILE)
    # Only use the input `--input` from BASE_COMMAND.
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND[0:2] + [
        '--output-dir',
        tmp_path,
        '--config',
        cfg_path,
    ]) == 0
    # Make sure the correct # of events were detected (correct for config file).
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS + 1


@pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")
def test_ffmpeg_mode(tmp_path):
    """Test -m/--mode ffmpeg."""
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND +
                           ['--output-dir', tmp_path, '--output-mode', 'ffmpeg']) == 0
    # Make sure the correct # of events were detected.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS


@pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")
def test_copy_mode(tmp_path):
    """Test -m/--mode copy."""
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND +
                           ['--output-dir', tmp_path, '--output-mode', 'copy']) == 0
    # Make sure the correct # of events were detected.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS
