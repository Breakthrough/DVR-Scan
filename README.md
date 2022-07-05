# ![DVR-Scan Logo](https://raw.githubusercontent.com/Breakthrough/DVR-Scan/master/docs/img/dvr-scan-logo_small.png)
:vhs: Tool for extracting scenes with motion from security camera/DVR footage.  Written in Python, depends on OpenCV.

**Latest Release:** [v1.5-beta0 (July 4, 2022)](http://dvr-scan.readthedocs.io/en/v1.5/changelog/)

------------------------------------------------

### | [Download](http://dvr-scan.readthedocs.io/en/latest/download/) | [Install Guide](http://dvr-scan.readthedocs.io/en/latest/guide/installing/) | [Getting Started](http://dvr-scan.readthedocs.io/en/latest/guide/examples/) | [FAQ](http://dvr-scan.readthedocs.io/en/latest/faq/) | [Documentation](http://dvr-scan.readthedocs.io/) |

------------------------------------------------

**Quick Install**: Requires Python modules `numpy`, OpenCV `cv2`, and `tqdm` (optional) for displaying progress.  To install DVR-Scan via `pip` with all dependencies:

    pip install dvr-scan[opencv]

Or to install just DVR-Scan (OpenCV installation required):

    pip install dvr-scan

To test if you have the required prerequisites, open a `python` prompt, and run the following:

    import numpy
    import cv2

If both of those commands execute without any problems, you should be able to run DVR-Scan without any issues.

------------------------------------------------

**DVR-Scan** is a cross-platform command-line (CLI) application that **automatically detects motion events in video files** (e.g. security camera footage).  In addition to locating both the time and duration of each motion event, DVR-Scan will save the footage of each motion event to a new, separate video clip.  Not only is DVR-Scan free and open-source software (FOSS), written in Python, and based on Numpy and OpenCV, it was built to be extendable and hackable.

For users wanting finer control over the output video encoding method, the default timecode format (`HH:MM:SS.nnnn`) is compatible with most popular video tools, so in most cases the motion events DVR-Scan finds can be simply copied and pasted into another tool of your choice (e.g. `ffmpeg`, `avconv` or the `mkvtoolnix` suite).

------------------------------------------------

Copyright © 2016-2022 Brandon Castellano. All rights reserved.
Licensed under BSD 2-Clause (see the LICENSE file for details).
