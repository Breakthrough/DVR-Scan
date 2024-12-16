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
"""Shared code for region validation."""

import typing as ty
from collections import namedtuple

Point = namedtuple("Point", ["x", "y"])
Size = namedtuple("Size", ["w", "h"])


class RegionValidator:
    """Validator for a set of points representing a closed polygon."""

    _IGNORE_CHARS = [",", "/", "(", ")", "[", "]"]
    """Characters to ignore."""

    def __init__(self, value: str):
        translation_table = str.maketrans({char: " " for char in RegionValidator._IGNORE_CHARS})
        values = value.translate(translation_table).split()
        if not all([val.isdigit() for val in values]):
            raise ValueError(
                "Regions can only contain numbers and the following characters:"
                f" , / ( )\n  Input: {value}"
            )
        if not len(values) % 2 == 0:
            raise ValueError(f"Could not parse region, missing X or Y component.\n  Input: {value}")
        if not len(values) >= 6:
            raise ValueError(f"Regions must have at least 3 points.\n  Input: {value}")

        self._value = [Point(int(x), int(y)) for x, y in zip(values[0::2], values[1::2])]

    @property
    def value(self) -> ty.List[Point]:
        return self._value

    def __repr__(self) -> str:
        return repr(self.value)

    def __str__(self) -> str:
        return ", ".join(f"P({x},{y})" for x, y in self._value)


def load_regions(path: ty.AnyStr) -> ty.Iterable[RegionValidator]:
    region_data = None
    with open(path) as file:
        region_data = file.readlines()
    if region_data:
        return list(
            RegionValidator(region).value
            for region in filter(None, (region.strip() for region in region_data))
        )
    return []


def bound_point(point: Point, size: Size) -> Point:
    return Point(min(max(0, point.x), size.w), min(max(0, point.y), size.h))
