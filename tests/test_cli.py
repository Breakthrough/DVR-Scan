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

BASE_COMMAND_EVENT_LIST_GOLDEN = """
-------------------------------------------------------------
|   Event #    |  Start Time  |   Duration   |   End Time   |
-------------------------------------------------------------
|  Event    1  |  00:00:00.4  |  00:00:05.6  |  00:00:05.9  |
|  Event    2  |  00:00:14.3  |  00:00:05.3  |  00:00:19.6  |
|  Event    3  |  00:00:21.7  |  00:00:01.4  |  00:00:23.0  |
-------------------------------------------------------------
"""[1:]

BASE_COMMAND_TIMECODE_LIST_GOLDEN = """
00:00:00.360,00:00:05.920,00:00:14.320,00:00:19.600,00:00:21.680,00:00:23.040
"""[1:]


def test_info_commands():
    """Test information commands (e.g. -h/--help)."""
    assert subprocess.call(DVR_SCAN_COMMAND + ['--help']) == 0
    assert subprocess.call(DVR_SCAN_COMMAND + ['--version']) == 0
    assert subprocess.call(DVR_SCAN_COMMAND + ['--license']) == 0


def test_scan_only(tmp_path):
    """Test -so/--scan-only."""
    tmp_path = str(tmp_path)                     # Hack for Python 3.7 builder.
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
    assert len(os.listdir(tmp_path)) == 0, "Scan-only mode should not create any files."
    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


def test_quiet_mode(tmp_path):
    """Test -q/--quiet."""
    tmp_path = str(tmp_path)                     # Hack for Python 3.7 builder.
    output = subprocess.check_output(
        args=DVR_SCAN_COMMAND + BASE_COMMAND + [
            '--output-dir',
            tmp_path,
            '--scan-only',
            '--quiet',
        ],
        text=True)
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


def test_mog(tmp_path):
    """Test -b/--bg-subtractor MOG (the default)."""
    tmp_path = str(tmp_path)                                        # Hack for Python 3.7 builder.
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
    ]) == 0

    # Make sure the correct # of events were detected.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


@pytest.mark.skipif(not MotionDetectorCNT.is_available(), reason="CNT not available")
def test_cnt(tmp_path):
    """Test -b/--bg-subtractor CNT."""
    tmp_path = str(tmp_path)                                        # Hack for Python 3.7 builder.
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--bg-subtractor',
        'cnt',
    ]) == 0
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


@pytest.mark.skipif(not MotionDetectorCudaMOG2.is_available(), reason="MOG_CUDA not available")
def test_mog_cuda(tmp_path):
    """Test -b/--bg-subtractor MOG_CUDA."""
    tmp_path = str(tmp_path)                                        # Hack for Python 3.7 builder.
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--bg-subtractor',
        'mog_cuda',
    ]) == 0
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


def test_overlays(tmp_path):
    """Test overlays -bb/--bounding-box and -tc/--timecode."""
    tmp_path = str(tmp_path)                                        # Hack for Python 3.7 builder.
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--bounding-box',
        '--time-code',
    ]) == 0
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


def test_mask_output(tmp_path):
    """Test mask output -mo/--mask-output."""
    tmp_path = str(tmp_path)                                        # Hack for Python 3.7 builder.
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--scan-only',
        '--mask-output',
        'mask.avi',
    ]) == 0

    assert os.listdir(tmp_path) == ['mask.avi'], "Only mask file should be created with -so -mo ..."


def test_config_file(tmp_path):
    """Test using a config file to set the same parameters as in BASE_COMMAND."""
    tmp_path = str(tmp_path) # Hack for Python 3.7 builder.
    cfg_path = os.path.join(tmp_path, 'config.cfg')
    with open(cfg_path, 'w') as f:
        f.write(TEST_CONFIG_FILE)

    output = subprocess.check_output(
        args=DVR_SCAN_COMMAND + BASE_COMMAND[0:2] + [ # Only use the input from BASE_COMMAND.
            '--output-dir',
            tmp_path,
            '--config',
            cfg_path,
        ],
        text=True)

    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS + 1, "Incorrect amount of files."
    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


@pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")
def test_ffmpeg_mode(tmp_path):
    """Test -m/--mode ffmpeg."""
    tmp_path = str(tmp_path)                                        # Hack for Python 3.7 builder.
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--output-mode',
        'ffmpeg',
    ]) == 0
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."
                                                                    # TODO: Open files and validate some frames.


@pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")
def test_copy_mode(tmp_path):
    """Test -m/--mode copy."""
    tmp_path = str(tmp_path)                                        # Hack for Python 3.7 builder.
    assert subprocess.call(args=DVR_SCAN_COMMAND + BASE_COMMAND + [
        '--output-dir',
        tmp_path,
        '--output-mode',
        'copy',
    ]) == 0
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."
