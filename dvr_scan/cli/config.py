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

Handles loading configuration files from disk and validating each section. Only validation
of the config file schema and data types are performed. Constants/defaults are also defined
here where possible and re-used by the CLI so that there is one source of truth.
"""

from abc import ABC, abstractmethod
import logging
import os
import os.path
from configparser import ConfigParser, ParsingError
from typing import AnyStr, Dict, List, Optional, Tuple, Union

from appdirs import user_config_dir

from scenedetect.frame_timecode import FrameTimecode


class ValidatedValue(ABC):
    """Used to represent configuration values that must be validated against constraints."""

    @staticmethod
    @abstractmethod
    def from_config(config: ConfigParser, section: str, option: str,
                    default: 'ValidatedValue') -> 'ValidatedValue':
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
    """Validator for timecode values in frames (1234), seconds (123.4s), or HH:MM:SS."""

    def __init__(self, value: Union[int, str]):
        self.value = value
        # Ensure value is a valid timecode.
        FrameTimecode(timecode=value, fps=100.0)

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

    @staticmethod
    def from_config(config: ConfigParser, section: str, option: str,
                    default: 'TimecodeValue') -> 'TimecodeValue':
        raw_value = config.get(section, option).replace('\n', ' ').strip()
        try:
            return TimecodeValue(raw_value)
        except ValueError as ex:
            raise OptionParseFailure(
                'Invalid [%s] value for %s: %s is not a valid timecode. Timecodes'
                ' must be in frames (1234), seconds (123.4s), or HH:MM:SS'
                ' (00:02:03.400).' % (section, option, raw_value)) from ex


class RangeValue(ValidatedValue):
    """Validator for int/float ranges. `min_val` and `max_val` are inclusive."""

    def __init__(self, value: Union[int, float], min_val: Union[int, float], max_val: Union[int,
                                                                                            float]):
        self.value = value
        if value < min_val or value > max_val:
            # min and max are inclusive.
            raise ValueError()
        self.min_val = min_val
        self.max_val = max_val

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

    @staticmethod
    def from_config(config: ConfigParser, section: str, option: str,
                    default: 'RangeValue') -> 'RangeValue':

        raw_value = (
            config.getint(section, option) if isinstance(default.value, int) else config.getfloat(
                section, option))
        try:
            return RangeValue(raw_value, default.min_val, default.max_val)
        except ValueError as ex:
            raise OptionParseFailure(
                'Invalid [%s] value for %s: %s. Value must be between %s and %s.' %
                ((section, option, raw_value, default.min_val, default.max_val))) from ex


class KernelSizeValue(ValidatedValue):
    """Validator for kernel sizes (odd integer > 1, or -1 for auto size)."""

    def __init__(self, value: int = -1):
        self.value = value
        if self.value == -1:
            # Downscale factor of -1 maps to None internally for auto downscale.
            self.value = None
        elif value % 2 == 0:
            raise ValueError()

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        if self.value is None:
            return 'auto'
        return str(self.value)

    @staticmethod
    def from_config(config: ConfigParser, section: str, option: str,
                    default: 'KernelSizeValue') -> 'KernelSizeValue':
        raw_value = config.getint(section, option)
        try:
            return KernelSizeValue(raw_value)
        except ValueError as ex:
            raise OptionParseFailure(
                'Invalid [%s] value for %s: %s. Value must be an odd integer greater than 1, or -1 for auto kernel size.'
                % ((section, option, raw_value))) from ex


class ROIValue(ValidatedValue):
    """Validator for region-of-interest values."""

    _IGNORE_CHARS = [',', '/', '(', ')']
    """Characters to ignore."""

    def __init__(self, value: Optional[str] = None, allow_point: bool = False):
        if value is not None:
            values = ROIValue.parse_raw(value)
            valid_lengths = (
                2,
                4,
            ) if allow_point else (4,)
            if not (len(values) in valid_lengths and all([val.isdigit() for val in values])
                    and all([int(val) >= 0 for val in values])):
                raise ValueError()
            self.value = [int(val) for val in values]
        else:
            self.value = None

    @staticmethod
    def parse_raw(value: str) -> List[int]:
        translation_table = str.maketrans({char: ' ' for char in ROIValue._IGNORE_CHARS})
        return value.translate(translation_table).split()

    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        if self.value is not None:
            return '(%d,%d)/(%d,%d)' % (self.value[0], self.value[1], self.value[2], self.value[3])
        return str(self.value)

    @staticmethod
    def from_config(config: ConfigParser, section: str, option: str,
                    default: 'ROIValue') -> 'ROIValue':
        raw_value = config.get(section, option)
        try:
            return ROIValue(raw_value)
        except ValueError as ex:
            raise OptionParseFailure(
                'Invalid [%s] value for %s: %s. ROI must be four positive integers of the form'
                ' (x,y)/(w,h). Brackets, commas, slashes, and spaces are optional.' %
                ((section, option, raw_value))) from ex


ConfigValue = Union[bool, int, float, str]
ConfigDict = Dict[str, Dict[str, ConfigValue]]

_CONFIG_FILE_NAME: AnyStr = 'dvr-scan.cfg'
_CONFIG_FILE_DIR: AnyStr = user_config_dir("DVR-Scan", False)

USER_CONFIG_FILE_PATH: AnyStr = os.path.join(_CONFIG_FILE_DIR, _CONFIG_FILE_NAME)

CONFIG_MAP: ConfigDict = {
    'program': {
        'opencv-codec': 'XVID',
        'quiet-mode': False,
        'verbosity': 'info',
    },
    'detection': {
        'bg-subtractor': 'MOG',
        'downscale-factor': 0,
        'frame-skip': 0,
        'kernel-size': KernelSizeValue(),
        'min-event-length': TimecodeValue(2),
        'region-of-interest': ROIValue(),
        'threshold': 0.15,
        'time-before-event': TimecodeValue('1.5s'),
        'time-post-event': TimecodeValue('2.0s'),
    },
    'overlays': {
        'bounding-box': False,
        'bounding-box-smooth-time': TimecodeValue(0.1),
    },
}
"""Mapping of valid configuration file parameters and their default values or placeholders.
The types of these values are used when decoding the configuration file. Valid choices for
certain string options are stored in `CHOICE_MAP`."""

# TODO: This should be a validator.
CHOICE_MAP: Dict[str, Dict[str, List[str]]] = {
    'program': {
        'verbosity': ['debug', 'info', 'warning', 'error'],
        'opencv-codec': ['XVID', 'MP4V', 'MP42', 'H264'],
    },
    'detection': {
        'bg-subtractor': ['MOG', 'CNT', 'MOG_CUDA'],
    },
}
"""Mapping of string options which can only be of a particular set of values. We use a list instead
of a set to preserve order when generating error contexts. Values are case-insensitive, and must be
in lowercase in this map."""


def _validate_structure(config: ConfigParser) -> List[str]:
    """Validates the layout of the section/option mapping.

    Returns:
        List of any parsing errors in human-readable form.
    """
    errors: List[str] = []
    for section in config.sections():
        if not section in CONFIG_MAP.keys():
            errors.append('Unsupported config section: [%s]' % (section))
            continue
        for (option_name, _) in config.items(section):
            if not option_name in CONFIG_MAP[section].keys():
                errors.append('Unsupported config option in [%s]: %s' % (section, option_name))
    return errors


def _parse_config(config: ConfigParser) -> Tuple[ConfigDict, List[str]]:
    """Process the given configuration into a key-value mapping.

    Returns:
        Configuration mapping and list of any processing errors in human readable form.
    """
    out_map: ConfigDict = {}
    errors: List[str] = []
    for section in CONFIG_MAP:
        out_map[section] = {}
        for option in CONFIG_MAP[section]:
            if section in config and option in config[section]:
                try:
                    value_type = None
                    if isinstance(CONFIG_MAP[section][option], bool):
                        value_type = 'yes/no value'
                        out_map[section][option] = config.getboolean(section, option)
                        continue
                    elif isinstance(CONFIG_MAP[section][option], int):
                        value_type = 'integer'
                        out_map[section][option] = config.getint(section, option)
                        continue
                    elif isinstance(CONFIG_MAP[section][option], float):
                        value_type = 'number'
                        out_map[section][option] = config.getfloat(section, option)
                        continue
                except ValueError as _:
                    errors.append('Invalid [%s] value for %s: %s is not a valid %s.' %
                                  (section, option, config.get(section, option), value_type))
                    continue

                # Handle custom validation types.
                default = CONFIG_MAP[section][option]
                option_type = type(default)
                if issubclass(option_type, ValidatedValue):
                    try:
                        new_value = option_type.from_config(
                            config=config,
                            section=section,
                            option=option,
                            default=default,
                        )
                        out_map[section][option] = new_value
                    except OptionParseFailure as ex:
                        errors.append(ex.error)
                    continue

                # If we didn't process the value as a given type, handle it as a string. We also
                # replace newlines with spaces, and strip any remaining leading/trailing whitespace.
                if value_type is None:
                    config_value = config.get(section, option).replace('\n', ' ').strip()
                    if section in CHOICE_MAP and option in CHOICE_MAP[section]:
                        if config_value.lower() not in [
                                choice.lower() for choice in CHOICE_MAP[section][option]
                        ]:
                            errors.append('Invalid [%s] value for %s: %s. Must be one of: %s.' %
                                          (section, option, config.get(section, option), ', '.join(
                                              choice for choice in CHOICE_MAP[section][option])))
                            continue
                    out_map[section][option] = config_value
                    continue

    return (out_map, errors)


class ConfigLoadFailure(Exception):

    def __init__(self, init_log: Tuple[int, str], reason: Optional[Exception] = None):
        super().__init__()
        self.init_log = init_log
        self.reason = reason


class ConfigRegistry:

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
        """Current configuration options that are set for each section."""
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
            result = config.read(path)
        except ParsingError as ex:
            raise ConfigLoadFailure(self._init_log, reason=ex)
        if not result:
            error_msg = "Failed to load config file. Check that the file is valid, and can be read."
            self._init_log.append((logging.ERROR, error_msg))
            raise ConfigLoadFailure(self._init_log)
        # At this point the config file syntax is correct, but we need to still validate
        # the parsed options (i.e. that the sections or options have valid values).
        errors = _validate_structure(config)
        if not errors:
            self._config, errors = _parse_config(config)
        if errors:
            for log_str in errors:
                self._init_log.append((logging.ERROR, log_str))
            raise ConfigLoadFailure(self._init_log)

    def is_default(self, section: str, option: str) -> bool:
        """True if the option is default, i.e. is NOT set by the user."""
        return not (section in self._config and option in self._config[section])

    def get_value(self,
                  section: str,
                  option: str,
                  override: Optional[ConfigValue] = None,
                  ignore_default: bool = False) -> ConfigValue:
        """Get the current setting or default value of the specified section option."""
        assert section in CONFIG_MAP and option in CONFIG_MAP[section]
        if override is not None:
            return override
        if section in self._config and option in self._config[section]:
            value = self._config[section][option]
        else:
            value = CONFIG_MAP[section][option]
            if ignore_default:
                return None
        if hasattr(value, 'value'):
            return value.value
        return value

    def get_help_string(self,
                        section: str,
                        option: str,
                        show_default: Optional[bool] = None) -> str:
        """Get string for help text including the option's value, if set, otherwise the default.

        Arguments:
            section: A section name or, "global" for global options.
            option: Command-line option to set within `section`.
            show_default: Always show default value. If None, only shows default value
                if the type is not a flag (boolean). It will still be displayed if set.
        """
        assert section in CONFIG_MAP and option in CONFIG_MAP[section]
        is_flag = isinstance(CONFIG_MAP[section][option], bool)
        if section in self._config and option in self._config[section]:
            if is_flag:
                value_str = 'on' if self._config[section][option] else 'off'
            else:
                value_str = str(self._config[section][option])
            return ' [setting: %s]' % (value_str)
        if show_default is False or (show_default is None and is_flag
                                     and CONFIG_MAP[section][option] is False):
            return ''
        return ' [default: %s]' % (str(CONFIG_MAP[section][option]))
