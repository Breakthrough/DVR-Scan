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

import pytest

from dvr_scan.config import USER_CONFIG_FILE_PATH, ConfigLoadFailure, ConfigRegistry
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


def test_unknown_option_preset_is_skipped(tmp_path):
    save_user_preset("Valid", make_settings(threshold=0.25), base_dir=tmp_path)
    (tmp_path / "Broken.cfg").write_text("not-a-real-option = 5\n")
    presets = scan_user_presets(tmp_path)
    assert [preset.name for preset in presets] == ["Valid"]


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


def test_load_from_string_rejects_unknown_option():
    with pytest.raises(ConfigLoadFailure):
        ConfigRegistry().load_from_string("not-a-real-option = 5\n")


def test_startup_mode_choices():
    config = ConfigRegistry()
    config.load_from_string("startup-mode = classic\n")
    assert config.get("startup-mode") == "classic"
    assert ConfigRegistry().get("startup-mode") == "wizard"
    with pytest.raises(ConfigLoadFailure):
        ConfigRegistry().load_from_string("startup-mode = invalid\n")
