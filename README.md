![DVR-Scan Logo](https://raw.githubusercontent.com/Breakthrough/DVR-Scan/main/docs/assets/dvr-scan-logo.png)

:vhs: Find and extract motion events in videos.

------------------------------------------------

### Latest Release: v1.6 (October 15, 2023)

**Website**: [dvr-scan.com](https://www.dvr-scan.com)

**User Guide**: [dvr-scan.com/guide](https://www.dvr-scan.com/guide/)

**Documentation**: [dvr-scan.com/docs](https://www.dvr-scan.com/docs/)

------------------------------------------------------

DVR-Scan is a command-line application that **automatically detects motion events in video files** (e.g. security camera footage).  DVR-Scan looks for areas in footage containing motion, and saves each event to a separate video clip.  DVR-Scan is free and open-source software, and works on Windows, Linux, and Mac.

## Quick Install

    pip install dvr-scan[opencv] --upgrade

Windows builds are also available on [the Downloads page](https://www.dvr-scan.com/download/).

## Quickstart

Scan `video.mp4` (separate clips for each event):

    dvr-scan -i video.mp4

Select a region to scan using [the region editor](https://www.dvr-scan.com/guide/):

    dvr-scan -i video.mp4 -r

<img alt="example of region editor" src="https://raw.githubusercontent.com/Breakthrough/DVR-Scan/releases/1.6/docs/assets/region-editor-mask.jpg" width="480"/>

Select a region to scan using command line (list of points as X Y):

    dvr-scan -i video.mp4 -a 50 50 100 50 100 100 100 50

Draw boxes around motion:

    dvr-scan -i video.mp4 -bb

<img alt="example of bounding boxes" src="https://raw.githubusercontent.com/Breakthrough/DVR-Scan/releases/1.6/docs/assets/bounding-box.gif" width="480"/>

Use `ffmpeg` to extract events:

    dvr-scan -i video.mp4 -m ffmpeg

See [the documentation](docs.md) for a complete list of all command-line and configuration file options which can be set. You can also type `dvr-scan --help` for an overview of command line options. Some program options can also be set [using a config file](docs.md#config-file).

------------------------------------------------

Copyright © 2016-2023 Brandon Castellano. All rights reserved.
Licensed under BSD 2-Clause (see the LICENSE file for details).
