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

"""Preset management for DVR-Scan.

A preset is a named set of configuration values that can be applied all at once.
User presets are plain config files stored in a ``presets`` directory inside the
user config folder; the filename (without extension) is the preset name. Built-in
presets are defined in code so they work in all distributions without requiring
packaged data files. The special ``Default`` preset maps to the user config file
itself (USER_CONFIG_FILE_PATH).
"""

import logging
import re
import typing as ty
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from dvr_scan.config import USER_CONFIG_FILE_PATH, ConfigLoadFailure, ConfigRegistry

if ty.TYPE_CHECKING:
    from dvr_scan.shared.settings import ScanSettings

logger = logging.getLogger("dvr_scan")

PRESETS_DIR_NAME = "presets"
PRESET_SUFFIX = ".cfg"
DEFAULT_PRESET_NAME = "Default"

# Restrict user preset names to filesystem-safe ASCII. Windows also strips
# trailing dots/spaces from filenames, so we disallow those explicitly.
_VALID_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-().]*[A-Za-z0-9_\-()]$|^[A-Za-z0-9]$")


@dataclass(frozen=True)
class Preset:
    """A named set of configuration values which can be applied to the UI.

    Exactly one of `path` (Default/user presets) or `overrides` (built-ins) is set.
    """

    name: str
    builtin: bool
    path: ty.Optional[Path] = None
    overrides: ty.Optional[ty.Dict[str, str]] = None

    def __post_init__(self):
        if (self.path is None) == (self.overrides is None):
            raise ValueError("exactly one of `path` or `overrides` must be set")


# OrderedDict (rather than a plain dict) documents that iteration order is the intended
# display order of the built-in presets in the UI.
# TODO: Revisit these values with user feedback. Baseline program defaults:
# threshold 0.15, min-event-length 0.1s, variance-threshold 16, MOG2,
# no frame skip or downscaling.
BUILTIN_PRESETS: ty.OrderedDict[str, ty.Dict[str, str]] = OrderedDict(
    [
        (
            # Catch faint/small motion: half the default threshold, a small fixed
            # noise-filter kernel (auto can pick larger kernels at high resolutions,
            # which suppresses small objects), and generous context around events.
            "High Sensitivity",
            {
                "threshold": "0.075",
                "kernel-size": "3",
                "time-before-event": "2.0s",
                "time-post-event": "3.0s",
            },
        ),
        (
            # Only sustained, significant motion: higher score threshold, longer
            # minimum event length, and a stricter MOG2 variance threshold to
            # reject noise/illumination flicker; shorter post-event padding.
            "Low Sensitivity",
            {
                "threshold": "0.5",
                "min-event-length": "0.6s",
                "variance-threshold": "32",
                "time-post-event": "1.5s",
            },
        ),
        (
            # Throughput over precision: CNT subtractor (fastest), process every
            # other frame, quarter-area downscale; threshold raised slightly to
            # offset the extra noise those introduce.
            "Fast Scan",
            {
                "bg-subtractor": "CNT",
                "frame-skip": "1",
                "downscale-factor": "2",
                "threshold": "0.2",
            },
        ),
    ]
)
"""Built-in presets shipped with DVR-Scan, as raw config option/value strings.
Each entry must validate against CONFIG_MAP/CHOICE_MAP (enforced by unit test)."""


def presets_dir() -> Path:
    """Directory where user presets are stored."""
    return USER_CONFIG_FILE_PATH.parent / PRESETS_DIR_NAME


def default_preset() -> Preset:
    """The `Default` preset, backed by the user config file. Loads program defaults
    if the user config file does not exist."""
    return Preset(name=DEFAULT_PRESET_NAME, builtin=True, path=USER_CONFIG_FILE_PATH)


def is_valid_preset_name(name: str) -> bool:
    """True if `name` can be used to save a user preset. `Default` is valid (it maps
    to the user config file), but built-in preset names cannot be overwritten."""
    if name == DEFAULT_PRESET_NAME:
        return True
    if name in BUILTIN_PRESETS:
        return False
    return _VALID_NAME_RE.match(name) is not None


def preset_path(name: str, base_dir: ty.Optional[Path] = None) -> Path:
    """Path where a user preset named `name` is stored. `Default` maps to the user
    config file regardless of `base_dir`."""
    if name == DEFAULT_PRESET_NAME:
        return USER_CONFIG_FILE_PATH
    if base_dir is None:
        base_dir = presets_dir()
    return base_dir / (name + PRESET_SUFFIX)


def scan_user_presets(base_dir: ty.Optional[Path] = None) -> ty.List[Preset]:
    """Find valid user presets in `base_dir` (the user presets folder by default),
    sorted by name. Files that fail to load, or whose name conflicts with a built-in
    preset, are skipped with a warning."""
    if base_dir is None:
        base_dir = presets_dir()
    found: ty.List[Preset] = []
    if not base_dir.is_dir():
        return found
    for path in base_dir.glob("*" + PRESET_SUFFIX):
        name = path.stem
        if name == DEFAULT_PRESET_NAME or name in BUILTIN_PRESETS:
            logger.warning("Skipping preset %s: name conflicts with a built-in preset.", path.name)
            continue
        try:
            # Fully load the file: this enforces the CONFIG_MAP schema (rejecting unknown
            # options), which a bare ConfigParser parse would not catch.
            ConfigRegistry().load(path)
        except ConfigLoadFailure:
            logger.warning("Skipping invalid preset file: %s", path)
            continue
        found.append(Preset(name=name, builtin=False, path=path))
    found.sort(key=lambda preset: preset.name.lower())
    return found


def list_presets(base_dir: ty.Optional[Path] = None) -> ty.List[Preset]:
    """All available presets: `Default`, then built-ins, then user presets."""
    presets = [default_preset()]
    presets += [
        Preset(name=name, builtin=True, overrides=overrides)
        for name, overrides in BUILTIN_PRESETS.items()
    ]
    presets += scan_user_presets(base_dir)
    return presets


def load_preset(preset: Preset) -> ConfigRegistry:
    """Load `preset` into a new ConfigRegistry.

    Raises:
        ConfigLoadFailure: The preset file is missing or invalid.
    """
    config = ConfigRegistry()
    if preset.overrides is not None:
        config_str = "\n".join(f"{key} = {value}" for key, value in preset.overrides.items())
        config.load_from_string(config_str, source=f"<preset: {preset.name}>")
    elif preset.name == DEFAULT_PRESET_NAME:
        # Gracefully handles a missing user config file (loads program defaults).
        config.load()
    else:
        config.load(preset.path)
    return config


def save_user_preset(
    name: str, settings: "ScanSettings", base_dir: ty.Optional[Path] = None
) -> Path:
    """Write the app settings in `settings` as a preset named `name`, atomically
    (temp file + replace). Saving over `Default` updates the user config file.

    Returns:
        Path the preset was written to.

    Raises:
        ValueError: `name` is not a valid preset name.
        OSError: The preset file could not be written.
    """
    if not is_valid_preset_name(name):
        raise ValueError(f"invalid preset name: {name!r}")
    path = preset_path(name, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = NamedTemporaryFile(mode="w", dir=path.parent, suffix=".tmp", delete=False)
    try:
        with tmp:
            settings.write_to_file(tmp)
        Path(tmp.name).replace(path)
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)
        raise
    return path
