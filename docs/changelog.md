
# :fontawesome-solid-bars:Changelog

----------------------------------------------------------

#### Changelog

### 1.8.1 (2025-08-27)

#### Release Notes

Fixes issue with application not loading config files saved with v1.8.

#### Changelog

 * [general] Add `--ignore-user-config` flag to both `dvr-scan` and `dvr-scan-app` commands to allow the application to run even if the user config file is corrupted
 * [general] Add new `scan-only` config option to match the UI checkbox and the `--scan-only` CLI flag
 * [bugfix] Fix crash on startup when trying to load user config saved with v1.8 [#240](https://github.com/Breakthrough/DVR-Scan/issues/240)
    * This was caused by the `scan-only` UI option being emitted but the config file did not support it in v1.8
    * Users who are running into this issue should be able to run DVR-Scan after updating to v1.8.1
    * As a workaround for previous versions, you can manually remove the `scan-only` line in the saved config file


### 1.8 (2025-08-23)

#### Release Notes

DVR-Scan 1.8 includes several UI additions and enhancements, and fixes a long-standing issue with Python packaging dependencies.

#### Changelog

 * [general] The Python distribution now correctly requires `opencv-python` [#204](https://github.com/Breakthrough/DVR-Scan/issues/204)
    * There is a separate `dvr-scan-headless` package available for servers which requires `opencv-python-headless` and only includes CLI functionality
 * [bugfix] Fix bounding box overlay stuck on when using the OpenCV output mode [#218](https://github.com/Breakthrough/DVR-Scan/issues/218)
 * [feature] UI additions and enhancements:
     * add option for enabling output concatenation [#223](https://github.com/Breakthrough/DVR-Scan/issues/223)
     * output folder now opens on completion by default [#226](https://github.com/Breakthrough/DVR-Scan/issues/226)
     * input videos can now be sorted by each column
     * add menu button to open DVR-Scan log folder
 * [feature] Add `max-area`, `max-width`, and `max-height` options to help suppress improbable motion events, such as those caused by rain or fog [#224](https://github.com/Breakthrough/DVR-Scan/issues/224) (thanks @elvis-epx)
 * [bugfix] Log files no longer append to the same file, and now have randomized suffixes to support multiple instances [#227](https://github.com/Breakthrough/DVR-Scan/issues/227)
     * Config option changes: logs are no longer appended to the same file, so `max-log-size` is no longer required, and `max-log-files` has been raised from 4 to 15
 * [bugfix] Use `pathlib.Path` everywhere for path handling to mitigate issues with ffmpeg output mode on Windows [#220](https://github.com/Breakthrough/DVR-Scan/issues/220)
 * [bugfix] Fix inaccurate progress bar when using `-st`/`--start-time` [#191](https://github.com/Breakthrough/DVR-Scan/issues/191)
 * [bugfix] Fix missing log message when processing next video [#213](https://github.com/Breakthrough/DVR-Scan/issues/213)
 * [improvement] Update default ffmpeg stream mapping to more gracefully handle audio/subtitles [#219](https://github.com/Breakthrough/DVR-Scan/issues/219)
 * [dist] Update ffmpeg from 7.1 -> 8.0 in binary distributions


### 1.7.0.1 (2025-03-11)

Re-release of Windows distribution that fixes program hanging when starting scan ([#209](https://github.com/Breakthrough/DVR-Scan/issues/209)). This was caused due to the way the program was built. There are no code changes, so the Python distribution has not been re-released.


### 1.7 (2025-02-28)

#### Release Notes

DVR-Scan 1.7 ships with a completely new UI, and supports faster video decoders (up to 50% better scanning performance):

<img alt="example of region editor" src="https://raw.githubusercontent.com/Breakthrough/DVR-Scan/releases/1.7/docs/assets/app-main-window.jpg" width="480"/>

The UI can be started by running `dvr-scan-app`, and is installed alongside the existing command line interface `dvr-scan`.  Config settings and region files can be shared seamlessly between both. Feedback on the new UI is welcome.

#### Changelog

 - [feature] New GUI now available across all platforms, can be launched via `dvr-scan-app`
    - Has UI elements for all settings, supports editing motion regions
    - Shows scan progress in real-time
 - [feature] Add ability to control video decoder via `input-mode` config option (`opencv`, `pyav`, `moviepy`)
    - Allows switching between `OpenCV` (default), `PyAV`, and `MoviePy` for video decoding
    - Certain backends provide substantial performance benefits, up to 50% in some cases (let us know which one works best!)
 - [bugfix] Fix crash on headless systems that don't have `pillow` installed
 - [general] The region editor no longer prompts for a save path if one was already specified via the `-s`/`--save-regions` option
 - [general] A size-limited logfile is now kept locally, useful for filing bug reports
    - Can be controlled with config file options `save-log` (default: yes), `max-log-size` (default: 20 kB), `max-log-files` (default: 4)
    - Path can be found under help entry for `--logfile` by running `dvr-scan --help` or `dvr-scan-app --help`
 - [general] Minimum supported Python version is now 3.9

----------------------------------------------------------

## DVR-Scan 1.6

### 1.6.2 (2024-12-17)

 - [feature] Vastly improved region editor UI:
    - Reimplemented entire UI with Tcl/Tk to provide much more consistent experience across platforms
    - All options now have dedicated UI controls in addition to keyboard shortcuts
    - System-specific shortcuts like undo/redo now work as expected
    - Various performance and usability improvements including zoom/pan and shape selection
 - [feature] Add new `variance-threshold` [config option](https://www.dvr-scan.com/docs/#config-file) to control how MOG2 controls which pixels are described by the current background model [#163](https://github.com/Breakthrough/DVR-Scan/issues/163)
 - [feature] Add new `--thumbnails` option to extract images from each event, use `--thumbnails highscore` to save frame with highest motion score [#159](https://github.com/Breakthrough/DVR-Scan/issues/159)
 - [feature] Add `--use-pts` option to allow using presentation time instead of frame number for timestamps [#170](https://github.com/Breakthrough/DVR-Scan/pull/170)
 - [bugfix] Fix incorrect framerate detection in Windows builds [#174](https://github.com/Breakthrough/DVR-Scan/issues/174)
 - [general] Updates to Windows distributions:
     - Python 3.9 -> Python 3.12
     - OpenCV 4.10.0.82 -> 4.10.0.84
     - Ffmpeg 6.0 -> 7.1


### 1.6.1 (2024-06-18)

#### Release Notes

DVR-Scan 1.6.1 includes some important fixes and improvements for the region editor. Minimum supported Python version is now 3.8.

#### Changelog

 - [bugfix] Corrupt frames are no longer encoded and are skipped when encoding [#151](https://github.com/Breakthrough/DVR-Scan/issues/151)
 - [bugfix] Fix `region-editor` config file option having no effect [#154](https://github.com/Breakthrough/DVR-Scan/issues/154)
 - [bugfix] The region editor now always prompts on any unsaved changes [#161](https://github.com/Breakthrough/DVR-Scan/issues/161)
 - [general] The region editor no longer prompts for a save path if `-s`/`--save-region` was specified
 - [general] Regions added via command line are now be merged with those loaded from the `load-region` config option
 - [general] Add new `learning-rate` [config option](https://www.dvr-scan.com/docs/#config-file) to control how fast the background model is updated
    - Value between `0.0` and `1.0` controls how much weight is placed on next frame, or `-1` for auto
    - `0.0` implies no update to the model, `1.0` will re-initialize it completely on each frame
    - Default value of `-1` is for automatic, which is unchanged from previous releases


### 1.6 (2023-11-15)

#### Release Notes

DVR-Scan greatly improves masking capabilities with the new region editor ([user guide](https://www.dvr-scan.com/guide/#region-editor)):

<img alt="example of region editor" src="https://raw.githubusercontent.com/Breakthrough/DVR-Scan/releases/1.6/docs/assets/region-editor-multiple.jpg" width="480"/>
<img alt="example of region editor" src="https://raw.githubusercontent.com/Breakthrough/DVR-Scan/releases/1.6/docs/assets/region-editor-mask.jpg" width="480"/>

Multiple regions can now be defined with any shape, size, and complexity. Region data can be saved to a file and loaded again. Regions can also be specified by command line.

There are also several other bugfixes and improvements, such as improved seeking performance.

#### Changelog

 - [feature] [New region editor](https://www.dvr-scan.com/guide/#region-editor) `-r`/`--region-editor` allows creation of multiple regions without shape restrictions, replaces `-roi`/`--region-of-interest`
 - [feature] Multiple regions of interest (rectangular or polygonal) can now be created:
    - Using the new region editor by adding the `-r`/`--region-editor` flag: `dvr-scan -i video.mp4 -r`
    - New `-a`/`--add-region` replaces `-roi`/`--region-of-interest` option: `dvr-scan -i video.mp4 -a 5 5 20 5 20 20 5 20`
    - Regions can now be saved to a file: press S in the region editor or use `-s`/`--save-region`
    - Regions can now be loaded from a file: press O in the region editor or use `-R`/`--load-region`
    - Config files can specify a region file to use by default with the `load-region` option, replaces the `region-of-interest` setting
 - [feature] New `-fm` / `--frame-metrics` option draws motion score on each frame to help tune detection parameters
 - [cli] Short flag `-v` is now used for `--verbosity`, replaced by `-V` for `--version`
 - [cli] `-roi`/`--region-of-interest` is now deprecated, replaced by region editor and add/save/load region flags
    - Specifying this option will display the ROI in the new region format allowing you to update usages more easily
 - [general] Improved seeking performance, using `-st`/`--start-time` is now much faster ([#92](https://github.com/Breakthrough/DVR-Scan/issues/92))
 -detection-parameters)
 - [general] Noise reduction kernel can now be disabled by setting `-k`/`--kernel-size` to `0` ([#123](https://github.com/Breakthrough/DVR-Scan/issues/123))
 - [general] Include stack traces in logfiles when setting `--verbosity debug`
 - [bugfix] Add `max-score` option to config file to fix CNT mode always treating first few frame as motion, default is 255.0 [#119](https://github.com/Breakthrough/DVR-Scan/issues/119)
 - [bugfix] Fix timecode format `HH:MM:SS[.nnn]` being rejected for start/end time ([#141](https://github.com/Breakthrough/DVR-Scan/issues/141))
 - [bugfix] Fix incorrect RGB mapping for config file (values were treated as BGR instead)
 - [other] Config option `timecode` has been renamed to `time-code` to match the command-line option
 - [other] Config options that started with `timecode-` have been renamed to start with `text-`, and are now shared between the `time-code` and `frame-metrics` overlays:
    - `time-code-margin` is now `text-margin`
    - `time-code-font-scale` is now `text-font-scale`
    - `time-code-font-thickness` is now `text-font-thickness`
    - `time-code-font-color` is now `text-font-color`
    - `time-code-bg-color` is now `text-bg-color`

#### Known Issues

 - Some prebuilt archives include documentation which references the `load-region` config option with the incorrect name (`region-file`) [#153](https://github.com/Breakthrough/DVR-Scan/issues/153)

----------------------------------------------------------

## DVR-Scan 1.5

### :fontawesome-solid-tags: 1.5.1 (2022-08-15)

#### Changelog

 * [bugfix] Fix crash when opening multiple input videos ([#95](https://github.com/Breakthrough/DVR-Scan/issues/95))
 * [bugfix] Fix incorrect warning regarding frame decode failures at end of video

### 1.5 (2022-07-30)

#### Release Notes

 * Significant performance improvements on multicore systems
 * Support wildcards/globs as inputs for scanning entire folders (`-i folder/*.mp4`)
 * Allow use of ffmpeg for better output quality (`-m ffmpeg`) or codec-copying mode (`-m copy`)
 * Configuration files are now supported, [see documentation for details](https://www.dvr-scan.com/docs/#config-file)
     * Can specify config file path with `-c`/`--config`, or create a `dvr-scan.cfg` file in your user config folder
 * Windows binaries are now signed, thanks [SignPath.io](https://signpath.io/) (certificate by [SignPath Foundation](https://signpath.org/))
 * Experimental Nvidia CUDA® support has been added (set `-b MOG2_CUDA`)
    * If installing via `pip`, requires manual installation of OpenCV compiled with CUDA support
    * If downloading Windows version, make sure to download the GPU-enabled build (`dvr-scan-1.5-win64-cuda.zip`)
    * CUDA-enabled builds are not code signed, and do not include the `CNT` method
 * Minimum supported Python version is now 3.7
 * Minimum supported OpenCV version is now 3.x

#### Command-Line Changes

 * New options:
    * `-c`/`--config` - set path to config file
    * `-d`/`--output-dir` - set directory to write output files (default is working directory)
    * `-m`/`--output-mode` - set output mode (one of: `opencv`, `ffmpeg`, `copy`)
    * `-mo`/`--mask-output` - path to write motion mask for analysis
    * `--verbosity` and `--logfile` - control output verbosity and path to save output
 * `-i`/`--input` now supports globs/wildcards to scan entire folders, e.g. `-i folder/*.mp4`
 * Change default value for `-l`/`--min-event-length` to 0.1 seconds, previously was 2 frames
 * Long form of `-roi` has been renamed to `--region-of-interest` (previously was `--rectangle-of-interest`)
 * `-c` is now used for `--config`, previously was for `--codec`
 * Add experimental `MOG2_CUDA` option for `-b`/`--bg-subtractor`
 * Rename existing `MOG` option to `MOG2`
 * `--codec` has been removed, the value should now be set using a [config file](https://www.dvr-scan.com/docs/#config-file)

#### Changelog

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
 * [bugfix] Event end times now include the presentation duration of the last frame
 * [bugfix] Small values for `-l`/`--min-event-length` are now handled correctly, previously would cause an error
 * [enhancement] Progress bar now indicates how many events have been detected so far
 * [enhancement] Change default value for `min_event_len` to 0.1 seconds, previously was 2 frames ([#91](https://github.com/Breakthrough/DVR-Scan/issues/91))

#### Known Issues

 * Attempting to open multiple input videos will cause DVR-Scan to crash, fixed in v1.5.1 ([#95](https://github.com/Breakthrough/DVR-Scan/issues/95))
 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))
 * Video output when using frame skip and `-m opencv` (default output mode) will result in frames missing from the exported videos ([#81](https://github.com/Breakthrough/DVR-Scan/issues/81))
     * Use `-m ffmpeg` or `-m copy` as a workaround
 * Multiple input videos are not supported with `-m ffmpeg` or `-m copy` ([#86](https://github.com/Breakthrough/DVR-Scan/issues/86))
     * Use ffmpeg to [concatenate/merge input videos](https://trac.ffmpeg.org/wiki/Concatenate) before processing as a workaround
 * CUDA builds do not include the `CNT` option for `-b`/`--bg-subtractor`

----------------------------------------------------------

## DVR-Scan 1.4

### 1.4.1 (2022-02-20)

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
 * If a motion event happens to be *exactly* the number of frames specified by `-l`/`--min-event-length`, the end timecode will be displayed incorrectly ([#90](https://github.com/Breakthrough/DVR-Scan/issues/90))

----------------------------------------------------------

### 1.4 (2022-02-08)

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
 * If a motion event happens to be *exactly* the number of frames specified by `-l`/`--min-event-length`, the end timecode will be displayed incorrectly ([#90](https://github.com/Breakthrough/DVR-Scan/issues/90))

----------------------------------------------------------

## DVR-Scan 1.3

### 1.3 (2021-06-23)

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

----------------------------------------------------------

## DVR-Scan 1.2

### 1.2 (2021-03-10)

#### Changelog

 * [bugfix] Fix quiet mode (`-q/--quiet`) not working correctly ([#19](https://github.com/Breakthrough/DVR-Scan/issues/19), [#35](https://github.com/Breakthrough/DVR-Scan/issues/35))
 * [bugfix] Fix downscale factor (`-df`/`--downscale-factor`) having no effect ([#46](https://github.com/Breakthrough/DVR-Scan/issues/46))
 * [api] Swap order of `fps` and `timecode` arguments in `FrameTimecode` constructor to match that of PySceneDetect ([#33](https://github.com/Breakthrough/DVR-Scan/issues/33))
 * [api] Refactor ScanContext class for better usage from Python ([#33](https://github.com/Breakthrough/DVR-Scan/issues/33))
 * [api] Use named logger rather than print statements ([#35](https://github.com/Breakthrough/DVR-Scan/issues/35))

#### Known Issues

 * When using the `-o`/`--output` argument, a file is still written to disk even if no motion events are discovered in the input file ([#50](https://github.com/Breakthrough/DVR-Scan/issues/50))
 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))

----------------------------------------------------------

## DVR-Scan 1.1

### 1.1 (2020-07-12)

#### Changelog

 * [feature] Add new `-roi` argument to allow specifying a rectangular detection window, can select graphically or specify x/y/w/h via command line (thanks [@klucsik](https://github.com/klucsik))
 * [bugfix] Fixed broken OpenCV compatibility layer causing issues with OpenCV 3.0+
 * [general] Released project on pip, pinned OpenCV version requirement

#### Known Issues

 * Quiet mode (`-q/--quiet`) does not work correctly
 * Variable framerate videos (VFR) are not fully supported, and will yield incorrect timestamps ([#20](https://github.com/Breakthrough/DVR-Scan/issues/20))

----------------------------------------------------------

## DVR-Scan 1.0

### 1.0.1 (2017-01-12)

 * [bugfix] unhandled exception affecting users running source distributions under Python 2.7 environments


### 1.0 (2017-01-11)

 * [feature] detects motion events with configurable sensitivity and noise removal thresholds
 * [feature] output events to individual video files, or as a single-file compilation
 * [feature] allows input seeking, frame skipping, and output suppression mode
 * [feature] configurable detection windows and pre/post-event inclusion length


----------------------------------------------------------

### In Development


### 1.9

 * [bugfix] Fix `quiet-mode` setting (`-q`/`--quiet` flag) still allowing extraneous output
