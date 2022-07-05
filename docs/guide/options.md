
## DVR-Scan Command-Line Reference

This page lists all DVR-Scan command line options grouped by functionality. Command line options always take precedence over values set with a [config file](config_file.md).


### General

 * <b><pre>-h, --help</pre></b>
    Show help message and all options and default values. Will also show any options overriden by your [user config file](config_file.md), if set.

 * <b><pre>-v, --version</pre></b>
    Show version information.

 * <b><pre>-L, --license</pre></b>
    Show copyright information.

The following options control terminal output:

 * <b><pre>--logfile log.txt</pre></b>
    File to save (append) log output.

 * <b><pre>-q, --quiet</pre></b>
    Suppress all console output except for final cutting list.

 * <b><pre>--verbosity</pre></b>
    Set verbosity of output messages, must be one of: (<b><pre>debug, info, warning, error</pre></b>
    *Default*: `--verbosity info`


### Input/Output

 * <b><pre>-i video.mp4, --input video.mp4</b></pre>
    Path to input video. May specify multiple input videos so long as they have the same resolution and framerate. Wildcards/globs are supported (e.g. `-i folder/*.mp4`). Extracted motion events use the filename of the first video only as a prefix.

 * <b><pre>-c settings.cfg, --config settings.cfg</b></pre>
    Path to config file. If not set, tries to load one automatically from the user settings folder. See the [config file documentation](config_file.md) for details.

 * <b><pre>-d path, --output-dir path</b></pre> Write all output files to `path`. If not specified, files are written in the working directory.

 * <b><pre>-m mode, --output-mode mode</b></pre> Mode to use for saving motion events. Must be one of:

    * <b><pre>opencv</b></pre>
        (*Default*) Use OpenCV for saving motion events. Requires output to be in .AVI format.

    * <b><pre>ffmpeg</b></pre>
        Use ffmpeg for saving motion events. Ffmpeg encoder args can be set using a [config file](config_file.md#inputoutput) (option: *ffmpeg-output-args*). Does not work with overlays.

    * <b><pre>copy</b></pre>
        Same as `ffmpeg`, but using stream copying mode (no reencoding). Can potentially create inaccurate events due to keyframe placement.

 * <b><pre>-o video.avi, --output video.avi</b></pre> Save all motion events to a single file, instead of the default (one file per event). Only supported with the default output mode (`opencv`). Requires `.avi` extension.

 * <b><pre>-mo mask.avi, --mask-output mask.avi</b></pre> Save a video containing the calculated motion mask on each frame. Useful for tuning motion detection parameters. Requires `.avi` extension.

 * <b><pre>-so, --scan-only</b></pre> Do not save/extract events, only perform motion detection and display results.


### Seeking / Duration

All time values can be given as a timecode (`HH:MM:SS` or `HH:MM:SS.nnn`), in seconds as a number followed by `s` (`123s` or `123.45s`), or as number of frames (e.g. `1234`).

 * <b><pre>-st time, --start-time time</pre></b>Timecode in video to start motion detection from

 * <b><pre>-dt time, --duration time</b></pre> Maximum duration of input to process.

 * <b><pre>-et time, --end-time time</b></pre> Timecode to stop processing input.

For example, to scan the input between 1m30s and 2m:

    dvr-scan -i video.mp4 -st 00:01:30 -et 00:02:00


### Motion Events

All time values can be given as a timecode (`HH:MM:SS` or `HH:MM:SS.nnn`), in seconds as a number followed by `s` (`123s` or `123.45s`), or as number of frames (e.g. `1234`).

 * <b><pre>-l time, --min-event-length time</b></pre> Amount of time/frames that must have a motion score above the threshold setting before triggering a new event.
<br/>*Default*: `--min-event-length 2`

 * <b><pre>-tb time, --time-before-event time</b></pre> Maximum amount of time to include before each event.
<br/>*Default*: `--time-before-event 1.5s`

 * <b><pre>-tp time, --time-post-event time</b></pre> Maximum amount of time to include after each event. The event will end once no motion has been detected for this period of time.
<br/>*Default*: `--time-post-event time 2.0s`

For example, to save 10 seconds before or after any frame that exceeds the threshold:

    dvr-scan -i video.mp4 -l 1 -tb 10s -tp 10s


### Detection Parameters

When modifying these parameters, it can be useful to generate a motion mask (`-mo mask.avi`) to visually see how DVR-Scan processes the input when looking for motion events.

 * <b><pre>-b type, --bg-subtractor type</b></pre> The type of background subtractor to use. Must be one of:

    * `MOG` (*default*): [MOG2 Background Subtractor](https://docs.opencv.org/3.4/d7/d7b/classcv_1_1BackgroundSubtractorMOG2.html).

    * `MOG_CUDA</b></pre> [Nvidia CUDA-based version of MOG2](https://docs.opencv.org/3.4/df/d23/classcv_1_1cuda_1_1BackgroundSubtractorMOG2.html).

    * `CNT</b></pre> [CNT Background Subtractor](https://docs.opencv.org/3.4/de/dca/classcv_1_1bgsegm_1_1BackgroundSubtractorCNT.html), faster than `MOG` but uses different method, so may need to adjust threshold/kernel size.

 * <b><pre>-t value, --threshold value</b></pre> Threshold representing the minimum amount of motion a frame must have to trigger an event. Lower values are more sensitive to motion, requiring less movement. If the threshold is too high, some movement in the scene may not be detected, while too low of a threshold can trigger false detections. May need to be adjusted when modifying other parameters (e.g. `bg-subtractor` or `kernel-size`).
<br/>*Default*: `--threshold 0.15`

 * <b><pre>-k size, --kernel-size size</b></pre> Size in pixels of the noise reduction kernel. Must be an odd integer at least 3 or greater. Can also be -1 to auto-set based on input video resolution (default). If kernel size is too large, some movement in the scene may not be detected. Default values: 7 for 1080p or greater, 5 for 720p, 3 for 480p.
<br/>*Default*: `--kernel-size -1`

Detection can be limited to a smaller region of the frame using the `-roi`/`--region-of-interest` flag:

 * <b><pre>-roi, --region-of-interest</b></pre> Show a pop-up window to select a region of interest using the mouse. The first frame will be displayed.

 * <b><pre>-roi x0, y0 w, h</b></pre> Rectangle specified as top-left corner and size. For example, `-roi 50,75, 100,150` specifies a 100x150 rectangle with the top left corner at coordinates (50,75). (0,0) is the top-left corner of the video.

 * <b><pre>-roi width,height</b></pre> Same as `-roi` but shrinks the window to fit within (width x height). Useful for processing videos larger than the monitor resolution.

The following options can improve performance, but may reduce detection accuracy:

 * <b><pre>-df factor, --downscale-factor factor</b></pre> Integer factor to downscale (shrink) video before processing, to improve performance. For example, if input video resolution is 1024 x 400, and factor=2, each frame is reduced to 1024/2 x 400/2=512 x 200 before processing.

 * <b><pre>-fs num_frames, --frame-skip num_frames</b></pre> Number of frames to skip after processing a given frame. Improves performance, at expense of frame and time accuracy, and may increase probability of missing motion events. If set, `-l`/`--min-event-length, -tb`/`--time-before-event`, and `-tp`/`--time-post-event` will all be scaled relative to the source framerate. Values above 1 or 2 are not recommended.
<br/><br/>When using the default output mode (`opencv`), skipped frames are not included. Set `-m`/`--output-mode` to `ffmpeg` or `copy` to include all frames from the input video when writing motion events to disk.
<br/><br/>Although adjusted for frame skipping, bounding box smoothing may be inconsistent when using frame skipping. Set `-bb 0` to disable smoothing.

### Overlays

 * <b><pre>-bb, --bounding-box</b></pre> Draw a bounding box around the areas where motion is detected.
<br/><br/>An optional amount of time for temporal smoothing can also be specified (e.g. `-bb 0.1s`). The default smoothing amount is 0.1 seconds. If set to 0 (`-bb 0`), smoothing is disabled.
<br/><br/>The color, thickness, and minimum size can be set with a [config file](config_file.md#bounding-box-overlay).

 * <b><pre>-tc, --time-code</b></pre>  Draw time code of each frame on the top left corner.
<br/><br/>Text properties (e.g. color, font size, margin) can be set with a [config file](config_file.md#timecode-overlay).

For example, to draw a bounding box and timecode on extracted motion events:

    dvr-scan -i video.mp4 -bb -tc

Overlays are only supported with the default output mode (`opencv`).
