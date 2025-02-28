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
"""``dvr_scan.__main__`` Module

Provides entry point for DVR-Scan's command-line interface (CLI).
"""

import logging
import sys
from subprocess import CalledProcessError

from scenedetect import VideoOpenFailure
from scenedetect.platform import FakeTqdmLoggingRedirect, logging_redirect_tqdm

from dvr_scan.controller import parse_settings, run_dvr_scan

EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1


def main():
    """Main entry-point for DVR-Scan."""
    settings = parse_settings()
    if settings is None:
        sys.exit(EXIT_ERROR)
    logger = logging.getLogger("dvr_scan")
    # TODO(1.7): The logging redirect does not respect the original log level, which is now set to
    # DEBUG mode for rolling log files. https://github.com/tqdm/tqdm/issues/1272
    # We might have to just roll our own instead of relying on this one.
    redirect = FakeTqdmLoggingRedirect if settings.get("quiet-mode") else logging_redirect_tqdm
    # TODO: Use Python __debug__ mode instead of hard-coding as config option.
    debug_mode = settings.get("debug")
    show_traceback = getattr(logging, settings.get("verbosity").upper()) == logging.DEBUG
    with redirect(loggers=[logger]):
        try:
            run_dvr_scan(settings)
        except ValueError as ex:
            logger.critical("Setting Error: %s", str(ex), exc_info=show_traceback)
            if debug_mode:
                raise
        except VideoOpenFailure as ex:
            logger.critical("Failed to load input: %s", str(ex), exc_info=show_traceback)
            if debug_mode:
                raise
        except KeyboardInterrupt:
            logger.info("Stopping (interrupt received)...", exc_info=show_traceback)
            if debug_mode:
                raise
        except CalledProcessError as ex:
            logger.error(
                "Failed to run command:\n  %s\nCommand returned %d, output:\n\n%s",
                " ".join(ex.cmd),
                ex.returncode,
                ex.output,
                exc_info=show_traceback,
            )
            if debug_mode:
                raise
        except NotImplementedError as ex:
            logger.critical("Error (Not Implemented): %s", str(ex), exc_info=show_traceback)
            if debug_mode:
                raise
        except Exception as ex:
            logger.critical("Critical Error: %s", str(ex), exc_info=True)
            if debug_mode:
                raise
        else:
            sys.exit(EXIT_SUCCESS)
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":
    main()
