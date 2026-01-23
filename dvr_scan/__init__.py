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

import pkgutil
import sys

# Used for module/distribution identification.
__version__ = "1.9-dev0"

# Handle loading OpenCV. This **MUST** be first before any other DVR-Scan or third-party
# packages are imported which might attempt to import the `cv2` module.
import dvr_scan.opencv_loader as _  # noqa: F401
from dvr_scan.platform import init_logger

# Initialize logger.
init_logger(show_stdout=True)


def get_license_info() -> str:
    """Get license/copyright information for the package or standalone executable."""
    license_text = pkgutil.get_data(__name__, "LICENSE").decode()
    # Include additional third-party license text if they were bundled into this release.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        license_text += pkgutil.get_data(__name__, "LICENSE-THIRDPARTY").decode()
    return license_text
