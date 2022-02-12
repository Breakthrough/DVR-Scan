
<h1>Obtaining DVR-Scan</h1>

DVR-Scan is completely free software, and can be downloaded from the links below.  See the [license and copyright information](copyright.md) page for details.  If you have trouble running DVR-Scan, ensure that you have all the required dependencies listed on the [Installing & Updating](guide/installing.md) page.

**Important:** DVR-Scan v1.4 is the last release that is compatible with both Python 2 and 3.  Starting with v1.5, the minimum required Python version will be 3.6.

------------------------------------------------

## Download and Installation

### Install via pip &nbsp; <span class="wy-text-neutral"><span class="fa fa-windows"></span> &nbsp; <span class="fa fa-linux"></span> &nbsp; <span class="fa fa-apple"></span></span></h3>

<div class="important">
<h4 class="wy-text-neutral"><span class="fa fa-angle-double-down wy-text-info"></span> Including all dependencies (recommended):</h4>
<h3 class="wy-text-neutral"><tt>pip install dvr-scan[opencv]</tt></h3>
<h4 class="wy-text-neutral"><span class="fa fa-angle-down wy-text-info"></span> Without extras (OpenCV installation required):</h4>
<h3 class="wy-text-neutral"><tt>pip install dvr-scan</tt></h3>
</div>

DVR-Scan is available via `pip` as [the `dvr-scan` package](https://pypi.org/project/dvr-scan/).  See below for instructions on installing a non-pip version of OpenCV.  To ensure you have all the requirements installed, open a `python` interpreter, and ensure you can run `import cv2` without any errors.

If GUI support is not required (e.g. for server-only usage), you can install the headless version of OpenCV via `pip install dvr-scan[opencv-headless]`.

### Windows Build (64-bit Only) &nbsp; <span class="wy-text-neutral"><span class="fa fa-windows"></span></span>

<div class="important">
<h3 class="wy-text-neutral"><span class="fa fa-forward wy-text-info"></span> Latest Release: <b class="wy-text-neutral">v1.4</b></h3>
<h4 class="wy-text-neutral"><span class="fa fa-calendar wy-text-info"></span>&nbsp; Release Date:&nbsp; <b>February 8, 2022</b></h4>
<a href="https://github.com/Breakthrough/DVR-Scan/releases/download/v1.4/dvr-scan-1.4-win64.exe" class="btn btn-info" style="margin-bottom:8px;" role="button"><span class="fa fa-download"></span>&nbsp; <b>Installer</b>&nbsp;&nbsp;(recommended)</a> &nbsp;&nbsp;&nbsp;&nbsp; <a href="https://github.com/Breakthrough/DVR-Scan/releases/download/v1.4/dvr-scan-1.4-win64-portable.zip" class="btn btn-info" style="margin-bottom:8px;" role="button"><span class="fa fa-download"></span>&nbsp; <b>Portable .zip</b></a> &nbsp;&nbsp;&nbsp;&nbsp; <a href="../guide/examples/" class="btn btn-success" style="margin-bottom:8px;" role="button"><span class="fa fa-book"></span>&nbsp; <b>Getting Started</b></a>
</div>

### Python Installer (All Platforms) &nbsp; <span class="wy-text-neutral"><span class="fa fa-windows"></span> &nbsp; <span class="fa fa-linux"></span> &nbsp; <span class="fa fa-apple"></span></span></h3>

<div class="important">
<h4 class="wy-text-neutral"><span class="fa fa-forward wy-text-info"></span> Latest Release: <b class="wy-text-neutral">v1.4</b></h4>
<h4 class="wy-text-neutral"><span class="fa fa-calendar wy-text-info"></span>&nbsp; Release Date:&nbsp; <b>February 8, 2022</b></h4>
<a href="https://github.com/Breakthrough/DVR-Scan/archive/v1.4.zip" class="btn btn-info" style="margin-bottom:8px;" role="button"><span class="fa fa-download"></span>&nbsp; <b>Source</b>&nbsp;&nbsp;.zip</a> &nbsp;&nbsp;&nbsp;&nbsp; <a href="https://github.com/Breakthrough/DVR-Scan/archive/v1.4.tar.gz" class="btn btn-info" style="margin-bottom:8px;" role="button"><span class="fa fa-download"></span>&nbsp; <b>Source</b>&nbsp;&nbsp;.tar.gz</a> &nbsp;&nbsp;&nbsp;&nbsp; <a href="../examples/usage/" class="btn btn-success" style="margin-bottom:8px;" role="button"><span class="fa fa-book"></span>&nbsp; <b>Getting Started</b></a>
</div>

To install from source, download and extract the latest release to a location of your choice, and make sure you have the appropriate [system requirements](guide/installing.md) installed before continuing.  DVR-Scan can be installed by running the following command in the location of the extracted files (don't forget `sudo` if you're installing system-wide):

```md
python setup.py install
```

See the section [Installing & Updating](guide/installing.md) for instructions on installing DVR-Scan and the required system dependencies.  The source distribution is the recommended download for Linux and Mac users.  Although source installation is possible on Windows, the installer and portable versions are the recommended downloads for Windows users, as all required dependencies come bundled with these distributions.

------------------------------------------------

