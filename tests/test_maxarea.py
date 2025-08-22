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
"""DVR-Scan Max-Area Tests

Tests parameters max-area, max-height, max-width
"""

import os
import subprocess
import typing as ty

DVR_SCAN_COMMAND: str = "python -m dvr_scan"
BASE_OUTPUT_NAME: str = "haze"
# Should yield 3 events with all detector types.
BASE_COMMAND = [
    "--input",
    "tests/resources/haze.mp4",
    "-t",
    "0.225",
    "-l",
    "3",
    "-df",
    "4",
    "-bb",
    "-fm",
    "--add-region",
    "0 99 1920 99 1920 1080 0 1080",
    "--add-region",
    "0 0 1440 0 1440 99 0 99",
]
BASE_COMMAND_NUM_EVENTS = 2

TEST_CONFIG_FILE = """
max-area = 0.16
max-height = 0.4
"""

BASE_COMMAND_EVENT_LIST_GOLDEN = """
-------------------------------------------------------------
|   Event #    |  Start Time  |   Duration   |   End Time   |
-------------------------------------------------------------
|  Event    1  |  00:00:08.2  |  00:00:23.9  |  00:00:32.1  |
|  Event    2  |  00:00:33.1  |  00:00:05.8  |  00:00:38.9  |
-------------------------------------------------------------
"""[1:]

# On some ARM chips (e.g. Apple M1), results are slightly different, so we allow a 1 frame
# delta on the events for those platforms.
BASE_COMMAND_TIMECODE_LIST_GOLDEN = """
00:00:08.229,00:00:32.113,00:00:33.117,00:00:38.937
"""[1:]


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


def test_scan_haze(tmp_path):
    """Test haze video without max-area filter"""
    output = _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
        ]
    )

    # Make sure the correct # of events were detected.
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output

    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


def test_scan_haze_maxarea(tmp_path):
    """Test haze video with max-area/max-height filter"""
    cfg_path = os.path.join(tmp_path, "config.cfg")
    with open(cfg_path, "w") as file:
        file.write(TEST_CONFIG_FILE)
    output = _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
            "--config",
            cfg_path,
        ]
    )

    # Make sure the correct # of events were detected.
    assert "No motion events detected in input." in output
