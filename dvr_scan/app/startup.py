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

"""Startup mode selection for the DVR-Scan application (Scan Wizard vs. Advanced Mode).

The ``startup-mode`` config option holds the user's default. The code default is
``advanced`` so existing installs keep the full settings view, while the config template
shipped with the installer sets ``wizard`` so fresh installs start in the Scan Wizard.
Installs without any user config file (e.g. pip or portable) fall back to a one-time
heuristic: if DVR-Scan has written log files before, the user is treated as an existing
user (Advanced Mode), otherwise as a new one (wizard). The result is persisted to the user
config so later runs agree (the first run itself writes a log file).

The legacy value ``classic`` (the name of Advanced Mode during 2.0 development) is still
accepted wherever a startup mode is read, and is normalized to ``advanced``.

The ``--startup-mode`` command line option overrides the default for a single launch.
"""

import logging
import typing as ty
from pathlib import Path

from dvr_scan.config import (
    CHOICE_MAP,
    CONFIG_MAP,
    ConfigRegistry,
    normalize_choice,
    set_user_config_option,
)

logger = logging.getLogger("dvr_scan")

STARTUP_MODE_OPTION = "startup-mode"
WIZARD = "wizard"
ADVANCED = "advanced"
# Matches current (`dvr-scan-app.<random>.log`, `dvr-scan.<random>.log`) and legacy
# (`dvr-scan-app.log`, `dvr-scan.log`) log file names.
LOG_GLOB = "dvr-scan*.log"


def normalize_startup_mode(mode: str) -> str:
    """Lowercase `mode` and map the legacy alias "classic" to "advanced". Does not
    validate; unknown values are returned lowercased."""
    return normalize_choice(STARTUP_MODE_OPTION, str(mode)).strip().lower()


def has_prior_logs(log_dir: Path, exclude: ty.Optional[Path] = None) -> bool:
    """True if `log_dir` holds any DVR-Scan log file other than `exclude` (the log file
    of the current process, which may already exist)."""
    if not log_dir.is_dir():
        return False
    excluded = exclude.resolve() if exclude is not None else None
    for path in log_dir.glob(LOG_GLOB):
        if excluded is not None and path.resolve() == excluded:
            continue
        return True
    return False


def resolve_default_startup_mode(
    config: ConfigRegistry,
    user_config_exists: bool,
    prior_logs: bool,
    allow_heuristic: bool,
) -> ty.Tuple[str, bool]:
    """Determine the default startup mode.

    Arguments:
        config: Loaded configuration (user config, or the one passed with `-c`).
        user_config_exists: Whether a user config file exists on disk.
        prior_logs: Whether DVR-Scan log files from earlier runs exist.
        allow_heuristic: False when the user config is being ignored or a config file was
            given explicitly, in which case the first-run heuristic must not run (and
            nothing should be written to the user config).

    Returns:
        (mode, needs_persist): `mode` is "wizard" or "advanced". `needs_persist` is True
        when the mode was chosen by the first-run heuristic and should be written to the
        user config so later runs agree.
    """
    if not config.is_default(STARTUP_MODE_OPTION):
        return normalize_startup_mode(config.get(STARTUP_MODE_OPTION)), False
    if allow_heuristic and not user_config_exists:
        return (ADVANCED if prior_logs else WIZARD), True
    return normalize_startup_mode(CONFIG_MAP[STARTUP_MODE_OPTION]), False


def save_startup_mode(mode: str, path: ty.Optional[Path] = None) -> Path:
    """Persist `mode` as the default startup mode in the user config file (or `path`).
    The legacy alias "classic" is written as "advanced".

    Raises:
        ValueError: `mode` is not a valid startup mode.
        OSError: The config file could not be written.
    """
    mode = normalize_startup_mode(mode)
    if mode not in CHOICE_MAP[STARTUP_MODE_OPTION]:
        raise ValueError(f"invalid startup mode: {mode!r}")
    return set_user_config_option(STARTUP_MODE_OPTION, mode, path)
