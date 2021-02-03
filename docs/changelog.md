
<h1>DVR-Scan Changelog</h1>

--------------------------------------------------------------------------------

## <span class="wy-text-info">Official DVR-Scan Releases</span>

--------------------------------------------------------------------------------

<h3>Version 1.2 (TBD)</h3>

 * [bugfix] Fixed quiet mode (`-q/--quiet`) not working correctly ([#19](https://github.com/Breakthrough/DVR-Scan/issues/19), [#35](https://github.com/Breakthrough/DVR-Scan/issues/35))
 * [general] Refactor ScanContext class for better usage from Python ([#33](https://github.com/Breakthrough/DVR-Scan/issues/19))

<h3>Version 1.1 (2020-07-12)  &nbsp; &nbsp;  &nbsp; &nbsp;<span class="fa fa-tags wy-text-success"></span> <span class="fa wy-text-success">Latest &nbsp;<span class="fa fa-hand-o-right wy-text-neutral"></span> &nbsp; <a href="../download/">Download &nbsp;<span class="fa fa-download wy-text-info"></span></a></span></h3>

 * [feature] Add new `-roi` argument to allow specifying a rectangular detection window, can select graphically or specify x/y/w/h via command line (thanks [@klucsik](https://github.com/klucsik))
 * [bugfix] Fixed broken OpenCV compatibility layer causing issues with OpenCV 3.0+
 * [general] Released project on pip, pinned OpenCV version requirement

<h3>Version 1.0.1 (2017-01-12)</h3>

 * [bugfix] unhandled exception affecting users running source distributions under Python 2.7 environments

<h3>Version 1.0 (2017-01-11)</h3>

 * [feature] detects motion events with configurable sensitivity and noise removal thresholds
 * [feature] output events to individual video files, or as a single-file compilation
 * [feature] allows input seeking, frame skipping, and output suppression mode
 * [feature] configurable detection windows and pre/post-event inclusion length

