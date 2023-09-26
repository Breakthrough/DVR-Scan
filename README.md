![DVR-Scan Logo](https://raw.githubusercontent.com/Breakthrough/DVR-Scan/main/docs/assets/dvr-scan-logo.png)

:vhs: Find and extract motion events in videos.

------------------------------------------------

### Latest Release: v1.5.1 (August 15, 2022)

**Website**: [dvr-scan.com](https://www.dvr-scan.com)

**Documentation**: [dvr-scan.com/docs](https://www.dvr-scan.com/docs/)

------------------------------------------------------

DVR-Scan is a command-line application that **automatically detects motion events in video files** (e.g. security camera footage).  DVR-Scan looks for areas in footage containing motion, and saves each event to a separate video clip.  DVR-Scan is free and open-source software, and works on Windows, Linux, and Mac.

## Quick Install

    pip install dvr-scan[opencv] --upgrade

Windows builds are also available on [the Downloads page](https://www.dvr-scan.com/download/).

## Quickstart

![example](https://raw.githubusercontent.com/Breakthrough/DVR-Scan/main/docs/assets/bounding-box.gif)

Scan `video.mp4` (separate clips for each event):

    dvr-scan -i video.mp4

Only scan a region of interest (select with mouse):

    dvr-scan -i video.mp4 -roi

Draw boxes around motion:

    dvr-scan -i video.mp4 -bb

Use `ffmpeg` to extract events:

    dvr-scan -i video.mp4 -m ffmpeg

See [the documentation](docs.md) for a complete list of all command-line and configuration file options which can be set. You can also type `dvr-scan --help` for an overview of command line options. Some program options can also be set [using a config file](docs.md#config-file).

------------------------------------------------

Copyright © 2016-2022 Brandon Castellano. All rights reserved.
Licensed under BSD 2-Clause (see the LICENSE file for details).
