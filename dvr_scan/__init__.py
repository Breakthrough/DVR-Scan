# -*- coding: utf-8 -*-
#
#       DVR-Scan: Find & Export Motion Events in Video Footage
#   --------------------------------------------------------------
#     [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#     [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# This file contains all code for the main `dvr_scan` module.
#
# Copyright (C) 2016-2020 Brandon Castellano <http://www.bcastell.com>.
#
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file or visit one of the following pages for details:
#  - https://github.com/Breakthrough/DVR-Scan/
#
# This software uses Numpy and OpenCV; see the LICENSE-NUMPY and
# LICENSE-OPENCV files or visit the above URL for details.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
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

# Standard Library Imports
from __future__ import print_function

# DVR-Scan Library Imports
import dvr_scan.cli
import dvr_scan.scanner


# Used for module identification and when printing copyright & version info.
__version__ = 'v1.2-dev'

# About & copyright message string shown for the -v/--version CLI argument.
ABOUT_STRING = """-----------------------------------------------
DVR-Scan %s
-----------------------------------------------
Copyright (C) 2016-2021 Brandon Castellano
< https://github.com/Breakthrough/DVR-Scan >

This DVR-Scan is licensed under the BSD 2-Clause license; see the
included LICENSE file, or visit the above link for details. This
software uses the following third-party components:
  NumPy: Copyright (C) 2005-2013, Numpy Developers.
 OpenCV: Copyright (C) 2016, Itseez.
THE SOFTWARE IS PROVIDED "AS IS" WITHOUT ANY WARRANTY, EXPRESS OR IMPLIED.

""" % __version__

def parse_cli_args():
    """ Parses all given arguments, returning the object containing
    all options as properties. """
    # Parse the user-supplied CLI arguments.
    args = dvr_scan.cli.get_cli_parser().parse_args()

    # We close any opened file handles, as only the paths are required,
    # and replace the file handles with the path as a string.
    for input_file in args.input:
        input_file.close()
    args.input = [ handle.name for handle in args.input ]
    if args.output:
        args.output.close()
        args.output = args.output.name
    return args


def main():
    """Entry point for running main DVR-Scan program.

    Handles high-level interfacing of video IO and motion event detection.
    """
    # Parse CLI arguments and create our ScanContext.
    args = parse_cli_args()
    sctx = dvr_scan.scanner.ScanContext(args)

    # Set context properties based on CLI arguments.
    sctx.set_output(args.scan_only_mode, args.output, args.fourcc_str)
    sctx.set_detection_params(args.threshold, args.kernel_size)

    # If the context was successfully initialized, we can process the video(s).
    if sctx.initialized is True:
        sctx.scan_motion()
