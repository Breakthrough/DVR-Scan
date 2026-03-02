#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
#

# This script generates a headless (no GUI) version of the package
# by modifying the pyproject.toml file. When the project is next built,
# the headless variant will be used.
#
# *WARNING*: This modifies the existing pyproject.toml file in place.
# The changes must be reverted to restore the full package.
#

import os
import re

# Correctly locate pyproject.toml relative to the script's location
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
pyproject_path = os.path.join(project_root, "pyproject.toml")

with open(pyproject_path, "r") as f:
    content = f.read()

# Rename package to headless variant
assert 'name = "dvr-scan"' in content
content = content.replace('name = "dvr-scan"', 'name = "dvr-scan-headless"', 1)

# Remove dvr-scan-app entry point
assert "dvr-scan-app" in content
content = re.sub(r'^dvr-scan-app\s*=.*\n', "", content, flags=re.MULTILINE)

# Swap GUI opencv for headless opencv
assert "opencv-contrib-python<4.13" in content
content = content.replace('"opencv-contrib-python<4.13"', '"opencv-contrib-python-headless<4.13"', 1)

# Remove screeninfo (GUI dependency)
assert "screeninfo" in content
content = re.sub(r'^\s*"screeninfo",?\n', "", content, flags=re.MULTILINE)

with open(pyproject_path, "w") as f:
    f.write(content)

print("Successfully generated headless pyproject.toml.")
