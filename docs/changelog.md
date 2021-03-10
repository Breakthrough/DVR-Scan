
DVR-Scan Changelog
==========================================================

## DVR-Scan 1.0

### 1.2

#### Release Notes

This is the final release of DVR-Scan 1.x.  All new development will proceed with DVR-Scan 2.x.  Any known issues will be updated here when discovered.

#### Changelog

 * [bugfix] Fix quiet mode (`-q/--quiet`) not working correctly ([#19](https://github.com/Breakthrough/DVR-Scan/issues/19), [#35](https://github.com/Breakthrough/DVR-Scan/issues/35))
 * [bugfix] Fix downscale factor (`-df`/`--downscale-factor`) having no effect ([#46](https://github.com/Breakthrough/DVR-Scan/issues/46))
 * [api] Swap order of `fps` and `timecode` arguments in `FrameTimecode` constructor to match that of PySceneDetect ([#33](https://github.com/Breakthrough/DVR-Scan/issues/33))
 * [api] Refactor ScanContext class for better usage from Python ([#33](https://github.com/Breakthrough/DVR-Scan/issues/33))
 * [api] Use named logger rather than print statements ([#35](https://github.com/Breakthrough/DVR-Scan/issues/35))

### 1.1 (2020-07-12) &nbsp;<span class="fa fa-tags"></span>

#### Changelog

 * [feature] Add new `-roi` argument to allow specifying a rectangular detection window, can select graphically or specify x/y/w/h via command line (thanks [@klucsik](https://github.com/klucsik))
 * [bugfix] Fixed broken OpenCV compatibility layer causing issues with OpenCV 3.0+
 * [general] Released project on pip, pinned OpenCV version requirement

#### Known Issues

 * Quiet mode (`-q/--quiet`) does not work correctly

### 1.0.1 (2017-01-12)

 * [bugfix] unhandled exception affecting users running source distributions under Python 2.7 environments

### 1.0

 * [feature] detects motion events with configurable sensitivity and noise removal thresholds
 * [feature] output events to individual video files, or as a single-file compilation
 * [feature] allows input seeking, frame skipping, and output suppression mode
 * [feature] configurable detection windows and pre/post-event inclusion length

