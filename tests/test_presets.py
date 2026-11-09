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
"""DVR-Scan Preset Tests"""

import logging
import os
import stat

import pytest

import dvr_scan.presets as presets_module
from dvr_scan.config import (
    USER_CONFIG_FILE_PATH,
    ConfigLoadFailure,
    ConfigRegistry,
    atomic_write_text,
    set_user_config_option,
)
from dvr_scan.presets import (
    BUILTIN_PRESETS,
    DEFAULT_PRESET_NAME,
    Preset,
    is_valid_preset_name,
    list_presets,
    load_preset,
    preset_path,
    save_user_preset,
    scan_user_presets,
)
from dvr_scan.shared.settings import ScanSettings


def make_settings(**options) -> ScanSettings:
    """Create a ScanSettings with the given app settings (underscores become dashes)."""
    settings = ScanSettings(args=None, config=ConfigRegistry())
    for key, value in options.items():
        settings.set(key.replace("_", "-"), value)
    return settings


def test_save_and_load_round_trip(tmp_path):
    settings = make_settings(threshold=0.25, bg_subtractor="CNT")
    path = save_user_preset("My Camera", settings, base_dir=tmp_path)
    assert path == tmp_path / "My Camera.cfg"
    presets = scan_user_presets(tmp_path)
    assert [preset.name for preset in presets] == ["My Camera"]
    config = load_preset(presets[0])
    assert config.get("threshold") == 0.25
    assert config.get("bg-subtractor") == "CNT"


def test_save_overwrites_existing(tmp_path):
    save_user_preset("Cam", make_settings(threshold=0.25), base_dir=tmp_path)
    save_user_preset("Cam", make_settings(threshold=0.5), base_dir=tmp_path)
    (preset,) = scan_user_presets(tmp_path)
    assert load_preset(preset).get("threshold") == 0.5


def test_invalid_preset_is_skipped(tmp_path):
    save_user_preset("Valid", make_settings(threshold=0.25), base_dir=tmp_path)
    (tmp_path / "Broken.cfg").write_text("threshold = not-a-number\n")
    # Unknown options do not fail the load (#242), e.g. presets from newer versions.
    (tmp_path / "Newer.cfg").write_text("not-a-real-option = 5\n")
    presets = scan_user_presets(tmp_path)
    assert [preset.name for preset in presets] == ["Newer", "Valid"]


def test_builtin_name_collision_file_is_skipped(tmp_path):
    (tmp_path / "Fast Scan.cfg").write_text("threshold = 0.3\n")
    (tmp_path / "Default.cfg").write_text("threshold = 0.3\n")
    assert scan_user_presets(tmp_path) == []


def test_scan_missing_dir_returns_empty(tmp_path):
    assert scan_user_presets(tmp_path / "does-not-exist") == []


def test_presets_sorted_by_name(tmp_path):
    for name in ("zebra", "Alpha", "monkey"):
        save_user_preset(name, make_settings(threshold=0.25), base_dir=tmp_path)
    assert [preset.name for preset in scan_user_presets(tmp_path)] == [
        "Alpha",
        "monkey",
        "zebra",
    ]


def test_list_presets_order(tmp_path):
    save_user_preset("User Preset", make_settings(threshold=0.25), base_dir=tmp_path)
    names = [preset.name for preset in list_presets(tmp_path)]
    assert names == [DEFAULT_PRESET_NAME] + list(BUILTIN_PRESETS) + ["User Preset"]


@pytest.mark.parametrize("name", ["Cam 1", "night-mode", "Backyard (HD)", "a"])
def test_valid_preset_names(name):
    assert is_valid_preset_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "",
        " leading-space",
        "trailing-space ",
        "trailing-dot.",
        "../evil",
        "a/b",
        "a\\b",
        "caf\N{LATIN SMALL LETTER E WITH ACUTE}",
    ],
)
def test_invalid_preset_names(name):
    assert not is_valid_preset_name(name)


def test_builtin_names_are_reserved():
    for name in BUILTIN_PRESETS:
        assert not is_valid_preset_name(name)
        with pytest.raises(ValueError):
            save_user_preset(name, make_settings(threshold=0.25))


def test_default_preset_routes_to_user_config_path(tmp_path):
    assert preset_path(DEFAULT_PRESET_NAME, base_dir=tmp_path) == USER_CONFIG_FILE_PATH
    assert is_valid_preset_name(DEFAULT_PRESET_NAME)


def test_builtin_presets_validate_against_config_schema():
    """Every built-in preset must load cleanly through the real config parser."""
    for name, overrides in BUILTIN_PRESETS.items():
        preset = Preset(name=name, builtin=True, overrides=overrides)
        config = load_preset(preset)
        for option in overrides:
            assert not config.is_default(option), f"{name}: {option} not applied"


def test_load_from_string_ignores_unknown_option():
    """Unknown options must not fail the load, so config files written by newer
    versions of DVR-Scan keep working with older ones (#242)."""
    config = ConfigRegistry()
    config.load_from_string("not-a-real-option = 5\nthreshold = 0.5\n")
    # Known options in the same file must still be applied.
    assert config.get("threshold") == 0.5
    assert any(
        level == logging.WARNING and "not-a-real-option" in message
        for (level, message) in config.consume_init_log()
    )


def test_timecode_list_format_choices():
    config = ConfigRegistry()
    config.load_from_string("timecode-list-format = parts\n")
    assert config.get("timecode-list-format") == "parts"
    assert ConfigRegistry().get("timecode-list-format") == "timecodes"
    with pytest.raises(ConfigLoadFailure):
        ConfigRegistry().load_from_string("timecode-list-format = invalid\n")


def test_startup_mode_choices():
    config = ConfigRegistry()
    config.load_from_string("startup-mode = wizard\n")
    assert config.get("startup-mode") == "wizard"
    config = ConfigRegistry()
    config.load_from_string("startup-mode = advanced\n")
    assert config.get("startup-mode") == "advanced"
    # Code default is Advanced Mode so existing installs keep the full settings view; the
    # shipped config template sets wizard for fresh installs.
    assert ConfigRegistry().get("startup-mode") == "advanced"
    with pytest.raises(ConfigLoadFailure):
        ConfigRegistry().load_from_string("startup-mode = invalid\n")


@pytest.mark.parametrize("value", ["classic", "CLASSIC", "Classic"])
def test_startup_mode_legacy_classic_alias(value):
    """`classic` (the pre-release name of Advanced Mode) is accepted and normalized."""
    config = ConfigRegistry()
    config.load_from_string("startup-mode = %s\n" % value)
    assert config.get("startup-mode") == "advanced"


def test_save_default_preserves_unmanaged_options(tmp_path, monkeypatch):
    """Saving the Default preset rewrites the user config, but must keep options the UI
    has no widget for (startup-mode, verbosity, ...). UI values still win."""
    user_config = tmp_path / "dvr-scan.cfg"
    user_config.write_text(
        "startup-mode = wizard\nverbosity = debug\nsave-log = no\nthreshold = 0.9\n"
    )
    monkeypatch.setattr(presets_module, "USER_CONFIG_FILE_PATH", user_config)
    path = save_user_preset(DEFAULT_PRESET_NAME, make_settings(threshold=0.3))
    assert path == user_config
    config = ConfigRegistry()
    config.load(user_config)
    assert config.get("startup-mode") == "wizard"
    assert config.get("verbosity") == "debug"
    assert config.get("save-log") is False
    assert config.get("threshold") == 0.3
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_default_over_invalid_config_still_writes(tmp_path, monkeypatch):
    user_config = tmp_path / "dvr-scan.cfg"
    user_config.write_text("threshold = not-a-number\n")
    monkeypatch.setattr(presets_module, "USER_CONFIG_FILE_PATH", user_config)
    save_user_preset(DEFAULT_PRESET_NAME, make_settings(threshold=0.3))
    config = ConfigRegistry()
    config.load(user_config)
    assert config.get("threshold") == 0.3


def test_save_default_creates_missing_config(tmp_path, monkeypatch):
    user_config = tmp_path / "nested" / "dvr-scan.cfg"
    monkeypatch.setattr(presets_module, "USER_CONFIG_FILE_PATH", user_config)
    save_user_preset(DEFAULT_PRESET_NAME, make_settings(threshold=0.3))
    config = ConfigRegistry()
    config.load(user_config)
    assert config.get("threshold") == 0.3


def test_load_preset_logs_at_debug_level(tmp_path):
    """Preset loads should record file/string load messages at DEBUG, not INFO."""
    save_user_preset("Custom", make_settings(threshold=0.25), base_dir=tmp_path)
    for preset in list_presets(tmp_path):
        config = load_preset(preset)
        assert all(level < logging.INFO for level, _ in config.consume_init_log())


def test_scan_user_presets_warns_only_once_per_unchanged_file(tmp_path, caplog):
    broken = tmp_path / "Broken.cfg"
    broken.write_text("threshold = not-a-number\n")
    collision = tmp_path / "Default.cfg"
    collision.write_text("threshold = 0.3\n")

    with caplog.at_level(logging.WARNING, logger="dvr-scan"):
        assert scan_user_presets(tmp_path) == []
        assert len(caplog.records) == 2

        caplog.clear()
        assert scan_user_presets(tmp_path) == []
        assert len(caplog.records) == 0


def test_save_default_does_not_resurrect_cleared_ui_options(tmp_path, monkeypatch):
    """Options the UI manages come from the UI state only: an output folder cleared in
    the UI ("Ask Me") must not be brought back from the old file."""
    user_config = tmp_path / "dvr-scan.cfg"
    user_config.write_text("output-dir = C:/old\nthreshold = 0.9\nload-region = r.txt\n")
    monkeypatch.setattr(presets_module, "USER_CONFIG_FILE_PATH", user_config)
    save_user_preset(DEFAULT_PRESET_NAME, make_settings(threshold=0.3))
    text = user_config.read_text()
    assert "output-dir" not in text
    assert "load-region" not in text
    assert "threshold = 0.3" in text


def test_save_default_preserves_validated_unknown_and_raw_values(tmp_path, monkeypatch):
    user_config = tmp_path / "dvr-scan.cfg"
    user_config.write_text(
        "max-event-length = 30s\n"
        "future-option = 5\n"
        "timecode = yes\n"  # migrated name: dropped, the UI writes time-code
        "region-of-interest = 0 0 10 10\n"  # deprecated: dropped
        "verbosity = DEBUG\n"
    )
    monkeypatch.setattr(presets_module, "USER_CONFIG_FILE_PATH", user_config)
    save_user_preset(DEFAULT_PRESET_NAME, make_settings(threshold=0.3))
    text = user_config.read_text()
    assert "max-event-length = 30s\n" in text
    assert "future-option = 5\n" in text
    assert "verbosity = DEBUG\n" in text
    assert "timecode" not in text.replace("time-code", "")
    assert "region-of-interest" not in text
    config = ConfigRegistry()
    config.load(user_config)
    assert config.get("max-event-length") == "30s"


#
# Config file encoding and atomic writes
#

# U+0441 CYRILLIC SMALL LETTER ES in UTF-8. The 0x81 byte is undefined in cp1252, so
# decoding this file in the Windows locale encoding fails.
CYRILLIC_UTF8 = b"\xd1\x81"


def test_preset_with_non_ascii_utf8_text_loads(tmp_path):
    (tmp_path / "Camera.cfg").write_bytes(b"# Front door " + CYRILLIC_UTF8 + b"\nthreshold = 0.3\n")
    (preset,) = scan_user_presets(tmp_path)
    assert load_preset(preset).get("threshold") == 0.3


def test_config_with_utf8_bom_loads_first_option(tmp_path):
    path = tmp_path / "bom.cfg"
    path.write_bytes(b"\xef\xbb\xbfthreshold = 0.42\r\nmin-event-length = 3\r\n")
    config = ConfigRegistry()
    config.load(path)
    assert config.get("threshold") == 0.42
    assert config.get("min-event-length") == "3"


def test_config_falls_back_to_locale_encoding(tmp_path, monkeypatch):
    monkeypatch.setattr("locale.getpreferredencoding", lambda do_setlocale=True: "cp1252")
    path = tmp_path / "legacy.cfg"
    path.write_bytes(b"output-dir = C:/Users/Jos\xe9\n")
    config = ConfigRegistry()
    config.load(path)
    assert config.get("output-dir") == "C:/Users/Jos\N{LATIN SMALL LETTER E WITH ACUTE}"


def test_undecodable_config_is_a_load_failure(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr("locale.getpreferredencoding", lambda do_setlocale=True: "ascii")
    path = tmp_path / "Broken.cfg"
    path.write_bytes(b"threshold = 0.3\n# \x81\n")
    with pytest.raises(ConfigLoadFailure):
        ConfigRegistry().load(path)
    # Presets that cannot be decoded are skipped with a warning instead of raising.
    with caplog.at_level(logging.WARNING, logger="dvr_scan"):
        assert scan_user_presets(tmp_path) == []
    assert any("Broken.cfg" in record.getMessage() for record in caplog.records)


def test_save_user_preset_writes_utf8(tmp_path):
    settings = make_settings(output_dir="C:/Videos/" + CYRILLIC_UTF8.decode("utf-8"))
    path = save_user_preset("Unicode", settings, base_dir=tmp_path)
    assert CYRILLIC_UTF8 in path.read_bytes()
    assert load_preset(scan_user_presets(tmp_path)[0]).get("output-dir") == (
        "C:/Videos/" + CYRILLIC_UTF8.decode("utf-8")
    )


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_atomic_write_keeps_newline_style(tmp_path, newline):
    path = tmp_path / "dvr-scan.cfg"
    path.write_bytes(b"threshold = 0.5" + newline)
    atomic_write_text(path, "threshold = 0.6\nmin-event-length = 3\n")
    assert path.read_bytes() == b"threshold = 0.6" + newline + b"min-event-length = 3" + newline


def test_set_user_config_option_keeps_lf_file(tmp_path):
    path = tmp_path / "dvr-scan.cfg"
    path.write_bytes(b"threshold = 0.5\nstartup-mode = wizard\n")
    set_user_config_option("startup-mode", "advanced", path)
    assert path.read_bytes() == b"threshold = 0.5\nstartup-mode = advanced\n"


def test_atomic_write_read_only_file(tmp_path):
    """Replacing a read-only file must raise the real error and leave no temp file."""
    path = tmp_path / "dvr-scan.cfg"
    path.write_text("threshold = 0.5\n")
    os.chmod(path, stat.S_IREAD)
    try:
        if os.name == "nt":
            with pytest.raises(PermissionError) as excinfo:
                atomic_write_text(path, "threshold = 0.6\n")
            # The error is from replacing the file (tmp -> path), not the cleanup.
            assert excinfo.value.filename2 == str(path)
            assert path.read_text() == "threshold = 0.5\n"
        else:
            # POSIX allows replacing a read-only file; its mode bits are kept.
            atomic_write_text(path, "threshold = 0.6\n")
            assert path.read_text() == "threshold = 0.6\n"
            assert stat.S_IMODE(path.stat().st_mode) == stat.S_IREAD
        assert list(tmp_path.glob("*.tmp")) == []
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
