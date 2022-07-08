
DVR-Scan Changelog
==========================================================

## DVR-Scan 1.5

### 1.5-beta (July 4, 2022) &nbsp;<span class="fa fa-tags"></span>

#### Release Notes

 * Significant performance improvements on multicore systems
 * Support wildcards/globs as inputs for scanning entire folders (`-i folder/*.mp4`)
 * Allow use of ffmpeg for better output quality (`-m ffmpeg`) or codec-copying mode (`-m copy`)
 * Configuration files are now supported, [see documentation for details](https://dvr-scan.readthedocs.io/en/v1.5/guide/config_file/)
     * Can specify config file path with `-c`/`--config`, or create a `dvr-scan.cfg` file in your user config folder
 * Windows binaries are now signed, thanks [SignPath.io](https://signpath.io/) (certificate by [SignPath Foundation](https://signpath.org/))
 * Experimental CUDA® support has been added (set `-b MOG2_CUDA`)
    * If installing via Pip, requires manual installation of OpenCV compiled with CUDA support
    * If downloading Windows version, make sure to download the GPU-enabled build (`dvr-scan-1.5.dev1-win64-cuda.zip`)
    * CUDA-enabled builds are not signed currently
 * Minimum supported Python version is now 3.7
 * Minimum supported OpenCV version is now 3.x

#### Changelog

**Command-Line Interface:**

 * New features/arguments (see below for more details):
    * `-c`/`--config` - set path to config file
    * `-d`/`--output-dir` - set directory to write output files (default is working directory)
    * `-m`/`--output-mode` - set output mode (one of: `opencv`, `ffmpeg`, `copy`)
    * `-mo`/`--mask-output` - path to write motion mask for analysis
    * `--verbosity` and `--logfile` - control output verbosity and path to save output
 * `-i`/`--input` now supports globs/wildcards to scan entire folders, e.g. `-i folder/*.mp4`
 * Long form of `-roi` has been renamed to `--region-of-interest` (previously was `--rectangle-of-interest`)
 * `-c` is now used for `--config`, previously was for `--codec`
 * Add experimental `MOG2_CUDA` option for `-b`/`--bg-subtractor`
 * Rename existing `MOG` option to `MOG2`
 * `--codec` has been removed, the value should now be set using a [config file](guide/config_file.md)

**General:**

 * [feature] Configuration file support and new `-c`/`--config` argument to specify path to config files ([#77](https://github.com/Breakthrough/DVR-Scan/issues/77))
     * Breaks existing behavior of `-c` (was previously the shortform of `--codec`)
 * [feature] Add support for multiple output modes via `-m`/`--output-mode` argument ([#27](https://github.com/Breakthrough/DVR-Scan/issues/27), [#42](https://github.com/Breakthrough/DVR-Scan/issues/42))
 * [feature] Experimental support for GPU-based CUDA MOG2 filter ([#12](https://github.com/Breakthrough/DVR-Scan/issues/12))
 * [feature] Video encoding and decoding are now done in parallel with the scanning logic leading to improved performance on most systems ([#52](https://github.com/Breakthrough/DVR-Scan/issues/52))
 * [feature] Add support for exporting motion masks via `-mo`/`--mask-output` argument
     * Useful for detailed analysis or tuning of detection parameters
     * ffmpeg can be used to generate output videos by specifying `-m ffmpeg`
     * Codec-copy mode, using ffmpeg, can be used by specifying `-m copy`
 * [feature] Add `--verbosity` and `--logfile` arguments to provide more control over program output
 * [feature] Allow scanning entire folders using wildcards with `-i`/`--input` ([#5](https://github.com/Breakthrough/DVR-Scan/issues/5))
     * Glob expansion is also performed on each input path directly, so quoted globs also function correctly
 * [bugfix] Fix incorrect results when `-st`/`--start-time` is set
 * [bugfix] Event start times are now correctly calculated when using `-fs`/`--frame-skip` ([#68](https://github.com/Breakthrough/DVR-Scan/issues/68), [#70](https://github.com/Breakthrough/DVR-Scan/issues/70))
    * Note that all skipped frames within the event window are included in motion event, thus the calculated start time may be slightly earlier
 * [bugfix] Only get screen resolution when required (was causing issues on headless machines)
 * [bugfix] Fix output messages conflicting with progress bar shown during scanning
 * [bugfix] Output events now start from 1 to align with the event list

#### Known Issues

 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))
 * Video output when using frame skip and `-m opencv` (default output mode) will result in frames missing from the exported videos ([#81](https://github.com/Breakthrough/DVR-Scan/issues/81), can use `-m ffmpeg` or `-m copy` as a workaround)
 * Multiple input videos are not supported yet when using `-m ffmpeg` or `-m copy` ([#86](https://github.com/Breakthrough/DVR-Scan/issues/86))


## DVR-Scan 1.4

### 1.4.1 (February 20, 2022)

#### Release Notes

This release includes fixes for incorrect event start/end times when using frame skipping, and improvements to the bounding box overlays.

**Important:** Aside from critical bugfixes, DVR-Scan 1.4.x is the last minor version supporting Python 2.7.  Starting from v1.5, the new minimum supported Python version will be 3.6 (see [#83](https://github.com/Breakthrough/DVR-Scan/issues/83) for details).

#### Changelog

 * [bugfix] Event start times are now correctly calculated when using `-fs`/`--frame-skip` ([#68](https://github.com/Breakthrough/DVR-Scan/issues/68), [#70](https://github.com/Breakthrough/DVR-Scan/issues/70))
    * Note that event start/end times may still be off by how many frames are skipped due to loss of context with respect to frame-accurate motion detection
 * [bugfix] Event end times now take into account the number of skipped frames if `-fs`/`--frame-skip` if specified (e.g. it is assumed all skipped frames contained motion)
 * [bugfix] Bounding box smoothing now takes into account `-fs`/`--frame-skip` ([#31](https://github.com/Breakthrough/DVR-Scan/issues/31))
 * [bugfix] Bounding boxes now cover all frames with motion ([#31](https://github.com/Breakthrough/DVR-Scan/issues/31))
    * In v1.4 only the frames after `-l`/`--min-event-length` frames had passed were covered

#### Known Issues

 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))
 * Using `-st`/`--start-time` will yield incorrect results


### 1.4 (February 8, 2022)

#### Release Notes

In addition to several bugfixes, this release of DVR-Scan adds the ability to draw a bounding box around the area in the frame where motion was detected. There are also several improves when using `-fs`/`--frame-skip` and/or `-df`/`--downscale-factor` by ensuring all other option are relative to the original video framerate/resolution.

**Important:** Aside from critical bugfixes, DVR-Scan 1.4.x is the last minor version supporting Python 2.7.  Starting from v1.5, the new minimum supported Python version will be 3.6 (see [#83](https://github.com/Breakthrough/DVR-Scan/issues/83) for details).

#### Changelog

 * [feature] Add new `--bb`/`--bounding-box` option to draw rectangle around the area in the video where motion was detected
     * An amount to temporally smooth the box in time can also be specified after `-bb` (e.g. `-bb 0.5s`), where the default is 0.1s
 * [bugfix] Processing errors should now return a non-zero exit code
 * [bugfix] Allow a maximum window size to be set when using `-roi` ([#59](https://github.com/Breakthrough/DVR-Scan/issues/59)):
     * The `-roi` flag now accepts a maximum window size for the ROI selection window (e.g. `-roi 1920 1080`)
     * If the `screeninfo` package is installed, or you are using a Windows build, videos will automatically be resized to the maximum screen size
 * [bugfix] Fix frozen timestamp at beginning of video ([#68](https://github.com/Breakthrough/DVR-Scan/issues/68))
 * [bugfix] Fix output videos not including all of the duration specified by `-tb`/`--time-before` in certain cases ([#68](https://github.com/Breakthrough/DVR-Scan/issues/68)
 * [bugfix] Fix event start times not reflecting `-l`/`--min-event-length` and `-tb`/`--time-before` ([#68](https://github.com/Breakthrough/DVR-Scan/issues/68)
 * [bugfix] Scanning no longer stops suddenly after a frame fails to decode ([#62](https://github.com/Breakthrough/DVR-Scan/issues/62))
     * If more than 1 corrupt frame is found, a warning will be displayed with the number of frame decode failures
     * If more than 5 frames in a row fail to be decoded, processing will stop and display an error
 * [bugfix] When no events have been found, an empty file is no longer created if `-o/--output` is specified
 * [enhancement] `-k`/`--kernel-size` is now relative to the original video resolution, and will be reduced to adjust for `-df`/`--downscale-factor` if set ([#46](https://github.com/Breakthrough/DVR-Scan/issues/46))
 * [bugfix] Output videos now have the correct playback speed when using `-fs`/`--frame-skip` by reducing the framerate ([#70](https://github.com/Breakthrough/DVR-Scan/issues/70))
 * [bugfix] The `-l`/`--min-event-length` and `-tp`/`--time-post-event` parameters are now adjusted to compensate for `-fs`/`--frame-skip` if set ([#70](https://github.com/Breakthrough/DVR-Scan/issues/70))
 * [bugfix] An erroneus event (false positive) is no longer generated at the beginning of a video when `-l`/`--min-event-length` is equal to 1 frame

#### Known Issues

 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))
 * When using `-fs`/`--frame-skip`, event start times do not include all of `-tb`/`--time-before-event` ([#68](https://github.com/Breakthrough/DVR-Scan/issues/68), [#70](https://github.com/Breakthrough/DVR-Scan/issues/70))
 * When using `-bb`/`--bounding-box`, the amount of time covered by `-l`/`--min-event-length` will be missing bounding box overlays ([#31](https://github.com/Breakthrough/DVR-Scan/issues/31))
 * Using `-st`/`--start-time` will yield incorrect results


## DVR-Scan 1.3

### 1.3 (May 23, 2021)

#### Release Notes

This version of DVR-Scan includes a new, faster background subtraction algorithm (`-b CNT`).  Results may be slightly different when using this method, so any feedback is most welcome.

#### Changelog

 * [feature] Add new `-b`/`--bg-subtractor` argument to allow selecting between the MOG and CNT background subtractor types (e.g. `dvr-scan -b CNT`). Resolves [#48](https://github.com/Breakthrough/DVR-Scan/issues/48). The following background subtractor types are available:
     * `MOG` is the default
     * `CNT` is a newer, faster algorithm (feedback is welcome)
 * [bugfix] When using the `-o`/`--output` argument, a file is no longer written to disk if no motion events are found in the input file ([#50](https://github.com/Breakthrough/DVR-Scan/issues/50))

#### Known Issues

 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))
 * Using the `-roi` flag with high resolution videos can result in the window exceeding the size of the monitor ([#59](https://github.com/Breakthrough/DVR-Scan/issues/59))
 * When using `-tc`/`--time-code` the start of the video may have a frozen timestamp ([#68](https://github.com/Breakthrough/DVR-Scan/issues/68))
 * The kernel size must be manually adjusted when using `-df`/`--downscale-factor` ([#46](https://github.com/Breakthrough/DVR-Scan/issues/46))
 * When using `--frame-skip`, the `--min-event-length` parameter must be manually adjusted, and exported clips will have the wrong playback speed


## DVR-Scan 1.2

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


## DVR-Scan 1.1

### 1.1 (July 12, 2020)

#### Changelog

 * [feature] Add new `-roi` argument to allow specifying a rectangular detection window, can select graphically or specify x/y/w/h via command line (thanks [@klucsik](https://github.com/klucsik))
 * [bugfix] Fixed broken OpenCV compatibility layer causing issues with OpenCV 3.0+
 * [general] Released project on pip, pinned OpenCV version requirement

#### Known Issues

 * Quiet mode (`-q/--quiet`) does not work correctly
 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))


## DVR-Scan 1.0

### 1.0.1 (January 12, 2017)

 * [bugfix] unhandled exception affecting users running source distributions under Python 2.7 environments


### 1.0 (January 11, 2017)

 * [feature] detects motion events with configurable sensitivity and noise removal thresholds
 * [feature] output events to individual video files, or as a single-file compilation
 * [feature] allows input seeking, frame skipping, and output suppression mode
 * [feature] configurable detection windows and pre/post-event inclusion length

