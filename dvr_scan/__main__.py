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
""" ``dvr_scan.__main__`` Module

Provides entry point for DVR-Scan's command-line interface (CLI).
"""

import logging
from subprocess import CalledProcessError
import sys

from dvr_scan.cli.controller import parse_settings, create_scan_context

from scenedetect import VideoOpenFailure

EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1


def main():
    """Main entry-point for DVR-Scan."""
    # Parse command-line options and config file settings.
    settings = parse_settings()
    if settings is None:
        sys.exit(EXIT_ERROR)

    logger = logging.getLogger('dvr_scan')
    try:
        sctx = create_scan_context(settings)
        sctx.scan_motion()
        return

    except ValueError as ex:
        logger.error('Error: %s', str(ex))
        if settings.debug_mode:
            raise
        sys.exit(EXIT_ERROR)

    except VideoOpenFailure as ex:
        # Error information should be logged by the ScanContext when this exception is raised.
        logger.error('Failed to load input: %s', str(ex))
        if settings.debug_mode:
            raise
        sys.exit(EXIT_ERROR)

    except KeyboardInterrupt as ex:
        # TODO(v1.6): Change this to log something with info verbosity so it's clear
        # to end users why the program terminated.
        logger.debug("KeyboardInterrupt received, quitting.")
        if settings.debug_mode:
            raise
        sys.exit(EXIT_ERROR)

    except CalledProcessError as ex:
        logger.error(
            'Failed to run command:\n  %s\nCommand returned %d, output:\n\n%s',
            ' '.join(ex.cmd),
            ex.returncode,
            ex.output,
        )
        if settings.debug_mode:
            raise
        sys.exit(EXIT_ERROR)


if __name__ == '__main__':
    main()
