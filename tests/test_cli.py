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

import csv
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import typing as ty

import pytest
from scenedetect import is_ffmpeg_available

from dvr_scan.cli import get_cli_parser
from dvr_scan.config import ConfigRegistry
from dvr_scan.shared.settings import ScanSettings

# We need to import the OpenCV loader before PySceneDetect as the latter imports OpenCV.
from dvr_scan.subtractor import SubtractorCNT, SubtractorCudaMOG2

MACHINE_ARCH = platform.machine().upper()

# TODO: Open extracted motion events and validate the actual frames.

# Run the CLI with the interpreter running the tests, not whichever `python` is on PATH
# (they differ when pytest runs from a separate build venv).
DVR_SCAN_COMMAND: str = f'"{sys.executable}" -m dvr_scan'
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

# On ARM chips (e.g. Apple M1), detection near the threshold differs by one frame from
# x86, so the first event's boundaries use a separate golden (values taken from the
# macos-14 CI runner).
# NOTE: The first event starts one frame earlier than in earlier releases (v2.0 decodes
# via PyAV by default, whose colorspace conversion differs slightly from OpenCV's, which
# can shift detection near the threshold by a frame).
BASE_COMMAND_TIMECODE_LIST_GOLDEN = (
    """
00:00:00.360,00:00:05.960,00:00:14.320,00:00:19.640,00:00:21.680,00:00:23.040
"""[1:]
    if not ("ARM" in MACHINE_ARCH or "AARCH" in MACHINE_ARCH)
    else """
00:00:00.400,00:00:05.960,00:00:14.320,00:00:19.640,00:00:21.680,00:00:23.040
"""[1:]
)


def _run_dvr_scan(args: ty.List[str]) -> str:
    """Helper to run dvr-scan with a list of arguments and return the output."""
    # Add quotes around arguments with spaces or glob metacharacters so the shell does not
    # split or expand them.
    processed_args = []
    for arg in args:
        needs_quotes = any(char in str(arg) for char in " []*?")
        processed_args.append(f'"{arg}"' if needs_quotes else str(arg))
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
    generated_files = os.listdir(tmp_path)
    assert len(generated_files) == BASE_COMMAND_NUM_EVENTS
    # The default output mode produces mp4 when ffmpeg is present, .avi otherwise.
    expected_extension = ".mp4" if is_ffmpeg_available() else ".avi"
    assert all(name.endswith(expected_extension) for name in generated_files)


def test_concatenate(tmp_path):
    """Test with setting -o/--output to concatenate all events to a single file.

    The output name is given without an extension; one must be appended based on the
    effective output mode (.mp4 for the default mode when ffmpeg is present)."""
    output = _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--output",
            "motion_events",
        ]
    )

    # Make sure the correct # of events were detected.
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output
    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."
    generated_files = os.listdir(tmp_path)
    assert len(generated_files) == 1
    expected_extension = "mp4" if is_ffmpeg_available() else "avi"
    assert "motion_events." + expected_extension in generated_files


def test_concatenate_opencv(tmp_path):
    """Test -o/--output with the legacy OpenCV output mode."""
    output = _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--output-mode",
            "opencv",
            "--output",
            "motion_events.avi",
        ]
    )
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output
    generated_files = os.listdir(tmp_path)
    assert generated_files == ["motion_events.avi"]


def test_report(tmp_path):
    """Test --report with both output formats, in scan-only mode with a relative path
    (which must be resolved against -d/--output-dir)."""
    golden_timecodes = _golden_event_pairs()
    _run_dvr_scan(
        BASE_COMMAND + ["--output-dir", tmp_path, "--scan-only", "--report", "report.csv"]
    )
    with open(tmp_path / "report.csv", newline="") as file:
        rows = list(csv.reader(file))
    assert len(rows) == 1 + BASE_COMMAND_NUM_EVENTS
    assert [row[0] for row in rows[1:]] == [
        str(number + 1) for number in range(BASE_COMMAND_NUM_EVENTS)
    ]
    # The CSV timecodes use 1 decimal place of precision (rounded), so only compare the
    # exact-seconds column against the golden timecode of the first event.
    golden_start_seconds = float(golden_timecodes[0][0][len("00:00:") :])
    assert float(rows[1][6]) == pytest.approx(golden_start_seconds)

    _run_dvr_scan(
        BASE_COMMAND + ["--output-dir", tmp_path, "--scan-only", "--report", "report.json"]
    )
    with open(tmp_path / "report.json") as file:
        report = json.load(file)
    assert report["scan"]["num_events"] == BASE_COMMAND_NUM_EVENTS
    assert len(report["events"]) == BASE_COMMAND_NUM_EVENTS
    # Event boundaries must match the golden timecodes printed by the CLI.
    reported = [
        (event["start"]["timecode"], event["end"]["timecode"]) for event in report["events"]
    ]
    assert reported == golden_timecodes


def test_report_rejects_unknown_format(tmp_path):
    """--report with an unsupported extension must fail before scanning."""
    with pytest.raises(subprocess.CalledProcessError):
        _run_dvr_scan(
            BASE_COMMAND + ["--output-dir", tmp_path, "--scan-only", "--report", "report.txt"]
        )


def test_scan_only(tmp_path):
    """Test -so/--scan-only."""
    output = _run_dvr_scan(BASE_COMMAND + ["--output-dir", tmp_path, "--scan-only"])

    # Make sure the correct # of events were detected.
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output

    # Make sure we didn't create a directory since we shouldn't write any files.
    assert len(os.listdir(tmp_path)) == 0, "Scan-only mode should not create any files."
    assert BASE_COMMAND_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


def test_input_path_with_glob_characters(tmp_path):
    """Input filenames containing glob metacharacters must be used as-is (#171)."""
    video = tmp_path / "00.08.00-00.16.00[R][0@0][0].mp4"
    shutil.copy("tests/resources/traffic_camera.mp4", video)
    output = _run_dvr_scan(["--input", video] + BASE_COMMAND[2:] + ["--scan-only"])
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


def test_input_glob_expansion(tmp_path):
    """Wildcards in input paths (including absolute paths and `**`) are expanded, sorted
    by filename regardless of case, and directories matched by a wildcard are ignored."""
    (tmp_path / "sub").mkdir()
    for name in ("b.mp4", "A.mp4", "sub/c.mp4"):
        shutil.copy("tests/resources/traffic_camera.mp4", tmp_path / name)
    (tmp_path / "ignored.mp4").mkdir()
    output = _run_dvr_scan(
        ["--input", tmp_path / "**" / "*.mp4"]
        + BASE_COMMAND[2:]
        + ["--scan-only", "--verbosity", "debug"]
    )
    # All three inputs must be opened in order. (The exact number of events is not asserted
    # since the events at the seams between the inputs are merged.)
    assert "Opened video A.mp4" in output
    assert output.index("Appending video b.mp4") < output.index("Appending video c.mp4")
    assert output.index("Opened video A.mp4") < output.index("Appending video b.mp4")
    assert "ignored.mp4" not in output
    match = re.search(r"Detected (\d+) motion events in input.", output)
    assert match is not None and int(match.group(1)) > BASE_COMMAND_NUM_EVENTS


def test_input_does_not_exist(tmp_path):
    """A missing input path (with or without wildcards) must fail with an error."""
    for missing in (tmp_path / "missing.mp4", tmp_path / "*.mp4"):
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            _run_dvr_scan(["--input", missing] + BASE_COMMAND[2:] + ["--scan-only"])
        assert "Input file does not exist" in excinfo.value.output


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


def _golden_event_pairs() -> ty.List[ty.Tuple[str, str]]:
    """Split the golden timecode list (`start,end,start,end,...`) into (start, end) pairs."""
    timecodes = BASE_COMMAND_TIMECODE_LIST_GOLDEN.strip().split(",")
    return list(zip(timecodes[0::2], timecodes[1::2], strict=True))


@pytest.mark.parametrize(
    "list_format,expected",
    [
        ("parts", lambda pairs: ",".join("%s-%s" % pair for pair in pairs)),
        ("timecodes", lambda pairs: ",".join(timecode for pair in pairs for timecode in pair)),
        ("lines", lambda pairs: "\n".join("%s-%s" % pair for pair in pairs)),
    ],
)
def test_timecode_list_format(tmp_path, list_format, expected):
    """Test the `timecode-list-format` config option in quiet mode (#78)."""
    cfg_path = tmp_path / "config.cfg"
    cfg_path.write_text("timecode-list-format = %s\n" % list_format)
    output = _run_dvr_scan(BASE_COMMAND + ["--scan-only", "--quiet", "--config", str(cfg_path)])
    assert output.strip().splitlines() == expected(_golden_event_pairs()).splitlines()


def test_max_events(tmp_path):
    """Test --max-events stops the scan after the given number of events (#261)."""
    output = _run_dvr_scan(
        BASE_COMMAND + ["--output-dir", tmp_path, "--scan-only", "--max-events", "1"]
    )
    assert "Detected 1 motion events in input." in output


def test_logfile_contains_timecodes(tmp_path):
    """The comma-separated timecode list must be written to log files, including in
    quiet mode where they are also printed to stdout (#265)."""
    logfile = tmp_path / "log.txt"
    output = _run_dvr_scan(BASE_COMMAND + ["--scan-only", "--quiet", "--logfile", str(logfile)])
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN in output, "Timecodes missing from stdout."
    assert BASE_COMMAND_TIMECODE_LIST_GOLDEN.strip() in logfile.read_text(), (
        "Timecodes missing from log file."
    )


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


def test_merge_window(tmp_path):
    """--merge-window must combine groups of motion which occur close together (#195)."""
    output = _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
            "--time-post-event",
            "10",
            "--merge-window",
            "120",
        ]
    )
    assert "Detected 2 motion events in input." in output


def test_merge_window_auto(tmp_path):
    """--merge-window auto must be accepted, matching the default merge behavior."""
    output = _run_dvr_scan(
        BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
            "--max-events",
            "1",
            "--merge-window",
            "auto",
        ]
    )
    assert "Detected 1 motion events in input." in output


def test_merge_window_config_file(tmp_path):
    """merge-window must also be settable from a config file."""
    cfg_path = os.path.join(tmp_path, "config.cfg")
    with open(cfg_path, "w") as file:
        file.write(TEST_CONFIG_FILE + "time-post-event = 10\nmerge-window = 120\n")
    output = _run_dvr_scan(
        BASE_COMMAND[0:4]
        + [  # Only use the input from BASE_COMMAND.
            "--output-dir",
            tmp_path,
            "--scan-only",
            "--config",
            cfg_path,
        ]
    )
    assert "Detected 2 motion events in input." in output


def test_merge_window_rejects_invalid_value(tmp_path):
    """Values other than auto or a valid timecode must be rejected."""
    with pytest.raises(subprocess.CalledProcessError):
        _run_dvr_scan(
            BASE_COMMAND + ["--output-dir", tmp_path, "--scan-only", "--merge-window", "invalid"]
        )


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


HAZE_BASE_COMMAND = [
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
    "--ignore-user-config",
]
HAZE_NUM_EVENTS = 2

HAZE_MAXAREA_CONFIG = """
max-area = 0.16
max-height = 0.4
"""

HAZE_EVENT_LIST_GOLDEN = """
-------------------------------------------------------------
|   Event #    |  Start Time  |   Duration   |   End Time   |
-------------------------------------------------------------
|  Event    1  |  00:00:08.2  |  00:00:23.9  |  00:00:32.1  |
|  Event    2  |  00:00:33.1  |  00:00:05.8  |  00:00:38.9  |
-------------------------------------------------------------
"""[1:]

# NOTE: Event boundaries are exact PTS values (v2.0); some timecodes differ by 1ms from
# earlier releases, which quantized event times to whole frames before formatting.
HAZE_TIMECODE_LIST_GOLDEN = """
00:00:08.229,00:00:32.114,00:00:33.117,00:00:38.938
"""[1:]


def test_scan_haze(tmp_path):
    """Test haze video without max-area filter (#224)."""
    output = _run_dvr_scan(
        HAZE_BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
        ]
    )

    assert "Detected %d motion events in input." % (HAZE_NUM_EVENTS) in output
    assert HAZE_EVENT_LIST_GOLDEN in output, "Output event list does not match test golden."
    assert HAZE_TIMECODE_LIST_GOLDEN in output, "Output timecodes do not match test golden."


def test_scan_haze_maxarea(tmp_path):
    """Test haze video with max-area/max-height filter (#224)."""
    cfg_path = os.path.join(tmp_path, "config.cfg")
    with open(cfg_path, "w") as file:
        file.write(HAZE_MAXAREA_CONFIG)
    output = _run_dvr_scan(
        HAZE_BASE_COMMAND
        + [
            "--output-dir",
            tmp_path,
            "--scan-only",
            "--config",
            cfg_path,
        ]
    )

    assert "No motion events detected in input." in output


#
# Option defaults, validation, and error reporting (2.0 release fixes)
#


def _parse_cli(args: ty.List[str], config_text: str = "") -> ScanSettings:
    """Parse `args` in-process with a config containing `config_text`."""
    config = ConfigRegistry()
    if config_text:
        config.load_from_string(config_text)
    return ScanSettings(args=get_cli_parser(config).parse_args(args), config=config)


def test_flags_do_not_override_config_when_absent():
    """Flags not given on the command line must not shadow their config file values."""
    settings = _parse_cli(["-i", "video.mp4"], "scan-only = yes\ndebug = yes\n")
    assert settings.get("scan-only") is True
    assert settings.get("debug") is True
    settings = _parse_cli(["-i", "video.mp4"])
    assert settings.get("scan-only") is False
    assert settings.get("debug") is False
    assert _parse_cli(["-i", "video.mp4", "-so"]).get("scan-only") is True


def test_scan_only_from_config_file(tmp_path):
    """`scan-only = yes` in a config file enables scan-only mode without -so."""
    cfg_path = tmp_path / "config.cfg"
    cfg_path.write_text("scan-only = yes\n")
    output_dir = tmp_path / "output"
    output = _run_dvr_scan(BASE_COMMAND + ["--config", cfg_path, "--output-dir", output_dir])
    assert "Detected %d motion events in input." % (BASE_COMMAND_NUM_EVENTS) in output
    assert not output_dir.exists() or not os.listdir(output_dir)


def test_thumbnails_option_validation():
    assert _parse_cli(["-i", "video.mp4", "--thumbnails", "HighScore"]).get("thumbnails") == (
        "highscore"
    )
    assert _parse_cli(["-i", "video.mp4"]).get("thumbnails") is None
    with pytest.raises(SystemExit):
        _parse_cli(["-i", "video.mp4", "--thumbnails", "lowscore"])


def test_report_unwritable_path_fails_before_scan(tmp_path):
    """An unwritable --report path is rejected up front with a message, not a traceback."""
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("")
    result = subprocess.run(
        " ".join(
            [DVR_SCAN_COMMAND]
            + BASE_COMMAND
            + ["--scan-only", "--report", '"%s"' % (not_a_dir / "report.csv")]
        ),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert result.returncode == 1
    assert "cannot write report file" in result.stdout
    assert "Traceback" not in result.stdout
    assert "Detected" not in result.stdout, "Report path must be checked before scanning."


def test_report_check_does_not_leave_file_behind(tmp_path):
    from dvr_scan.controller import _check_report_path

    report = tmp_path / "out" / "report.json"
    _check_report_path(_parse_cli(["-i", "video.mp4", "--report", str(report)]))
    assert report.parent.is_dir()
    assert not report.exists()


@pytest.mark.parametrize("error", [OSError("disk full"), RuntimeError("ffmpeg exited with code 1")])
def test_main_logs_io_errors_without_traceback(monkeypatch, caplog, error):
    """OSError/RuntimeError (e.g. ffmpeg failing to write output) are reported as a
    message only, unless running with debug verbosity."""
    import dvr_scan.__main__ as main_module

    settings = _parse_cli(["-i", "video.mp4", "--quiet"])

    def _raise(_settings):
        raise error

    monkeypatch.setattr(main_module, "parse_settings", lambda: settings)
    monkeypatch.setattr(main_module, "run_dvr_scan", _raise)
    with caplog.at_level(logging.DEBUG, logger="dvr_scan"):
        with pytest.raises(SystemExit) as excinfo:
            main_module.main()
    assert excinfo.value.code == 1
    (record,) = [record for record in caplog.records if record.levelno == logging.CRITICAL]
    assert str(error) in record.getMessage()
    assert not record.exc_info


@pytest.mark.parametrize("regions", [[], ["631 532 841 532 841 659 631 659"]])
def test_save_region_writes_scanned_area(tmp_path, regions):
    """`-s/--save-region` writes the regions that were scanned: the ones given with
    `-a/--add-region`, or the full frame when no regions were set."""
    from dvr_scan.region import Point, load_regions

    region_file = tmp_path / "regions.txt"
    args = ["--input", "tests/resources/traffic_camera.mp4", "--ignore-user-config"]
    args += ["--scan-only", "--end-time", "00:00:01", "--save-region", region_file]
    for region in regions:
        args += ["--add-region", region]
    _run_dvr_scan(args)

    saved = load_regions(region_file)
    if regions:
        assert saved == [[Point(631, 532), Point(841, 532), Point(841, 659), Point(631, 659)]]
    else:
        assert saved == [[Point(0, 0), Point(1279, 0), Point(1279, 719), Point(0, 719)]]
