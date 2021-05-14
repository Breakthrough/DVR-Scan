# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Provides functionality to run DVR-Scan directly as a Python module (in
# addition to using in other scripts via `import dvr_scan`) by running:
#
#   > python -m dvr_scan
#
# Installing DVR-Scan (using `python setup.py install` command in the parent
# directory) will allow the `dvr-scan` command to be used from anywhere,
# e.g. `dvr-scan -i myfile.mp4`.
#
# Copyright (C) 2016-2021 Brandon Castellano <http://www.bcastell.com>.
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

""" ``dvr_scan.__main__`` Module

Provides entry point for DVR-Scan's command-line interface (CLI).
"""

# Standard Library Imports
from __future__ import print_function
import logging
import sys

# DVR-Scan Library Imports
from dvr_scan import init_logger
from dvr_scan.cli import get_cli_parser
from dvr_scan.scanner import ScanContext
from dvr_scan.scanner import VideoLoadFailure
from dvr_scan.platform import cnt_is_available

def parse_cli_args():
    """ Parses all given arguments, returning the object containing
    all options as properties. """
    # Parse the user-supplied CLI arguments.
    args = get_cli_parser().parse_args()

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
    args = parse_cli_args()
    logger = init_logger(args.quiet_mode)

    try:
        if args.bg_subtractor == 'cnt' and not cnt_is_available():
            logger.error('Method CNT not available: OpenCV update is required.')
            sys.exit(1)

        sctx = ScanContext(
            input_videos=args.input,
            frame_skip=args.frame_skip,
            show_progress=not args.quiet_mode)

        # Set context properties based on CLI arguments.

        sctx.set_output(
            scan_only=args.scan_only_mode,
            comp_file=args.output,
            codec=args.fourcc_str,
            draw_timecode=args.draw_timecode)

        sctx.set_detection_params(
            threshold=args.threshold,
            kernel_size=args.kernel_size,
            downscale_factor=args.downscale_factor,
            roi=args.roi)

        sctx.set_event_params(
            min_event_len=args.min_event_len,
            time_pre_event=args.time_pre_event,
            time_post_event=args.time_post_event)

        sctx.set_video_time(
            start_time=args.start_time,
            end_time=args.end_time,
            duration=args.duration)

        sctx.scan_motion(args.bg_subtractor)

    except VideoLoadFailure:
        # Error information is logged in ScanContext when this exception is raised.
        logger.error('Failed to load input, see above output for details.')

    except ValueError as ex:
        logger.error(ex)

if __name__ == '__main__':
    main()