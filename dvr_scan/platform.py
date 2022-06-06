# -*- coding: utf-8 -*-
#
#       DVR-Scan: Find & Export Motion Events in Video Footage
#   --------------------------------------------------------------
#     [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#     [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# This file contains all platform/library specific code, intended to improve
# compatibility of DVR-Scan with a wider array of software versions.
#
# Copyright (C) 2016-2021 Brandon Castellano <http://www.bcastell.com>.
#
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file or visit one of the following pages for details:
#  - https://github.com/Breakthrough/DVR-Scan/
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

""" ``dvr_scan.platform`` Module

This file contains all platform/library/OS-specific compatibility fixes,
intended to improve the systems that are able to run DVR-Scan, and allow
for maintaining backwards compatibility with existing libraries going forwards.

For OpenCV 2.x, the scenedetect.platform module also makes a copy of the
OpenCV VideoCapture property constants from the cv2.cv namespace directly
to the cv2 namespace.  This ensures that the cv2 API is consistent
with those changes made to it in OpenCV 3.0 and above.

TODO: Replace with PySceneDetect's platform module to reduce code duplication
across both projects.
"""

import logging
import cv2

# Compatibility fix for OpenCV < 3.0
if cv2.__version__[0] == '2' or not (
        cv2.__version__[0].isdigit() and int(cv2.__version__[0]) >= 3):
    cv2.CAP_PROP_FRAME_WIDTH = cv2.cv.CV_CAP_PROP_FRAME_WIDTH
    cv2.CAP_PROP_FRAME_HEIGHT = cv2.cv.CV_CAP_PROP_FRAME_HEIGHT
    cv2.CAP_PROP_FPS = cv2.cv.CV_CAP_PROP_FPS
    cv2.CAP_PROP_POS_MSEC = cv2.cv.CV_CAP_PROP_POS_MSEC
    cv2.CAP_PROP_POS_FRAMES = cv2.cv.CV_CAP_PROP_POS_FRAMES
    cv2.CAP_PROP_FRAME_COUNT = cv2.cv.CV_CAP_PROP_FRAME_COUNT
    cv2.VideoWriter_fourcc = cv2.cv.CV_FOURCC

def get_tqdm():
    """ Safely attempts to import the tqdm module, returning either a
    reference to the imported module, or None if tqdm was not found."""
    try:
        import tqdm
        return tqdm
    except ImportError:
        pass
    return None

def cnt_is_available():
    try:
        return 'createBackgroundSubtractorCNT' in dir(cv2.bgsegm)
    except AttributeError:
        return False

def get_min_screen_bounds():
    """ Safely attempts to get the minimum screen resolution of all monitors
    using the `screeninfo` package. Returns the minimum of all monitor's heights
    and widths with 10% padding."""
    try:
        import screeninfo
        try:
            monitors = screeninfo.get_monitors()
            return (int(0.9 * min(m.height for m in monitors)),
                    int(0.9 * min(m.width for m in monitors)))
        except screeninfo.common.ScreenInfoError as ex:
            logging.getLogger('dvr_scan').warning("Unable to get screen resolution: %s", ex)
    except ImportError:
        pass
    return None
