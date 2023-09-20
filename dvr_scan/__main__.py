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

from dvr_scan.cli.controller import parse_settings, run_dvr_scan
from dvr_scan.cli.config import ConfigLoadFailure

from scenedetect import VideoOpenFailure
from scenedetect.platform import logging_redirect_tqdm, FakeTqdmLoggingRedirect

EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1


def main():
    """Main entry-point for DVR-Scan."""
    settings = parse_settings()
    if settings is None:
        sys.exit(EXIT_ERROR)
    logger = logging.getLogger('dvr_scan')
    redirect = FakeTqdmLoggingRedirect if settings.get('quiet-mode') else logging_redirect_tqdm
    debug_mode = settings.get('debug')
    log_traceback = logging.DEBUG == getattr(logging, settings.get('verbosity').upper())
    with redirect(loggers=[logger]):
        try:
            run_dvr_scan(settings)
        except ValueError as ex:
            logger.critical('Error: %s', str(ex), exc_info=log_traceback)
            if debug_mode:
                raise
        except VideoOpenFailure as ex:
            logger.critical('Failed to load input: %s', str(ex), exc_info=log_traceback)
            if debug_mode:
                raise
        except KeyboardInterrupt as ex:
            logger.info("Stopping (interrupt received)...", exc_info=log_traceback)
            if debug_mode:
                raise
        except CalledProcessError as ex:
            logger.error(
                'Failed to run command:\n  %s\nCommand returned %d, output:\n\n%s',
                ' '.join(ex.cmd),
                ex.returncode,
                ex.output,
                exc_info=log_traceback,
            )
            if debug_mode:
                raise
        except:
            logger.critical('Error during processing:', exc_info=True)
            if debug_mode:
                raise
        else:
            sys.exit(EXIT_SUCCESS)
        sys.exit(EXIT_ERROR)


if __name__ == '__main__':
    main()
