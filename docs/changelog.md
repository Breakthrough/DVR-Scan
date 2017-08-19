
<h1>DVR-Scan Changelog</h1>

--------------------------------------------------------------------------------

## <span class="wy-text-info">Official DVR-Scan Releases</span>

--------------------------------------------------------------------------------

<h3><span class="wy-text-info">Version 1.0.1 (2017-01-12)</span>   &nbsp; &nbsp;  &nbsp; &nbsp;<span class="fa fa-tags wy-text-success"></span> <span class="fa wy-text-success">Latest &nbsp;<span class="fa fa-hand-o-right wy-text-neutral"></span> &nbsp; <a href="../download/">Download &nbsp;<span class="fa fa-download wy-text-info"></span></a></span></h3>

 * [bugfix] unhandled exception affecting users running source distributions under Python 2.7 environments

<h3>Version 1.0 (2017-01-11)</h3>

 * [feature] detects motion events with configurable sensitivity and noise removal thresholds
 * [feature] output events to individual video files, or as a single-file compilation
 * [feature] allows input seeking, frame skipping, and output suppression mode
 * [feature] configurable detection windows and pre/post-event inclusion length

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------

## <span class="wy-text-info">Development Versions / Future Releases</span>

This section details the features currently being developed, implemented, and tested for the next release of DVR-Scan.  **Note that the development version of DVR-Scan provides the latest cutting-edge fetures under development, however note that this is still a pre-release development version, primarily intended to work out any implementation bugs being tackled for the updates.**

Any completed features listed below can be tried by installing the latest developmet version, the instructions of which are detailed below. A more comprehensive list of features being implemented and planned for the upcoming and subsequent releases can be found at [the DVR-Scan Wiki](https://github.com/Breakthrough/DVR-Scan/wiki).

--------------------------------------------------------------------------------

<h3><span class="wy-text-neutral">Current development version:</span> <b>v1.1-dev</b></h3>
<br\><span class="fa wy-text-small wy-text-info">See the section <i>Obtaining & Installing</i> below for details on using the latest development version.</span>

#### <span class="wy-text-neutral">Latest Changes / Bugfixes</span>

 * major release including several new features, bugfixes, and enhancements; includes updated documentation, and updated (optional) dependencies
 * [enhance] added progress bar and show estimated time remaining during processing (requires [the `tqdm` module](https://pypi.python.org/pypi/tqdm) to be installed)
 * [bugfix]  fixed case where motion events would not be detected when specifying the `-st` / `--start-time` option 

#### <span class="wy-text-neutral">Planned Features & Goals for Development</span>

 * [feature] add downscaling option for faster motion detection and encoding/output
 * [enhance] integration with `mkvmerge` to allow for automated extraction of motion events as discrete video files
 * [feature] image masking with a transparent .PNG image where the alpha channel indicates which parts of the frame should be excluded from motion detection
 * [feature] automatic generation of frame mask to determine static areas of long video clips
 * [enhance] include compatibility for live/real-time video sources (e.g. USB webcams, security cameras)

--------------------------------------------------------------------------------

<h4>Obtaining & Installing</h4>

** Warning, installing development versions of DVR-Scan is not recommended unless you are an advanced user, and are comfortable migrating back to a clean package should the current development version have a bug.  In addition to stable releases, bug/error eports in regards to testing development versions are also welcome to submit any issues one might come across.**

To install the latest development version of DVR-Scan, you can download a .zip archive of the current development repo by [clicking here to download `DVR-Scan-master.zip`](https://github.com/Breakthrough/DVR-Scan/archive/master.zip).  The installation instructions remain the same as those outlined in the documentation (simply run `sudo setup.py install` in the location of the extracted files).  To downgrade to a stable version, you must first uninstall the existing (newer) development version, or force a re-installation of the stable release over the development version.

