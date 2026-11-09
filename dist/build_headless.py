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
content = re.sub(r"^dvr-scan-app\s*=.*\n", "", content, flags=re.MULTILINE)

# Swap GUI opencv for headless opencv
assert '"opencv-contrib-python"' in content
content = content.replace('"opencv-contrib-python"', '"opencv-contrib-python-headless"', 1)

# scenedetect-headless depends on opencv-python-headless instead of opencv-python (same
# version constraints otherwise), so the headless package pulls in no GUI OpenCV build.
assert '"scenedetect[pyav]' in content
content = content.replace('"scenedetect[pyav]', '"scenedetect-headless[pyav]', 1)

# Drop the direct opencv-python dependency (see the comment in pyproject.toml): the
# headless OpenCV build is pulled in through scenedetect-headless.
assert re.search(r'^\s*"opencv-python",\n', content, flags=re.MULTILINE)
content = re.sub(r'^\s*"opencv-python",\n', "", content, count=1, flags=re.MULTILINE)

# Remove screeninfo (GUI dependency)
assert "screeninfo" in content
content = re.sub(r'^\s*"screeninfo",?\n', "", content, flags=re.MULTILINE)

# Remove tkinterdnd2 (GUI dependency)
assert "tkinterdnd2" in content
content = re.sub(r'^\s*"tkinterdnd2",?\n', "", content, flags=re.MULTILINE)

with open(pyproject_path, "w") as f:
    f.write(content)

print("Successfully generated headless pyproject.toml.")
