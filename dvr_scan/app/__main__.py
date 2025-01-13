#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2024 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#

import argparse
import logging
import sys
from subprocess import CalledProcessError

from scenedetect import VideoOpenFailure
from scenedetect.platform import FakeTqdmLoggingRedirect, logging_redirect_tqdm

import dvr_scan
from dvr_scan import get_license_info
from dvr_scan.app.application import Application
from dvr_scan.config import CHOICE_MAP, USER_CONFIG_FILE_PATH, ConfigLoadFailure, ConfigRegistry
from dvr_scan.shared import ScanSettings, init_logging
from dvr_scan.shared.cli import VERSION_STRING, LicenseAction, VersionAction, string_type_check

logger = logging.getLogger("dvr_scan")


EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1


def get_cli_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        argument_default=argparse.SUPPRESS,
    )
    if hasattr(parser, "_optionals"):
        parser._optionals.title = "arguments"

    parser.add_argument(
        "-c",
        "--config",
        metavar="dvr-scan.cfg",
        type=str,
        help=(
            "Config file to load scan settings from. If not set, tries to load one from %s"
            % USER_CONFIG_FILE_PATH
        ),
    )

    parser.add_argument(
        "-V",
        "--version",
        action=VersionAction,
        version=VERSION_STRING,
    )

    parser.add_argument(
        "-v",
        "--verbosity",
        metavar="type",
        type=string_type_check(CHOICE_MAP["verbosity"], False, "type"),
        help=(
            "Amount of verbosity to use for log output. Must be one of: %s."
            % (", ".join(CHOICE_MAP["verbosity"]),)
        ),
    )

    parser.add_argument(
        "--logfile",
        metavar="file",
        type=str,
        help=(
            "Path to log file for writing application output. If FILE already exists, the program"
            " output will be appended to the existing contents."
        ),
    )

    parser.add_argument(
        "-L",
        "--license",
        action=LicenseAction,
        version=get_license_info(),
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help=argparse.SUPPRESS,
        default=False,
    )

    parser.add_argument(
        "input",
        nargs="*",
        type=str,
    )

    return parser


# TODO: There's a lot of duplicated code here between the CLI and GUI. See if we can combine some
# of the handling of config file loading and exceptions to be consistent between the two.
#
# It would also be nice if both commands took the same set of arguments. Can probably re-use the
# existing CLI parser.
def main():
    """Parse command line options and load config file settings."""

    init_log = []
    config_load_error = None
    failed_to_load_config = False
    config = ConfigRegistry()
    # Try to load config from user settings folder.
    try:
        user_config = ConfigRegistry()
        user_config.load()
        config = user_config
    except ConfigLoadFailure as ex:
        config_load_error = ex

    # Parse CLI args, override config if an override was specified on the command line.
    try:
        args = get_cli_parser().parse_args()
        init_logging(args, config)
        init_log += [(logging.INFO, "DVR-Scan Application %s" % dvr_scan.__version__)]
        if config_load_error and not hasattr(args, "config"):
            raise config_load_error
        if hasattr(args, "config"):
            config_setting = ConfigRegistry()
            config_setting.load(args.config)
            init_logging(args, config_setting)
            config = config_setting
        init_log += config.consume_init_log()
    except ConfigLoadFailure as ex:
        init_log += ex.init_log
        if ex.reason is not None:
            init_log += [(logging.ERROR, "Error: %s" % str(ex.reason).replace("\t", "  "))]
        failed_to_load_config = True
        config_load_error = ex
    finally:
        for log_level, log_str in init_log:
            logger.log(log_level, log_str)
        if failed_to_load_config:
            logger.critical("Failed to load config file.")
            logger.debug("Error loading config file:", exc_info=config_load_error)
            # Intentionally suppress the exception in release mode since we've already logged the
            # failure reason to the user above. We can now exit with an error code.
            raise SystemExit(1)

    if config.config_dict:
        logger.debug("Loaded configuration:\n%s", str(config.config_dict))

    logger.debug("Program arguments:\n%s", str(args))
    settings = ScanSettings(args=args, config=config)
    redirect = FakeTqdmLoggingRedirect if settings.get("quiet-mode") else logging_redirect_tqdm
    show_traceback = getattr(logging, settings.get("verbosity").upper()) == logging.DEBUG
    # TODO: Use Python __debug__ mode instead of hard-coding as config option.
    debug_mode = settings.get("debug")
    with redirect(loggers=[logger]):
        try:
            app = Application(settings=settings)
            app.run()

        except ValueError as ex:
            logger.critical("Setting Error: %s", str(ex), exc_info=show_traceback)
            if debug_mode:
                raise
        except VideoOpenFailure as ex:
            logger.critical("Failed to load input: %s", str(ex), exc_info=show_traceback)
            if debug_mode:
                raise
        except KeyboardInterrupt:
            # TODO: This doesn't always work when the GUI is running.
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
