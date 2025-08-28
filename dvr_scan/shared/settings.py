#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2024 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#

import argparse
import typing as ty

import dvr_scan
from dvr_scan.config import ConfigRegistry


class ScanSettings:
    """Settings for a given scan job. This is shared across the CLI and the UI, and includes both
    command-line options, config file options, and UI options."""

    def __init__(self, args: argparse.Namespace, config: ConfigRegistry):
        self._args = args  # CLI settings
        self._config = config  # Config file settings
        self._app_settings = dict()  # UI settings

    @property
    def app_settings(self) -> ty.Dict[str, ty.Any]:
        return self._app_settings

    @property
    def config(self) -> ConfigRegistry:
        return self._config

    def get_arg(self, option: str) -> ty.Optional[ty.Any]:
        """Get setting specified via command line argument, if any."""
        if option in self._app_settings:
            return self._app_settings[option]
        arg_name = option.replace("-", "_")
        return getattr(self._args, arg_name) if hasattr(self._args, arg_name) else None

    def get(self, option: str) -> ty.Union[str, int, float, bool]:
        """Get the current value for `option`, preferring the current UI or CLI setting, falling
        back to either the config file option, or the default value."""
        if option in self._app_settings:
            return self._app_settings[option]
        arg_val = self.get_arg(option)
        if arg_val is not None:
            return arg_val
        return self._config.get(option)

    def set(self, option: str, value: ty.Union[str, int, float, bool]):
        """Set application overrides for any setting."""
        self._app_settings[option] = value

    def write_to_file(self, file: ty.TextIO):
        """Get application settings as a config file.

        *NOTE*: This is only implemented for the UI settings currently."""
        file.write("# DVR-Scan Config File\n")
        file.write(f"# Created by: DVR-Scan {dvr_scan.__version__}\n")
        keys = sorted(self._app_settings.keys())
        if "mask-output" in keys:
            keys.remove("mask-output")
        for key in keys:
            value = self._app_settings[key]
            if isinstance(value, bool):
                value = "yes" if True else "no"
            file.write(f"{key} = {str(value)}\n")
