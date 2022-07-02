# -*- coding: utf-8 -*-
#
#         PySceneDetect: Python-Based Video Scene Detector
#   ---------------------------------------------------------------
#     [  Site:   http://www.scenedetect.scenedetect.com/         ]
#     [  Docs:   http://manual.scenedetect.scenedetect.com/      ]
#     [  Github: https://github.com/Breakthrough/PySceneDetect/  ]
#
# Copyright (C) 2014-2022 Brandon Castellano <http://www.bcastell.com>.
# PySceneDetect is licensed under the BSD 3-Clause License; see the
# included LICENSE file, or visit one of the above pages for details.
#
"""``dvr_scan.cli.config`` Module

Handles loading configuration files from disk and validating each setting. Only validation
of the config file schema and data types are performed. Constants/defaults are also defined
here where possible and re-used by the CLI so that there is one source of truth.
"""

from abc import ABC, abstractmethod
import logging
import os
import os.path
from configparser import ConfigParser, ParsingError, DEFAULTSECT
from typing import Any, AnyStr, Dict, List, Optional, Tuple, Union

from platformdirs import user_config_dir
from scenedetect.frame_timecode import FrameTimecode

from dvr_scan.scanner import DEFAULT_FFMPEG_OUTPUT_ARGS


class ValidatedValue(ABC):
    """Used to represent configuration values that must be validated against constraints."""

    @property
    @abstractmethod
    def value(self) -> Any:
        """Get the value after validation."""
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def from_config(config_value: str, default: 'ValidatedValue') -> 'ValidatedValue':
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

    def __init__(self, value: Union[int, float, str]):
        # Ensure value is a valid timecode.
        FrameTimecode(timecode=value, fps=100.0)
        self._value = value

    @property
    def value(self) -> Union[int, float, str]:
        return self._value

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

    @staticmethod
    def from_config(config_value: str, default: 'TimecodeValue') -> 'TimecodeValue':
        try:
            return TimecodeValue(config_value)
        except ValueError as ex:
            raise OptionParseFailure(
                'Timecodes must be in frames (1234), seconds (123.4s), or HH:MM:SS (00:02:03.400).'
            ) from ex


class RangeValue(ValidatedValue):
    """Validator for int/float ranges. `min_val` and `max_val` are inclusive."""

    def __init__(
        self,
        value: Union[int, float],
        min_val: Union[int, float],
        max_val: Union[int, float],
    ):
        if value < min_val or value > max_val:
            # min and max are inclusive.
            raise ValueError()
        self._value = value
        self._min_val = min_val
        self._max_val = max_val

    @property
    def value(self) -> Union[int, float]:
        return self._value

    @property
    def min_val(self) -> Union[int, float]:
        """Minimum value of the range."""
        return self._min_val

    @property
    def max_val(self) -> Union[int, float]:
        """Maximum value of the range."""
        return self._max_val

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

    @staticmethod
    def from_config(config_value: str, default: 'RangeValue') -> 'RangeValue':
        try:
            return RangeValue(
                value=int(config_value) if isinstance(default.value, int) else float(config_value),
                min_val=default.min_val,
                max_val=default.max_val,
            )
        except ValueError as ex:
            raise OptionParseFailure('Value must be between %s and %s.' %
                                     (default.min_val, default.max_val)) from ex


class KernelSizeValue(ValidatedValue):
    """Validator for kernel sizes (odd integer > 1, or -1 for auto size)."""

    def __init__(self, value: int = -1):
        if value == -1:
            # Downscale factor of -1 maps to None internally for auto downscale.
            value = None
        elif value < 0:
            # Disallow other negative values.
            raise ValueError()
        elif value % 2 == 0:
            # Disallow even values.
            raise ValueError()
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        if self.value is None:
            return 'auto'
        return str(self.value)

    @staticmethod
    def from_config(config_value: str, default: 'KernelSizeValue') -> 'KernelSizeValue':
        try:
            return KernelSizeValue(int(config_value))
        except ValueError as ex:
            raise OptionParseFailure(
                'Value must be an odd integer greater than 1, or set to -1 for auto kernel size.'
            ) from ex


class ROIValue(ValidatedValue):
    """Validator for region-of-interest values."""

    _IGNORE_CHARS = [',', '/', '(', ')']
    """Characters to ignore."""

    def __init__(self, value: Optional[str] = None, allow_point: bool = False):
        if value is not None:
            translation_table = str.maketrans({char: ' ' for char in ROIValue._IGNORE_CHARS})
            values = value.translate(translation_table).split()
            valid_lengths = (
                2,
                4,
            ) if allow_point else (4,)
            if not (len(values) in valid_lengths and all([val.isdigit() for val in values])
                    and all([int(val) >= 0 for val in values])):
                raise ValueError()
            self._value = [int(val) for val in values]
        else:
            self._value = None

    @property
    def value(self) -> Optional[List[int]]:
        return self._value

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        if self.value is not None:
            return '(%d,%d)/(%d,%d)' % (self.value[0], self.value[1], self.value[2], self.value[3])
        return str(self.value)

    @staticmethod
    def from_config(config_value: str, default: 'ROIValue') -> 'ROIValue':
        try:
            return ROIValue(config_value)
        except ValueError as ex:
            raise OptionParseFailure('ROI must be four positive integers of the form (x,y)/(w,h).'
                                     ' Brackets, commas, slashes, and spaces are optional.') from ex


class RGBValue(ValidatedValue):
    """Validator for RGB values of the form (255, 255, 255) or 0xFFFFFF."""

    _IGNORE_CHARS = [',', '/', '(', ')']
    """Characters to ignore."""

    def __init__(self, value: Union[int, str]):
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
        if not isinstance(value, int) and value[0:2] in ('0x', '0X'):
            value = int(value, base=16)
        # Finally try to process in the form '(255, 255, 255)'.
        if not isinstance(value, int):
            translation_table = str.maketrans({char: ' ' for char in RGBValue._IGNORE_CHARS})
            values = value.translate(translation_table).split()
            if not (len(values) == 3 and all([val.isdigit() for val in values])
                    and all([int(val) >= 0 for val in values])):
                raise ValueError()
            value = int(values[0]) << 16 | int(values[1]) << 8 | int(values[2])
        assert isinstance(value, int)
        if value < 0x000000 or value > 0xFFFFFF:
            raise ValueError('RGB value must be between 0x000000 and 0xFFFFFF.')
        # Convert into tuple of (R, G, B)
        self._value = (
            (value & 0xFF0000) >> 16,
            (value & 0x00FF00) >> 8,
            (value & 0x0000FF),
        )

    @property
    def value(self) -> Tuple[int, int, int]:
        return self._value

    @property
    def value_as_int(self) -> int:
        """Return value in integral (binary) form as opposed to tuple of R,G,B."""
        return int(self.value[0]) << 16 | int(self.value[1]) << 8 | int(self.value[2])

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return '0x%06x' % self.value_as_int

    @staticmethod
    def from_config(config_value: str, default: 'RGBValue') -> 'RGBValue':
        try:
            return RGBValue(config_value)
        except ValueError as ex:
            raise OptionParseFailure(
                'Color values must be in hex (0xFFFFFF) or R,G,B (255,255,255).') from ex


ConfigValue = Union[bool, int, float, str]
ConfigDict = Dict[str, ConfigValue]

_CONFIG_FILE_NAME: AnyStr = 'dvr-scan.cfg'
_CONFIG_FILE_DIR: AnyStr = user_config_dir("DVR-Scan", False)

USER_CONFIG_FILE_PATH: AnyStr = os.path.join(_CONFIG_FILE_DIR, _CONFIG_FILE_NAME)

CONFIG_MAP: ConfigDict = {
                                                         # General Options
    'quiet-mode': False,
    'verbosity': 'info',
                                                         # Input/Output
    'output-dir': '',
    'output-mode': 'opencv',
    'ffmpeg-output-args': DEFAULT_FFMPEG_OUTPUT_ARGS,
    'opencv-codec': 'XVID',
                                                         # Motion Events
    'min-event-length': TimecodeValue(2),
    'time-before-event': TimecodeValue('1.5s'),
    'time-post-event': TimecodeValue('2.0s'),
                                                         # Detection Parameters
    'bg-subtractor': 'MOG',
    'threshold': 0.15,
    'kernel-size': KernelSizeValue(),
    'downscale-factor': 0,
    'region-of-interest': ROIValue(),
    'frame-skip': 0,
                                                         # Overlays
    'timecode': False,
    'timecode-margin': 5,
    'timecode-font-scale': 1.0,
    'timecode-font-thickness': 2,
    'timecode-font-color': RGBValue(0xFFFFFF),
    'timecode-bg-color': RGBValue(0x000000),
    'bounding-box': False,
    'bounding-box-smooth-time': TimecodeValue('0.1s'),
    'bounding-box-color': RGBValue(0xFF0000),
    'bounding-box-thickness': 0.0032,
    'bounding-box-min-size': 0.032,
}
"""Mapping of valid configuration file parameters and their default values or placeholders.
The types of these values are used when decoding the configuration file. Valid choices for
certain string options are stored in `CHOICE_MAP`."""

# TODO: This should be a validator.
CHOICE_MAP: Dict[str, List[str]] = {
    'opencv-codec': ['XVID', 'MP4V', 'MP42', 'H264'],
    'output-mode': ['scan_only', 'opencv', 'copy', 'ffmpeg'],
    'verbosity': ['debug', 'info', 'warning', 'error'],
    'bg-subtractor': ['MOG', 'CNT', 'MOG_CUDA'],
}
"""Mapping of string options which can only be of a particular set of values. We use a list instead
of a set to preserve order when generating error contexts. Values are case-insensitive, and must be
in lowercase in this map."""


def _validate_structure(config: ConfigParser) -> List[str]:
    """Validates the layout of the option mapping.

    Returns:
        List of any parsing errors in human-readable form.
    """
    errors: List[str] = []
    for (option_name, _) in config.items(DEFAULTSECT):
        if not option_name in CONFIG_MAP:
            errors.append('Unsupported config option: %s' % (option_name))
    return errors


def _parse_config(config: ConfigParser) -> Tuple[ConfigDict, List[str]]:
    """Process the given configuration into a key-value mapping.

    Returns:
        Configuration mapping and list of any processing errors in human readable form.
    """
    out_map: ConfigDict = {}
    errors: List[str] = []
    sections = config.sections()
    if sections:
        errors.append(
            'Invalid config file: must not contain any sections, found:\n  %s' %
            (', '.join(['[%s]' % section for section in sections if section != DEFAULTSECT])))
        return out_map, errors

    for option in CONFIG_MAP:
        if option in config[DEFAULTSECT]:
            try:
                value_type = None
                if isinstance(CONFIG_MAP[option], bool):
                    value_type = 'yes/no value'
                    out_map[option] = config.getboolean(DEFAULTSECT, option)
                    continue
                elif isinstance(CONFIG_MAP[option], int):
                    value_type = 'integer'
                    out_map[option] = config.getint(DEFAULTSECT, option)
                    continue
                elif isinstance(CONFIG_MAP[option], float):
                    value_type = 'number'
                    out_map[option] = config.getfloat(DEFAULTSECT, option)
                    continue
            except ValueError as _:
                errors.append('Invalid setting for %s:\n  %s\nValue is not a valid %s.' %
                              (option, config.get(DEFAULTSECT, option), value_type))
                continue

            # Handle custom validation types.
            config_value = config.get(DEFAULTSECT, option)
            default = CONFIG_MAP[option]
            option_type = type(default)
            if issubclass(option_type, ValidatedValue):
                try:
                    out_map[option] = option_type.from_config(
                        config_value=config_value, default=default)
                except OptionParseFailure as ex:
                    errors.append('Invalid setting for %s:\n  %s\n%s' %
                                  (option, config_value, ex.error))
                continue

            # If we didn't process the value as a given type, handle it as a string. We also
            # replace newlines with spaces, and strip any remaining leading/trailing whitespace.
            if value_type is None:
                config_value = config.get(DEFAULTSECT, option).replace('\n', ' ').strip()
                if option in CHOICE_MAP:
                    if config_value.lower() not in [
                            choice.lower() for choice in CHOICE_MAP[option]
                    ]:
                        errors.append('Invalid setting for %s:\n  %s\nMust be one of: %s.' %
                                      (option, config.get(DEFAULTSECT, option), ', '.join(
                                          choice for choice in CHOICE_MAP[option])))
                        continue
                out_map[option] = config_value
                continue

    return (out_map, errors)


class ConfigLoadFailure(Exception):
    """Raised when a user-specified configuration file fails to be loaded or validated."""

    def __init__(self, init_log: Tuple[int, str], reason: Optional[Exception] = None):
        super().__init__()
        self.init_log = init_log
        self.reason = reason


class ConfigRegistry:
    """Provides application option values based on either user-specified configuration, or
    default values specified in the global CONFIG_MAP."""

    def __init__(self, path: Optional[str] = None):
        """Loads configuration file from given `path`. If `path` is not specified, tries
        to load from the default location (USER_CONFIG_FILE_PATH).

        Raises:
            ConfigLoadFailure: The config file being loaded is corrupt or invalid,
            or `path` was specified but does not exist.
        """
        self._init_log: List[Tuple[int, str]] = []
        self._config: ConfigDict = {} # Options set in the loaded config file.
        self._load_from_disk(path)

    @property
    def config_dict(self) -> ConfigDict:
        """Current configuration options that are set for each setting."""
        return self._config

    def get_init_log(self):
        """Get initialization log. Consumes the log, so subsequent calls will return None."""
        init_log = self._init_log
        self._init_log = []
        return init_log

    def _log(self, log_level, log_str):
        self._init_log.append((log_level, log_str))

    def _load_from_disk(self, path=None):
        # Validate `path`, or if not provided, use USER_CONFIG_FILE_PATH if it exists.
        if path:
            self._init_log.append((logging.INFO, "Loading config from file:\n  %s" % path))
            if not os.path.exists(path):
                self._init_log.append((logging.ERROR, "File not found: %s" % (path)))
                raise ConfigLoadFailure(self._init_log)
        else:
            # Gracefully handle the case where there isn't a user config file.
            if not os.path.exists(USER_CONFIG_FILE_PATH):
                self._init_log.append((logging.DEBUG, "User config file not found."))
                return
            path = USER_CONFIG_FILE_PATH
            self._init_log.append((logging.INFO, "Loading user config file:\n  %s" % path))
        # Try to load and parse the config file at `path`.
        config = ConfigParser()
        try:
            config_file_contents = '[%s]\n%s' % (DEFAULTSECT, open(path, 'r').read())
            config.read_string(config_file_contents, source=path)
        except ParsingError as ex:
            raise ConfigLoadFailure(self._init_log, reason=ex)
        except OSError as ex:
            raise ConfigLoadFailure(self._init_log, reason=ex)
        # At this point the config file syntax is correct, but we need to still validate
        # the parsed options (i.e. that the options have valid values).
        errors = _validate_structure(config)
        if not errors:
            self._config, errors = _parse_config(config)
        if errors:
            for log_str in errors:
                self._init_log.append((logging.ERROR, log_str))
            raise ConfigLoadFailure(self._init_log)

    def is_default(self, option: str) -> bool:
        """True if the option is default, i.e. is NOT set by the user."""
        return not option in self._config

    def get_value(self,
                  option: str,
                  override: Optional[ConfigValue] = None,
                  ignore_default: bool = False) -> ConfigValue:
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
            return value.value # Extract validated value.
        return value

    def get_help_string(self, option: str, show_default: Optional[bool] = None) -> str:
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
                value_str = 'on' if self._config[option] else 'off'
            else:
                value_str = str(self._config[option])
            return ' [setting: %s]' % (value_str)
        if show_default is False or (show_default is None and is_flag
                                     and CONFIG_MAP[option] is False):
            return ''
        return ' [default: %s]' % (str(CONFIG_MAP[option]))
