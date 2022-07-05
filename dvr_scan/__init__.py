# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Copyright (C) 2014-2022 Brandon Castellano <http://www.bcastell.com>.
# PySceneDetect is licensed under the BSD 2-Clause License; see the
# included LICENSE file, or visit one of the above pages for details.
#
""" ``dvr_scan`` Module

This is the main DVR-Scan module containing all application logic,
motion detection implementation, and command line processing. The
modules are organized as follows:

  dvr_scan.cli:
    Command-line interface (argparse)

  dvr_scan.scanner:
    Application logic + motion detection algorithm (ScanContext)
"""

import os
import sys
import pkgutil

# Handle loading OpenCV.
# This **MUST** be first.
import dvr_scan.opencv_loader as _

# Top-level imports for easier access from the dvr_scan module.
from dvr_scan.platform import init_logger
from dvr_scan.scanner import ScanContext

# Used for module/distribution identification.
__version__ = 'v1.5.dev1'


def get_license_info() -> str:
    """Get license/copyright information for the package or standalone executable."""
    try:
        # If we're running a frozen/standalone executable distribution, make sure we include
        # the license information for the third-party components we redistribute.
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            app_folder = os.path.abspath(os.path.dirname(sys.executable))
            license_files = ['LICENSE', 'LICENSE-THIRDPARTY']
            license_text = '\n'.join([
                open(os.path.join(app_folder, license_file), 'rb').read().decode('ascii', 'ignore')
                for license_file in license_files
            ])
        # Use the LICENSE file included with the package distribution.
        else:
            license_text = pkgutil.get_data(__name__, "LICENSE").decode('ascii', 'ignore')
        return license_text
    # During development this is normal since the package paths won't be correct.
    except FileNotFoundError:
        pass
    return ('[DVR-Scan] Error: Missing LICENSE files.\n'
            'See the following URL for license/copyright information:\n'
            ' < https://dvr-scan.readthedocs.io/en/latest/copyright >\n')


# Initialize logger.
init_logger(show_stdout=True)
