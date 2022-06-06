# -*- coding: utf-8 -*-
#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#       [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# Copyright (C) 2016-2022 Brandon Castellano <http://www.bcastell.com>.
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
""" ``dvr_scan.__main__`` Module

Provides entry point for DVR-Scan's command-line interface (CLI).
"""

# Standard Library Imports
from __future__ import print_function
import os
import os.path
import sys

# DVR-Scan Library Imports
from dvr_scan import init_logger
from dvr_scan.cli import get_cli_parser
from dvr_scan.scanner import ScanContext
from dvr_scan.scanner import VideoLoadFailure
from dvr_scan.platform import cnt_is_available


def validate_cli_args(args, logger):
    """ Validates command line options, returning a boolean indicating if the validation succeeded,
    and a set of validated options. """
    for file in args.input:
        if not os.path.exists(file):
            logger.error("Error: Input file does not exist:\n  %s", file)
            return False, None
    if args.output and not '.' in args.output:
        args.output += '.avi'
    if args.kernel_size < 0:
        args.kernel_size = None
    return True, args


def main():
    """Entry point for running main DVR-Scan program.

    Handles high-level interfacing of video IO and motion event detection.

    Returns:
        0 on successful termination, non-zero otherwise.
    """
    # Parse the user-supplied CLI arguments and init the logger.
    args = get_cli_parser().parse_args()
    logger = init_logger(args.quiet_mode)
    # Validate arguments and then continue.
    validated, args = validate_cli_args(args, logger)

    if not validated:
        return 1

    try:
        if args.bg_subtractor == 'cnt' and not cnt_is_available():
            logger.error('Method CNT not available: OpenCV update is required.')
            sys.exit(1)

        sctx = ScanContext(
            input_videos=args.input,
            frame_skip=args.frame_skip,
            show_progress=not args.quiet_mode,
        )

        # Set context properties based on CLI arguments.

        sctx.set_output(
            scan_only=args.scan_only_mode,
            comp_file=args.output,
            codec=args.fourcc_str,
        )

        sctx.set_overlays(
            draw_timecode=args.draw_timecode,
            bounding_box_smoothing=args.bounding_box,
        )

        sctx.set_detection_params(
            threshold=args.threshold,
            kernel_size=args.kernel_size,
            downscale_factor=args.downscale_factor,
            roi=args.roi,
        )

        sctx.set_event_params(
            min_event_len=args.min_event_len,
            time_pre_event=args.time_pre_event,
            time_post_event=args.time_post_event,
        )

        sctx.set_video_time(
            start_time=args.start_time,
            end_time=args.end_time,
            duration=args.duration,
        )

        sctx.scan_motion(args.bg_subtractor)

    except VideoLoadFailure:
        # Error information is logged in ScanContext when this exception is raised.
        logger.error('Failed to load input, see above output for details.')
        return 1

    except ValueError as ex:
        logger.error(ex)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
