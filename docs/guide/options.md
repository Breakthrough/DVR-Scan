
## DVR-Scan Command-Line Reference

This page lists all DVR-Scan command line options grouped by functionality. Note that certain options can only be changed by [using a configuration file](config_file.md).


### General

 * `-h`, `--help`: Show help message and all options and default values. Will also show any options overriden by your [user config file](config_file.md), if set.

 * `-v`, `--version`: Show version information.

 * `-L`, `--license`: Show copyright information.

 * `-q`, `--quiet`: Suppress all console output except for final cutting list.

 * `--verbosity`: Set verbosity of output messages, must be one of: `debug`, `info`, `warning`, `error`.

 * `--logfile`: File to save (append) log output.


### Input/Output

 * `-i video.mp4`, `--input video.mp4`: Path to input video. May specify multiple input videos so long as they have the same resolution and framerate. Wildcards/globs are supported (e.g. `-i folder/*.mp4`).
    * Extracted motion events use the filename of the first video only as a prefix.

 * `-c settings.cfg`, `--config settings.cfg`: Path to [config file](config_file.md). If not set, tries to load one automatically from the user settings folder. Some options can only be set via configuration file. See the [Configuration File](config_file.md) page for details.

 * `-d path`, `--output-dir path`: Write all output files to `path`. If not specified, files are written in the working directory.

 * `-m mode`, `--output-mode mode`: Mode to use for saving motion events. Certain features may not work with all output modes. Current modes include:
    * `opencv` (default): Use OpenCV for saving motion events. Requires outputs to be in .AVI format.
    * `ffmpeg`: Use ffmpeg for saving motion events. Does not work with overlays. Encoder settings can be configured using the `ffmpeg-output-args` setting in a [config file](config_file.md).
    * `copy`: Use ffmpeg for saving motion events, but use stream copying mode (no re-encoding). May not produce exact motion event boundaries due to keyframe placement.

 * `-o video.avi`, `--output video.avi`: Save all motion events to a single file, instead of the default (one file per event).
    * Only supported with the default output mode `--mode opencv`, and thus requires a `.avi` extension.

 * `-mo mask.avi`, `--mask-output mask.avi`: Save a video containing the calculated motion mask on each frame. Useful for tuning motion detection parameters.
    * Must have `.avi` extension.

 * `-so`, `--scan-only`: Do not save/extract events, only perform motion detection and display results.

 * `--codec`: The four-letter identifier of the encoder/video codec to use when `-m`/`--mode` is `opencv`
    * Must be one of: `XVID`, `MP4V`, `MP42`, `H264`.
    * Prefer using `-m ffmpeg` with a config file instead.


### Motion Events

All time values can be given as a timecode (`HH:MM:SS` or `HH:MM:SS.nnn`), in seconds as a number followed by `s` (`123s` or `123.45s`), or as number of frames (e.g. `1234`).

 * `-l time`, `--min-event-length time`: Amount of time/frames that must have a motion score above the threshold setting before triggering a new event.

 * `-tb time`, `--time-before-event time`: Maximum amount of time to include before each event.

 * `-tp time`, `--time-post-event time`: Maximum amount of time to include after each event. The event will end once no motion has been detected for this period of time.


### Detection Parameters

 * `-b type`, `--bg-subtractor type`: The type of background subtractor to use. Must be one of:
    * `MOG` (default): [MOG2 Background Subtractor](https://docs.opencv.org/3.4/d7/d7b/classcv_1_1BackgroundSubtractorMOG2.html).
    * `MOG_CUDA`: [Nvidia CUDA-based version of MOG2](https://docs.opencv.org/3.4/df/d23/classcv_1_1cuda_1_1BackgroundSubtractorMOG2.html).
    * `CNT`: [CNT Background Subtractor](https://docs.opencv.org/3.4/de/dca/classcv_1_1bgsegm_1_1BackgroundSubtractorCNT.html), faster than `MOG` but uses different method, so may need to adjust threshold/kernel size.

 * `-t value`, `--threshold value`: Threshold representing the minimum amount of motion a frame must have to trigger an event. Lower values are more sensitive to motion, requiring less movement. If the threshold is too high, some movement in the scene may not be detected, while too low of a threshold can trigger false detections. May need to be adjusted when modifying other parameters (e.g. `bg-subtractor` or `kernel-size`).

 * `-k size`, `--kernel-size size`: Size in pixels of the noise reduction kernel. Must be an odd integer at least 3 or greater. Can also be -1 to auto-set based on input video resolution (default). If kernel size is too large, some movement in the scene may not be detected.

When modifying these parameters, it can be useful to generate a motion mask (`-m`/`--mask-output`) to verify what DVR-Scan calculates internally when looking for motion events.

Detection can also be limited to a particular region of the input frame by setting a rectangular region using the `-roi`/`--region-of-interest` flag in any of the following forms:

 * `-roi`: Show a pop-up window to select a region of interest using the mouse. The first frame will be displayed.
 * `-roi x0,y0 w,h`: Rectangle specified as top-left corner and size. For example, `-roi 50,75 100,150` specifies a 100x150 rectangle with the top left corner at coordinates (50,75). (0,0) is the top-left corner of the video.
 * `-roi width,height`: Same as `-roi` but shrinks the window to fit within (width x height). Useful for processing videos larger than the monitor resolution.

Lastly, the following options can improve performance, but may also reduce detection accuracy:

 * `-df factor`, `--downscale-factor factor`: Integer factor to downscale (shrink) video before processing, to improve performance. For example, if input video resolution is 1024 x 400, and factor=2, each frame is reduced to 1024/2 x 400/2=512 x 200 before processing.

 * `-fs num_frames`, `--frame-skip num_frames`: Number of frames to skip after processing a given frame. Improves performance, at expense of frame and time accuracy, and may increase probability of missing motion events. If set, `-l`/`--min-event-length`, `-tb`/`--time-before-event`, and `-tp`/`--time-post-event` will all be scaled relative to the source framerate. Values above 1 or 2 are not recommended.
   * When using the default output mode (`opencv`), skipped frames are not included. Set `-m`/`--mode` to `ffmpeg` or `copy` to include all frames from the input video when writing motion events to disk.
   * Although adjusted for frame skipping, bounding box smoothing may be inconsistent when using frame skipping. Set `-bb 0` to disable smoothing.

### Overlays

 * `-bb`, `--bounding-box`: Draw a bounding box around the areas where motion is detected.
    * An optional amount of time for temporal smoothing can also be specified (e.g. `-bb 0.1s`). The default smoothing amount is 0.1 seconds. If set to 0 (`-bb 0`), smoothing is disabled.
    * The color, thickness, and minimum size can be set using a [config file](config_file.md).

 * `-tc`, `--time-code`:  Draw time code of each frame on the top left corner.
   * Can configure various properties (e.g. color, font size, margin) using a [config file](config_file.md).

### Seeking / Duration

All time values can be given as a timecode (`HH:MM:SS` or `HH:MM:SS.nnn`), in seconds as a number followed by `s` (`123s` or `123.45s`), or as number of frames (e.g. `1234`).

 * `-st time`, `--start-time time`: Time to seek to in video before performing detection.
    * Note that seeking is not currently optimized.

 * `-dt time`, `--duration time`: Duration to limit motion detection to.
    * Overrides `-et`/`--end-time` if both are set.

 * `-et time`, `--end-time time`: Timecode to stop motion detection at.
