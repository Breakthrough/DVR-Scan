
DVR-Scan Changelog
==========================================================

## DVR-Scan 1.0

### 1.3 (May 23, 2021) &nbsp;<span class="fa fa-tags"></span>

#### Release Notes

This version of DVR-Scan includes a new, faster background subtraction algorithm (`-b CNT`).  Results may be slightly different when using this method, so any feedback is most welcome.

#### Changelog

 * [feature] Add new `-b`/`--bg-subtractor` argument to allow selecting between the MOG and CNT background subtractor types (e.g. `dvr-scan -b CNT`). Resolves [#48](https://github.com/Breakthrough/DVR-Scan/issues/48). The following background subtractor types are available:
     * `MOG` is the default
     * `CNT` is a newer, faster algorithm (feedback is welcome)
 * [bugfix] When using the `-o`/`--output` argument, a file is no longer written to disk if no motion events are found in the input file ([#50](https://github.com/Breakthrough/DVR-Scan/issues/50))

#### Known Issues

 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))


### 1.2 (March 10, 2021)

#### Changelog

 * [bugfix] Fix quiet mode (`-q/--quiet`) not working correctly ([#19](https://github.com/Breakthrough/DVR-Scan/issues/19), [#35](https://github.com/Breakthrough/DVR-Scan/issues/35))
 * [bugfix] Fix downscale factor (`-df`/`--downscale-factor`) having no effect ([#46](https://github.com/Breakthrough/DVR-Scan/issues/46))
 * [api] Swap order of `fps` and `timecode` arguments in `FrameTimecode` constructor to match that of PySceneDetect ([#33](https://github.com/Breakthrough/DVR-Scan/issues/33))
 * [api] Refactor ScanContext class for better usage from Python ([#33](https://github.com/Breakthrough/DVR-Scan/issues/33))
 * [api] Use named logger rather than print statements ([#35](https://github.com/Breakthrough/DVR-Scan/issues/35))

#### Known Issues

 * When using the `-o`/`--output` argument, a file is still written to disk even if no motion events are discovered in the input file ([#50](https://github.com/Breakthrough/DVR-Scan/issues/50))
 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))


### 1.1 (July 12, 2020)

#### Changelog

 * [feature] Add new `-roi` argument to allow specifying a rectangular detection window, can select graphically or specify x/y/w/h via command line (thanks [@klucsik](https://github.com/klucsik))
 * [bugfix] Fixed broken OpenCV compatibility layer causing issues with OpenCV 3.0+
 * [general] Released project on pip, pinned OpenCV version requirement

#### Known Issues

 * Quiet mode (`-q/--quiet`) does not work correctly
 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))

### 1.0.1 (January 12, 2017)

 * [bugfix] unhandled exception affecting users running source distributions under Python 2.7 environments

### 1.0 (January 11, 2017)

 * [feature] detects motion events with configurable sensitivity and noise removal thresholds
 * [feature] output events to individual video files, or as a single-file compilation
 * [feature] allows input seeking, frame skipping, and output suppression mode
 * [feature] configurable detection windows and pre/post-event inclusion length

