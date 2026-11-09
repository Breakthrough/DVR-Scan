#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2026 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""Tests for application startup mode selection (wizard vs. Advanced Mode) and the config
file line editor behind it. All Tk-free."""

import pytest

from dvr_scan.app.__main__ import get_cli_parser
from dvr_scan.app.startup import (
    ADVANCED,
    CLASSIC,
    WIZARD,
    has_prior_logs,
    normalize_startup_mode,
    resolve_default_startup_mode,
    save_startup_mode,
)
from dvr_scan.config import ConfigLoadFailure, ConfigRegistry, set_user_config_option

TEMPLATE = """# DVR-Scan Config File
# Some comment that must survive.

#startup-mode = WIZARD

# Detection threshold.
threshold = 0.5
"""


def _config(contents: str = "") -> ConfigRegistry:
    config = ConfigRegistry()
    if contents:
        config.load_from_string(contents)
    return config


#
# set_user_config_option
#


def test_set_option_replaces_commented_line(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_text(TEMPLATE)
    assert set_user_config_option("startup-mode", "advanced", path) == path
    text = path.read_text()
    assert "startup-mode = advanced\n" in text
    assert "#startup-mode" not in text
    # Everything else is untouched.
    assert "# Some comment that must survive.\n" in text
    assert "# Detection threshold.\nthreshold = 0.5\n" in text
    assert text.count("startup-mode") == 1


def test_set_option_replaces_active_line(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_text("startup-mode = advanced\nthreshold = 0.5\n")
    set_user_config_option("startup-mode", "wizard", path)
    assert path.read_text() == "startup-mode = wizard\nthreshold = 0.5\n"


def test_set_option_prefers_active_over_commented_line(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_text("#startup-mode = WIZARD\nstartup-mode = advanced\n")
    set_user_config_option("startup-mode", "wizard", path)
    assert path.read_text() == "#startup-mode = WIZARD\nstartup-mode = wizard\n"


def test_set_option_appends_when_absent(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_text("threshold = 0.5\n")
    set_user_config_option("startup-mode", "wizard", path)
    assert path.read_text() == "threshold = 0.5\n\nstartup-mode = wizard\n"


def test_set_option_creates_missing_file_with_header(tmp_path):
    path = tmp_path / "nested" / "dvr-scan.cfg"
    set_user_config_option("startup-mode", "wizard", path)
    lines = path.read_text().splitlines()
    assert lines[0].startswith("# DVR-Scan Config File")
    assert lines[1].startswith("# Created by: DVR-Scan")
    assert lines[-1] == "startup-mode = wizard"
    assert list(path.parent.glob("*.tmp")) == []


def test_set_option_result_loads_cleanly(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_text(TEMPLATE)
    set_user_config_option("startup-mode", "advanced", path)
    config = ConfigRegistry()
    config.load(path)
    assert config.get("startup-mode") == "advanced"
    assert config.get("threshold") == 0.5


def test_set_option_does_not_match_similar_option_names(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_text("max-log-size = 1\n")
    set_user_config_option("max-log-files", "3", path)
    assert path.read_text() == "max-log-size = 1\n\nmax-log-files = 3\n"


#
# save_startup_mode
#


def test_save_startup_mode_lowercases_and_validates(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    save_startup_mode("Wizard", path)
    assert "startup-mode = wizard" in path.read_text()
    with pytest.raises(ValueError):
        save_startup_mode("sideways", path)


def test_save_startup_mode_writes_legacy_classic_as_advanced(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    save_startup_mode("Classic", path)
    assert "startup-mode = advanced" in path.read_text()
    config = ConfigRegistry()
    config.load(path)
    assert config.get("startup-mode") == ADVANCED


@pytest.mark.parametrize(
    "value,expected",
    [
        ("wizard", WIZARD),
        (" Wizard ", WIZARD),
        ("advanced", ADVANCED),
        ("ADVANCED", ADVANCED),
        ("classic", ADVANCED),
        ("Classic", ADVANCED),
        ("sideways", "sideways"),
    ],
)
def test_normalize_startup_mode(value, expected):
    assert normalize_startup_mode(value) == expected


def test_classic_constant_is_advanced():
    assert CLASSIC == ADVANCED == "advanced"


#
# has_prior_logs
#


def test_has_prior_logs_missing_or_empty_dir(tmp_path):
    assert has_prior_logs(tmp_path / "missing") is False
    assert has_prior_logs(tmp_path) is False


def test_has_prior_logs_ignores_current_log_file(tmp_path):
    current = tmp_path / "dvr-scan-app.abc123.log"
    current.write_text("")
    assert has_prior_logs(tmp_path, exclude=current) is False
    assert has_prior_logs(tmp_path) is True


@pytest.mark.parametrize(
    "name", ["dvr-scan-app.log", "dvr-scan.log", "dvr-scan-app.x1y2z3.log", "dvr-scan.q.log"]
)
def test_has_prior_logs_matches_current_and_legacy_names(tmp_path, name):
    current = tmp_path / "dvr-scan-app.current.log"
    current.write_text("")
    (tmp_path / name).write_text("")
    assert has_prior_logs(tmp_path, exclude=current) is True


def test_has_prior_logs_ignores_unrelated_files(tmp_path):
    (tmp_path / "other.log").write_text("")
    (tmp_path / "dvr-scan.txt").write_text("")
    assert has_prior_logs(tmp_path) is False


#
# resolve_default_startup_mode
#


@pytest.mark.parametrize("value", ["wizard", "WIZARD", "Wizard"])
def test_resolve_explicit_config_value_wins(value):
    config = _config(f"startup-mode = {value}\n")
    for user_config_exists in (True, False):
        for prior_logs in (True, False):
            assert resolve_default_startup_mode(
                config, user_config_exists, prior_logs, allow_heuristic=True
            ) == (WIZARD, False)


def test_resolve_existing_config_without_option_is_advanced():
    assert resolve_default_startup_mode(
        _config(), user_config_exists=True, prior_logs=False, allow_heuristic=True
    ) == (CLASSIC, False)


def test_resolve_heuristic_new_user_is_wizard_and_persists():
    assert resolve_default_startup_mode(
        _config(), user_config_exists=False, prior_logs=False, allow_heuristic=True
    ) == (WIZARD, True)


def test_resolve_heuristic_existing_user_is_advanced_and_persists():
    assert resolve_default_startup_mode(
        _config(), user_config_exists=False, prior_logs=True, allow_heuristic=True
    ) == (CLASSIC, True)


@pytest.mark.parametrize("value", ["advanced", "Advanced", "classic", "CLASSIC"])
def test_resolve_explicit_advanced_or_legacy_classic(value):
    config = _config(f"startup-mode = {value}\n")
    assert resolve_default_startup_mode(
        config, user_config_exists=True, prior_logs=False, allow_heuristic=True
    ) == (ADVANCED, False)


def test_resolve_heuristic_disabled_falls_back_to_default():
    assert resolve_default_startup_mode(
        _config(), user_config_exists=False, prior_logs=False, allow_heuristic=False
    ) == (CLASSIC, False)


#
# --startup-mode CLI option
#


@pytest.mark.parametrize(
    "value,expected",
    [("wizard", WIZARD), ("Advanced", ADVANCED), ("advanced", ADVANCED), ("Classic", ADVANCED)],
)
def test_cli_startup_mode_option(value, expected):
    # The legacy name "classic" is still accepted, as an alias of "advanced".
    args = get_cli_parser().parse_args(["--startup-mode", value])
    assert args.startup_mode == expected


def test_cli_startup_mode_absent_by_default():
    assert not hasattr(get_cli_parser().parse_args([]), "startup_mode")


def test_cli_startup_mode_rejects_invalid():
    with pytest.raises(SystemExit):
        get_cli_parser().parse_args(["--startup-mode", "sideways"])


#
# set_user_config_option: review follow-ups
#


def test_set_option_matches_key_case_insensitively(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_text("STARTUP-MODE = WIZARD\nthreshold = 0.5\n")
    set_user_config_option("startup-mode", "advanced", path)
    assert path.read_text() == "startup-mode = advanced\nthreshold = 0.5\n"
    config = ConfigRegistry()
    config.load(path)
    assert config.get("startup-mode") == "advanced"


def test_set_option_replaces_multiline_value(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_text("startup-mode =\n    wizard\n\tmore\nthreshold = 0.5\n")
    set_user_config_option("startup-mode", "advanced", path)
    assert path.read_text() == "startup-mode = advanced\nthreshold = 0.5\n"


def test_set_option_keeps_utf8_bom_file_as_utf8(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_bytes(b"\xef\xbb\xbfstartup-mode = wizard\noutput-dir = C:/caf\xc3\xa9\n")
    set_user_config_option("startup-mode", "advanced", path)
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.count(b"startup-mode") == 1
    # Text mode writes platform newlines (CRLF on Windows); compare on normalized text.
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    assert "startup-mode = advanced\n" in text
    assert "output-dir = C:/caf\u00e9\n" in text


def test_set_option_round_trips_locale_encoded_text(tmp_path):
    """Read and write use the locale encoding like ConfigRegistry.load, so non-ASCII
    values written by the app survive a startup-mode toggle."""
    path = tmp_path / "dvr-scan.cfg"
    path.write_text("output-dir = C:/Users/Jos\u00e9/Videos\n")
    set_user_config_option("startup-mode", "advanced", path)
    assert path.read_text() == "output-dir = C:/Users/Jos\u00e9/Videos\n\nstartup-mode = advanced\n"
    config = ConfigRegistry()
    config.load(path)
    assert config.get("output-dir") == "C:/Users/Jos\u00e9/Videos"


def test_duplicate_option_is_a_config_load_failure():
    with pytest.raises(ConfigLoadFailure):
        ConfigRegistry().load_from_string("threshold = 0.5\nthreshold = 0.6\n")
