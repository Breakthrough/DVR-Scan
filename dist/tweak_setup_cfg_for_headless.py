#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
#

# This script generates a headless (no GUI) version of the package
# by modifying the setup.cfg file. When the project is next built,
# the headless variant will be used.
#
# *WARNING*: This modifies the existing setup.cfg file in place.
# The changes must be reverted to restore the full package.
#

import configparser
import os

COPYRIGHT_TEXT = """#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
#

"""

# Correctly locate setup.cfg relative to the script's location
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
setup_cfg_path = os.path.join(project_root, "setup.cfg")

# Read setup.cfg
config = configparser.ConfigParser()
# Preserve case of keys
config.optionxform = str
config.read(setup_cfg_path)

assert config.has_option("metadata", "name")
name = config.get("metadata", "name")
config.set("metadata", "name", f"{name}-Headless")

# Remove dvr-scan-app from console_scripts
assert config.has_section("options.entry_points")
assert config.has_option("options.entry_points", "console_scripts")
scripts = config.get("options.entry_points", "console_scripts").splitlines()
scripts = [s.strip() for s in scripts if s.strip() and "dvr-scan-app" not in s]
config.set("options.entry_points", "console_scripts", "\n" + "\n".join(scripts))

# Write back to setup.cfg
with open(setup_cfg_path, "w") as configfile:
    configfile.write(COPYRIGHT_TEXT)
    config.write(configfile)

print("Successfully generated headless setup.cfg.")
