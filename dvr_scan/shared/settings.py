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

from dvr_scan.config import ConfigRegistry


class ScanSettings:
    """Settings represent the complete user input and output settings for a given scan.
    This also includes the config to use for motion scanning."""

    def __init__(self, args: argparse.Namespace, config: ConfigRegistry):
        self._args = args
        self._config = config

    @property
    def config(self) -> ConfigRegistry:
        return self._config

    def get_arg(self, arg: str) -> ty.Optional[ty.Any]:
        """Get setting specified via command line argument, if any."""
        arg_name = arg.replace("-", "_")
        return getattr(self._args, arg_name) if hasattr(self._args, arg_name) else None

    def get(self, option: str) -> ty.Union[str, int, float, bool]:
        """Get setting based on following resolution order:
        1. Argument specified via command line.
        2. Option set in the active config file (either explicit with -c/--config, or
           the dvr-scan.cfg file in the user's settings folder).
        3. Default value specified in the config map (`dvr_scan.config.CONFIG_MAP`).
        """
        arg_val = self.get_arg(option)
        if arg_val is not None:
            return arg_val
        return self.config.get_value(option)
