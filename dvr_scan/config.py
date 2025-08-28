#
#         PySceneDetect: Python-Based Video Scene Detector
#   ---------------------------------------------------------------
#     [  Site:   http://www.scenedetect.scenedetect.com/         ]
#     [  Docs:   http://manual.scenedetect.scenedetect.com/      ]
#     [  Github: https://github.com/Breakthrough/PySceneDetect/  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
# PySceneDetect is licensed under the BSD 3-Clause License; see the
# included LICENSE file, or visit one of the above pages for details.
#
"""``dvr_scan.config`` Module

Handles loading configuration files from disk and validating each setting. Only validation
of the config file schema and data types are performed. The constants and default values
defined here are used by the CLI as well to ensure there is one source of truth. Note that
the constants defined here for use by the CLI/config file may differ from their equivalents
in the `dvr_scan` module.
"""

import logging
import typing as ty
from abc import ABC, abstractmethod
from configparser import DEFAULTSECT, ConfigParser, ParsingError
from pathlib import Path

from platformdirs import user_config_dir
from scenedetect.frame_timecode import FrameTimecode

from dvr_scan.scanner import DEFAULT_FFMPEG_INPUT_ARGS, DEFAULT_FFMPEG_OUTPUT_ARGS

# Backwards compatibility for config options that were renamed/replaced.
MIGRATED_CONFIG_OPTION: ty.Dict[str, str] = {
    "timecode": "time-code",
    "timecode-margin": "text-margin",
    "timecode-font-scale": "text-font-scale",
    "timecode-font-thickness": "text-font-thickness",
    "timecode-font-color": "text-font-color",
    "timecode-bg-color": "text-bg-color",
}

DEPRECATED_CONFIG_OPTION: ty.Dict[str, str] = {
    "region-of-interest": "The region-of-interest config option is deprecated and may be removed. "
    "Use the load-region option instead, or specify -R/--load-region."
}


class ValidatedValue(ABC):
    """Used to represent configuration values that must be validated against constraints."""

    @property
    @abstractmethod
    def value(self) -> ty.Any:
        """Get the value after validation."""
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def from_config(config_value: str, default: "ValidatedValue") -> "ValidatedValue":
        """Validate and get the user-specified configuration option.

        Raises:
            OptionParseFailure: Value from config file did not meet validation constraints.
        """
        raise NotImplementedError()


class OptionParseFailure(Exception):
    """Raised when a value provided in a user config file fails validation."""

    def __init__(self, error):
        super().__init__()
        self.error = error


class TimecodeValue(ValidatedValue):
    """Validator for timecode values in frames (1234), seconds (123.4s), or HH:MM:SS.

    Stores value in original representation."""

    def __init__(self, value: ty.Union[int, float, str]):
        # Ensure value is a valid timecode.
        FrameTimecode(timecode=value, fps=100.0)
        self._value = value

    @property
    def value(self) -> ty.Union[int, float, str]:
        return self._value

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

    @staticmethod
    def from_config(config_value: str, default: "TimecodeValue") -> "TimecodeValue":
        try:
            return TimecodeValue(config_value)
        except ValueError as ex:
            raise OptionParseFailure(
                "Timecodes must be in frames (1234), seconds (123.4s), or HH:MM:SS (00:02:03.400)."
            ) from ex


class RangeValue(ValidatedValue):
    """Validator for int/float ranges. `min_val` and `max_val` are inclusive."""

    def __init__(
        self,
        value: ty.Union[int, float],
        min_val: ty.Union[int, float],
        max_val: ty.Union[int, float],
    ):
        if value < min_val or value > max_val:
            # min and max are inclusive.
            raise ValueError()
        self._value = value
        self._min_val = min_val
        self._max_val = max_val

    @property
    def value(self) -> ty.Union[int, float]:
        return self._value

    @property
    def min_val(self) -> ty.Union[int, float]:
        """Minimum value of the range."""
        return self._min_val

    @property
    def max_val(self) -> ty.Union[int, float]:
        """Maximum value of the range."""
        return self._max_val

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

    @staticmethod
    def from_config(config_value: str, default: "RangeValue") -> "RangeValue":
        try:
            return RangeValue(
                value=int(config_value) if isinstance(default.value, int) else float(config_value),
                min_val=default.min_val,
                max_val=default.max_val,
            )
        except ValueError as ex:
            raise OptionParseFailure(
                "Value must be between %s and %s." % (default.min_val, default.max_val)
            ) from ex


class KernelSizeValue(ValidatedValue):
    """Validator for kernel sizes (odd integer > 1, 0 for off, or -1 for auto size)."""

    def __init__(self, value: int = -1):
        value = int(value)
        if value not in (-1, 0) and (value < 3 or value % 2 == 0):
            raise ValueError()
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        if self.value == -1:
            return "-1 (auto)"
        elif self.value == 0:
            return "0 (off)"
        return str(self.value)

    @staticmethod
    def from_config(config_value: str, default: "KernelSizeValue") -> "KernelSizeValue":
        try:
            return KernelSizeValue(int(config_value))
        except ValueError as ex:
            raise OptionParseFailure(
                "Size must be odd number starting from 3, 0 to disable, or -1 for auto."
            ) from ex


class RegionValueDeprecated(ValidatedValue):
    """Validator for deprecated region-of-interest values."""

    _IGNORE_CHARS = [",", "/", "(", ")"]
    """Characters to ignore."""

    def __init__(self, value: ty.Optional[str] = None, allow_size: bool = False):
        if value is not None:
            translation_table = str.maketrans(
                {char: " " for char in RegionValueDeprecated._IGNORE_CHARS}
            )
            values = value.translate(translation_table).split()
            valid_lengths = (2, 4) if allow_size else (4,)
            if not (
                len(values) in valid_lengths
                and all([val.isdigit() for val in values])
                and all([int(val) >= 0 for val in values])
            ):
                raise ValueError()
            self._value = [int(val) for val in values]
        else:
            self._value = None

    @property
    def value(self) -> ty.Optional[ty.List[int]]:
        return self._value

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        if self.value is not None:
            return "(%d,%d)/(%d,%d)" % (
                self.value[0],
                self.value[1],
                self.value[2],
                self.value[3],
            )
        return str(self.value)

    @staticmethod
    def from_config(config_value: str, default: "RegionValueDeprecated") -> "RegionValueDeprecated":
        try:
            return RegionValueDeprecated(config_value)
        except ValueError as ex:
            raise OptionParseFailure(
                "ROI must be four positive integers of the form (x,y)/(w,h)."
                " Brackets, commas, slashes, and spaces are optional."
            ) from ex


class RGBValue(ValidatedValue):
    """Validator for RGB values of the form (255, 255, 255) or 0xFFFFFF."""

    _IGNORE_CHARS = [",", "/", "(", ")"]
    """Characters to ignore."""

    def __init__(self, value: ty.Union[int, str, "RGBValue"]):
        if isinstance(value, RGBValue):
            return value
        # If not an int, convert to one.
        # First try to convert values of the form 'ffffff'.
        if not isinstance(value, int) and len(value) == 6:
            try:
                new_value = int(value, base=16)
                value = new_value
            except ValueError:
                # Continue trying to process it like the remaining types.
                pass
        # Next try to convert values of the form '0xffffff'.
        if not isinstance(value, int) and value[0:2] in ("0x", "0X"):
            value = int(value, base=16)
        # Finally try to process in the form '(255, 255, 255)'.
        if not isinstance(value, int):
            translation_table = str.maketrans({char: " " for char in RGBValue._IGNORE_CHARS})
            values = value.translate(translation_table).split()
            if not (
                len(values) == 3
                and all([val.isdigit() for val in values])
                and all([int(val) >= 0 for val in values])
            ):
                raise ValueError()
            value = int(values[0]) << 16 | int(values[1]) << 8 | int(values[2])
        assert isinstance(value, int)
        if value < 0x000000 or value > 0xFFFFFF:
            raise ValueError("RGB value must be between 0x000000 and 0xFFFFFF.")
        # Convert into tuple of (R, G, B)
        self._value = (
            (value & 0xFF0000) >> 16,
            (value & 0x00FF00) >> 8,
            (value & 0x0000FF),
        )

    @property
    def value(self) -> ty.Tuple[int, int, int]:
        return self._value

    @property
    def value_as_int(self) -> int:
        """Return value in integral (binary) form as opposed to tuple of R,G,B."""
        return int(self.value[0]) << 16 | int(self.value[1]) << 8 | int(self.value[2])

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return "0x%06x" % self.value_as_int

    @staticmethod
    def from_config(config_value: str, default: "RGBValue") -> "RGBValue":
        try:
            return RGBValue(config_value)
        except ValueError as ex:
            raise OptionParseFailure(
                "Color values must be in hex (0xFFFFFF) or R,G,B (255,255,255)."
            ) from ex


ConfigValue = ty.Union[bool, int, float, str, Path]
ConfigDict = ty.Dict[str, ConfigValue]

_CONFIG_FILE_NAME: str = "dvr-scan.cfg"
_CONFIG_FILE_DIR: Path = Path(user_config_dir("DVR-Scan", False))

USER_CONFIG_FILE_PATH: Path = _CONFIG_FILE_DIR / _CONFIG_FILE_NAME

# TODO: Investigate if centralizing user help strings here would be useful.
# It might make CLI help and documentation are easier to create, as well as
# for generating a default config file template.

# TODO: Replace these default values with those set in dvr_scan.context.
CONFIG_MAP: ConfigDict = {
    # General Options
    "quiet-mode": False,
    # Input/Output
    "ffmpeg-input-args": DEFAULT_FFMPEG_INPUT_ARGS,
    "ffmpeg-output-args": DEFAULT_FFMPEG_OUTPUT_ARGS,
    "input-mode": "opencv",
    "opencv-codec": "XVID",
    "output-dir": "",
    "open-output-dir": True,
    "output-mode": "opencv",
    "region-editor": False,
    "scan-only": False,
    # Motion Events
    "min-event-length": TimecodeValue("0.1s"),
    "time-before-event": TimecodeValue("1.5s"),
    "time-post-event": TimecodeValue("2.0s"),
    "use-pts": False,
    # Detection Parameters
    "bg-subtractor": "MOG2",
    "threshold": 0.15,
    "max-threshold": 255.0,
    "max-area": 1.0,
    "max-width": 1.0,
    "max-height": 1.0,
    "variance-threshold": 16.0,
    "kernel-size": KernelSizeValue(),
    "downscale-factor": 0,
    "learning-rate": float(-1),
    # TODO(1.9): Remove, has been replaced with region files.
    "region-of-interest": RegionValueDeprecated(),
    "load-region": "",
    "frame-skip": 0,
    # Overlays
    # Text Overlays
    "time-code": False,
    "frame-metrics": False,
    "text-border": 4,
    "text-margin": 4,
    "text-font-scale": 1.0,
    "text-font-thickness": 2,
    "text-font-color": RGBValue(0xFFFFFF),
    "text-bg-color": RGBValue(0x000000),
    # Bounding Box
    "bounding-box": False,
    "bounding-box-smooth-time": TimecodeValue("0.1s"),
    "bounding-box-color": RGBValue(0xFF0000),
    "bounding-box-thickness": 0.0032,
    "bounding-box-min-size": 0.032,
    "thumbnails": None,
    # Logging
    "verbosity": "info",
    "save-log": True,
    # max-log-size is not implemented, but is kept for backwards compatibility with older
    # config files. Previously, logs would be appended to the same file until they reached this size
    # after which a new file would be created.
    "max-log-size": 20000,
    "max-log-files": 15,
    # Development
    "debug": False,
}
"""Mapping of valid configuration file parameters and their default values or placeholders.
The types of these values are used when decoding the configuration file. Valid choices for
certain string options are stored in `CHOICE_MAP`."""

CHOICE_MAP: ty.Dict[str, ty.List[str]] = {
    "input-mode": ["opencv", "pyav", "moviepy"],
    "opencv-codec": ["XVID", "MP4V", "MP42", "H264"],
    "output-mode": ["scan_only", "opencv", "copy", "ffmpeg"],
    "verbosity": ["debug", "info", "warning", "error"],
    "bg-subtractor": ["MOG2", "CNT", "MOG2_CUDA"],
    "thumbnails": ["highscore"],
}
"""Mapping of string options which can only be of a particular set of values. We use a list instead
of a set to preserve order when generating error contexts. Values are case-insensitive, and must be
in lowercase in this map."""


class ConfigLoadFailure(Exception):
    """Raised when a user-specified configuration file fails to be loaded or validated."""

    def __init__(self, init_log: ty.Tuple[int, str], reason: ty.Optional[Exception] = None):
        super().__init__()
        self.init_log = init_log
        self.reason = reason


class ConfigRegistry:
    """Provides application option values based on either user-specified configuration, or
    default values specified in the global CONFIG_MAP."""

    def __init__(self):
        self._init_log: ty.List[ty.Tuple[int, str]] = []
        self._config: ConfigDict = {}

    @property
    def config_dict(self) -> ConfigDict:
        """Current configuration options that are set for each setting."""
        return self._config

    def consume_init_log(self):
        """Consumes initialization log."""
        init_log = self._init_log
        self._init_log = []
        return init_log

    def _log(self, level: int, message: str):
        self._init_log.append((level, message))

    def load(self, path: ty.Optional[Path] = None):
        """Loads configuration file from given `path`. If `path` is not specified, tries
        to load from the default location (USER_CONFIG_FILE_PATH).

        Raises:
            ConfigLoadFailure: The config file being loaded is corrupt or invalid,
            or `path` was specified but does not exist.
        """
        # Validate `path`, or if not provided, use USER_CONFIG_FILE_PATH if it exists.
        if path:
            self._log(logging.INFO, "Loading config from file: %s" % path)
            if not path.exists():
                self._log(logging.ERROR, "File not found: %s" % path)
                raise ConfigLoadFailure(self._init_log)
        else:
            # Gracefully handle the case where there isn't a user config file.
            if not USER_CONFIG_FILE_PATH.exists():
                self._log(logging.DEBUG, "User config file not found.")
                return
            path = USER_CONFIG_FILE_PATH
            self._log(logging.INFO, "Loading user config file:\n  %s" % path)
        # Try to load and parse the config file at `path`.
        config = ConfigParser()
        try:
            config_file_contents = "[%s]\n%s" % (DEFAULTSECT, open(path).read())
            config.read_string(config_file_contents, source=str(path))
        except ParsingError as ex:
            raise ConfigLoadFailure(self._init_log, reason=ex) from ex
        except OSError as ex:
            raise ConfigLoadFailure(self._init_log, reason=ex) from ex
        self._parse_config(config)
        if any(level >= logging.ERROR for level, _ in self._init_log):
            raise ConfigLoadFailure(self._init_log)

    def _migrate_deprecated(self, config: ConfigParser):
        migrated_options = [opt for opt in config[DEFAULTSECT] if opt in MIGRATED_CONFIG_OPTION]
        for migrated in migrated_options:
            replacement = MIGRATED_CONFIG_OPTION[migrated]
            if replacement in config[DEFAULTSECT]:
                self._log(
                    logging.WARNING,
                    f"WARNING: deprecated config option {migrated} was overriden by {replacement}.",
                )
            else:
                self._log(
                    logging.WARNING,
                    f"WARNING: config option {migrated} is deprecated, use {replacement} instead.",
                )
                config[DEFAULTSECT][replacement] = config[DEFAULTSECT][migrated]
            del config[DEFAULTSECT][migrated]
        deprecated_options = [opt for opt in config[DEFAULTSECT] if opt in DEPRECATED_CONFIG_OPTION]
        for deprecated in deprecated_options:
            self._log(logging.WARNING, f"WARNING: {DEPRECATED_CONFIG_OPTION[deprecated]}")

    def _parse_config(
        self, config: ConfigParser
    ) -> ty.Tuple[ty.Optional[ConfigDict], ty.List[ty.Tuple[int, str]]]:
        """Process the given configuration into a key-value mapping.

        Returns:
            Configuration mapping and list of any processing errors in human readable form.
        """
        if config.sections():
            self._log(
                logging.ERROR,
                "Invalid config file: must not contain any sections, found:\n  %s"
                % (", ".join(["[%s]" % section for section in config.sections()])),
            )
            return

        self._migrate_deprecated(config)

        for option in config[DEFAULTSECT]:
            if option not in CONFIG_MAP:
                self._log(logging.ERROR, "Unsupported config option: %s" % (option))
                continue
            try:
                value_type = None
                if isinstance(CONFIG_MAP[option], bool):
                    value_type = "yes/no value"
                    self._config[option] = config.getboolean(DEFAULTSECT, option)
                    continue
                elif isinstance(CONFIG_MAP[option], int):
                    value_type = "integer"
                    self._config[option] = config.getint(DEFAULTSECT, option)
                    continue
                elif isinstance(CONFIG_MAP[option], float):
                    value_type = "number"
                    self._config[option] = config.getfloat(DEFAULTSECT, option)
                    continue
            except ValueError as _:
                self._log(
                    logging.ERROR,
                    "Invalid setting for %s. Value is not a valid %s." % (option, value_type),
                )
                self._log(logging.DEBUG, "%s = %s" % (option, config.get(DEFAULTSECT, option)))
                continue

            # Handle custom validation types.
            config_value = config.get(DEFAULTSECT, option)
            default = CONFIG_MAP[option]
            option_type = type(default)
            if issubclass(option_type, ValidatedValue):
                try:
                    self._config[option] = option_type.from_config(
                        config_value=config_value, default=default
                    )
                except OptionParseFailure as ex:
                    self._log(
                        logging.ERROR,
                        "Invalid setting for %s: %s\n%s" % (option, config_value, ex.error),
                    )
                continue

            # If we didn't process the value as a given type, handle it as a string. We also
            # replace newlines with spaces, and strip any remaining leading/trailing whitespace.
            if value_type is None:
                config_value = config.get(DEFAULTSECT, option).replace("\n", " ").strip()
                if option in CHOICE_MAP:
                    if config_value.lower() not in [
                        choice.lower() for choice in CHOICE_MAP[option]
                    ]:
                        self._log(
                            logging.ERROR,
                            "Invalid setting for %s:\n  %s\nMust be one of: %s."
                            % (
                                option,
                                config.get(DEFAULTSECT, option),
                                ", ".join(choice for choice in CHOICE_MAP[option]),
                            ),
                        )
                        continue
                self._config[option] = config_value
                continue

    def is_default(self, option: str) -> bool:
        """True if the option is default, i.e. is NOT set by the user."""
        return option not in self._config

    def get(
        self,
        option: str,
        override: ty.Optional[ConfigValue] = None,
        ignore_default: bool = False,
    ) -> ConfigValue:
        """Get the current setting or default value of the specified option."""
        assert option in CONFIG_MAP
        if override is not None:
            return override
        if option in self._config:
            value = self._config[option]
        else:
            value = CONFIG_MAP[option]
            if ignore_default:
                return None
        if issubclass(type(value), ValidatedValue):
            return value.value  # Extract validated value.
        return value

    def get_help_string(self, option: str, show_default: ty.Optional[bool] = None) -> str:
        """Get string for help text including the option's value, if set, otherwise the default.

        Arguments:
            option: Command-line option whose name matches an entry in CONFIG_MAP.
            show_default: Always show default value. If None, only shows default value
                if the type is not a flag (boolean). It will still be displayed if set.
        """
        assert option in CONFIG_MAP
        is_flag = isinstance(CONFIG_MAP[option], bool)
        if option in self._config:
            if is_flag:
                value_str = "on" if self._config[option] else "off"
            else:
                value_str = str(self._config[option])
            return " [setting: %s]" % (value_str)
        if show_default is False or (
            show_default is None and is_flag and CONFIG_MAP[option] is False
        ):
            return ""
        return " [default: %s]" % (str(CONFIG_MAP[option]))
