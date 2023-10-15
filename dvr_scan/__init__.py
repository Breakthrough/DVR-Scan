# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2014-2023 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""``dvr_scan`` Module

This is the main DVR-Scan module containing all application logic,
motion detection implementation, and command line processing. The
main modules under `dvr_scan` are organized as follows:

  ``cli``: command-line interface

  ``scanner``: scans a video for motion and extracts events

  ``detector``: motion detection algorithms

  ``overlays``: overlays which can be drawn when outputting events

There are also a few helper modules:

  ``video_joiner``: concatenates multiple input videos

  ``opencv_loader``: helper for resolving dynamic libraries used by OpenCV

  ``platform``: library/platform specific helpers
"""

import os
import sys
import pkgutil

# Handle loading OpenCV. This **MUST** be first before any other DVR-Scan or third-party
# packages are imported which might attempt to import the `cv2` module.
import dvr_scan.opencv_loader as _

from dvr_scan.platform import init_logger

# Used for module/distribution identification.
__version__ = '1.6'


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
            ' < https://www.dvr-scan.com/resources >\n')


# Initialize logger.
init_logger(show_stdout=True)
