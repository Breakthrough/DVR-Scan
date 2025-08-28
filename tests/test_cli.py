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
"""DVR-Scan CLI Tests

Tests high level usage of the DVR-Scan command line interface.
"""

import os
import platform
import subprocess
import typing as ty

import pytest
from scenedetect.video_splitter import is_ffmpeg_available

# We need to import the OpenCV loader before PySceneDetect as the latter imports OpenCV.
from dvr_scan.subtractor import SubtractorCNT, SubtractorCudaMOG2

MACHINE_ARCH = platform.machine().upper()

# TODO: Open extracted motion events and validate the actual frames.

DVR_SCAN_COMMAND: str = "python -m dvr_scan"
BASE_OUTPUT_NAME: str = "traffic_camera"
# Should yield 3 events with all detector types.
BASE_COMMAND = [
    "--input",
    "tests/resources/traffic_camera.mp4",
    "--add-region",
    "631 532 841 532 841 659 631 659",
    "--min-event-length",
    "4",
    "--time-before-event",
    "0",
    "--threshold",
    "0.2",
    "--ignore-user-config",
]
BASE_COMMAND_NUM_EVENTS = 3

TEST_CONFIG_FILE = """
min-event-length = 4
time-before-event = 0
threshold = 0.2
"""

# TODO: Need to generate goldens for CNT/MOG2_CUDA, as their output can differ slightly.
BASE_COMMAND_EVENT_LIST_GOLDEN = """
-------------------------------------------------------------
|   Event #    |  Start Time  |   Duration   |   End Time   |
-------------------------------------------------------------
|  Event    1  |  00:00:00.4  |  00:00:05.6  |  00:00:06.0  |
|  Event    2  |  00:00:14.3  |  00:00:05.3  |  00:00:19.6  |
|  Event    3  |  00:00:21.7  |  00:00:01.4  |  00:00:23.0  |
-------------------------------------------------------------
"""[1:]

# On some ARM chips (e.g. Apple M1), results are slightly different, so we allow a 1 frame
# delta on the events for those platforms.
BASE_COMMAND_TIMECODE_LIST_GOLDEN = (
    """
00:00:00.400,00:00:05.960,00:00:14.320,00:00:19.640,00:00:21.680,00:00:23.040
"""[1:]
    if not ("ARM" in MACHINE_ARCH or "AARCH" in MACHINE_ARCH)
    else """
00:00:00.400,00:00:06.000,00:00:14.320,00:00:19.640,00:00:21.680,00:00:23.040
"""[1:]
)


def _run_dvr_scan(args: ty.List[str]) -> str:
    """Helper to run dvr-scan with a list of arguments and return the output."""
    # Add quotes around arguments with spaces.
    processed_args = []
    for arg in args:
        processed_args.append(f'"{arg}"' if " " in str(arg) else str(arg))
    command = " ".join([DVR_SCAN_COMMAND] + processed_args)
    return subprocess.check_output(
        command,
        shell=True,
        text=True,
    )


def test_info_commands():
    """Test information commands (e.g. -h/--help)."""
    _run_dvr_scan(["--help"])
    _run_dvr_scan(["--version"])
    _run_dvr_scan(["--license"])


def test_default(tmp_path):
    """Test with all default arguments."""
    output = _run_dvr_scan(BASE_COMMAND + ["--output-dir", tmp_path])

    # Make sure the correct # of events were detected.
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output
    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."
    # TODO: Check filenames.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS


def test_concatenate(tmp_path):
    """Test with setting -o/--output to concatenate all events to a single file."""
    ouptut_file_name = "motion_events.avi"
    output = _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--output",
            ouptut_file_name,
        ]
    )

    # Make sure the correct # of events were detected.
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output
    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."
    generated_files = os.listdir(tmp_path)
    assert len(generated_files) == 1
    assert ouptut_file_name in generated_files


def test_scan_only(tmp_path):
    """Test -so/--scan-only."""
    output = _run_dvr_scan(BASE_COMMAND + ["--output-dir", tmp_path, "--scan-only"])

    # Make sure the correct # of events were detected.
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output

    # Make sure we didn't create a directory since we shouldn't write any files.
    assert len(os.listdir(tmp_path)) == 0, "Scan-only mode should not create any files."
    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


def test_quiet_mode(tmp_path):
    """Test -q/--quiet."""
    output = _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
            "--quiet",
        ]
    )
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


def test_mog2(tmp_path):
    """Test -b/--bg-subtractor MOG2 (the default)."""
    _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
        ]
    )

    # Make sure the correct # of events were detected.
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


@pytest.mark.skipif(not SubtractorCNT.is_available(), reason="CNT not available")
def test_cnt(tmp_path):
    """Test -b/--bg-subtractor CNT."""
    _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--bg-subtractor",
            "cnt",
        ]
    )
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


@pytest.mark.skipif(not SubtractorCudaMOG2.is_available(), reason="MOG2_CUDA not available")
def test_mog2_cuda(tmp_path):
    """Test -b/--bg-subtractor MOG2_CUDA."""
    _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--bg-subtractor",
            "mog2_cuda",
        ]
    )
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


def test_overlays(tmp_path):
    """Test overlays -bb/--bounding-box, --fm/--frame-metrics, and -tc/--time-code."""
    _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--bounding-box",
            "--frame-metrics",
            "--time-code",
        ]
    )
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


def test_mask_output(tmp_path):
    """Test mask output -mo/--mask-output."""
    _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
            "--mask-output",
            "mask.avi",
        ]
    )

    assert os.listdir(tmp_path) == ["mask.avi"], "Only mask file should be created with -so -mo ..."


def test_config_file(tmp_path):
    """Test using a config file to set the same parameters as in BASE_COMMAND."""
    cfg_path = os.path.join(tmp_path, "config.cfg")
    with open(cfg_path, "w") as file:
        file.write(TEST_CONFIG_FILE)

    output = _run_dvr_scan(
        BASE_COMMAND[0:4]
        + [  # Only use the input from BASE_COMMAND.
            "--output-dir",
            tmp_path,
            "--config",
            cfg_path,
        ]
    )

    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS + 1, "Incorrect amount of files."
    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


@pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")
def test_ffmpeg_mode(tmp_path):
    """Test -m/--mode ffmpeg."""
    _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--output-mode",
            "ffmpeg",
        ]
    )
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


@pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")
def test_copy_mode(tmp_path):
    """Test -m/--mode copy."""
    _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--output-mode",
            "copy",
        ]
    )
    assert len(os.listdir(tmp_path)) == BASE_COMMAND_NUM_EVENTS, "Incorrect number of events found."


def test_deprecated_roi(tmp_path):
    """Test deprecated ROI translation."""
    _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
            "-dt",
            "2",
            "-roi",
            "10 20 10 15",
            "-s",
            "roi.txt",
        ]
    )
    roi_path = os.path.join(tmp_path, "roi.txt")
    assert os.path.exists(roi_path)
    with open(roi_path) as roi_file:
        last_line_of_file = list(filter(None, roi_file.readlines()))[-1].strip()
    assert last_line_of_file == "10 20 20 20 20 35 10 35"
