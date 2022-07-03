
## DVR-Scan Configuration File

This page lists all DVR-Scan config options. You can also download [the `dvr-scan.cfg` config template](https://github.com/Breakthrough/DVR-Scan/blob/v1.5/dvr-scan.cfg) which contains every possible configuration option (this file is also included with Python and Windows distributions).

A config file path can be specified via the -c/--config option. DVR-Scan also looks for a `dvr-scan.cfg` file in the following locations:

 * Windows: `C:/Users/%USERNAME%/AppData/Local/DVR-Scan/dvr-scan.cfg`
 * Linux: `~/.config/DVR-Scan/dvr-scan.cfg` or `$XDG_CONFIG_HOME/dvr-scan.cfg`
 * OSX: `~/Library/Preferences/DVR-Scan/dvr-scan.cfg`

Run `dvr-scan --help` to see the exact path on your system which will be used (it will be listed under the help text for the -c/--config option).

Configuration options are set as `option = value`, and lines starting with `#` are ignored as comments. For example:

```
# This is an example of a DVR-Scan config file.
# Lines starting with # are treated as comments.
output-mode = COPY
min-event-length = 0.25s
bounding-box = yes
bounding-box-color = 0, 255, 0
```

You can download [a `dvr-scan.cfg` config template](https://github.com/Breakthrough/DVR-Scan/blob/v1.5/dvr-scan.cfg) to use as a complete reference.


### General

 * `quiet-mode`: Suppress all console output: (`yes` or `no`). Only a final comma-separated list of timecodes will be printed if set to `yes`.
<br/>*Default*: `quiet-mode = no`
<br/><br/>

 * `verbosity`: Verbosity of console output: (`debug`, `info`, `warning`, `error`).
<br/>*Default*: `verbosity = info`


### Input/Output

 * `output-dir`: Directory to output all created files. If unset, files will be created in the current working directory.
<br/>*Example*: `output-dir = C:/temp/scanned/`
<br/><br/>

 * `output-mode`: Method of generating output videos: (`scan_only`, `opencv`, `ffmpeg`, `copy`). Not all features are supported in all modes.
<br/>*Default*: `output-mode = opencv`
<br/><br/>

 * `ffmpeg-output-args`: Encoder parameters used when generating output files when *output-mode* is *ffmpeg*.
<br/>*Default*: `ffmpeg-output-args = -map 0 -c:v libx264 -preset fast -crf 21 -c:a aac`
<br/><br/>

 * `opencv-fourcc`: Four-letter identifier of the encoder/video codec to use when *output-mode* is *opencv*. Must be one of: (`XVID`, `MP4V`, `MP42`, `H264`).
<br/>*Default*: `opencv-fourcc = XVID`


### Motion Events

All time values can be given as a timecode: (`HH:MM:SS` or `HH:MM:SS.nnn`), in seconds as a number followed by `s`: (`123s` or `123.45s`), or as number of frames: (`1234`).

 * `min-event-length`: Amount of time which must have motion in each frame to trigger an event.
<br/>*Default*: `min-event-length = 2`
<br/><br/>

 * `time-before-event`: Amount of time to include before a motion event.
<br/>*Default*: `time-before-event = 1.5s`
<br/><br/>

 * `time-post-event`: Amount of time to include after an event.
<br/>*Default*: `time-post-event = 2.0s`
<br/><br/>


### Detection Parameters

See the [detection parameters section on the previous page](options.md#detection-parameters) for a more comprehensive description of each option.

 * `bg-subtractor`: Type of background subtraction to use: (`MOG`, `CNT`, `MOG_CUDA`).
<br/>*Default*: `bg-subtractor = MOG`
<br/><br/>

 * `threshold`: Threshold representing amount of motion in a frame (or the ROI, if set) for a motion event to be triggered.
<br/>*Default*: `threshold = 0.15`
<br/><br/>

 * `kernel-size`: Size (in pixels) of the noise reduction kernel. Must be an odd integer greater than 1, or -1 to auto-set based on video resolution.
<br/>*Default*: `kernel-size = -1`
<br/><br/>

 * `region-of-interest`: Region of interest of the form (x, y) / (w, h), where x, y is the top left corner, and w, h is the width/height in pixels. Brackets, commas, and slahes are ignored.
<br/>*Example*: `region-of-interest = (100, 110) / (50, 50)`
<br/><br/>

 * `downscale-factor`: Integer factor to shrink video before processing. Values <= 1 imply no downscaling.
<br/>*Default*: `downscale-factor = 0`
<br/><br/>

 * `frame-skip`: Number of frames to skip between processing when looking for motion events.
<br/>*Default*: `frame-skip = 0`
<br/><br/>


### Overlays

Color values can be specified as either `(R,G,B)` or in hex as `0xFFFFFF`. Time values can be given in seconds as a number followed by `s` (`123s` or `123.45s`), or as number of frames (e.g. `1234`).

#### Timecode Overlay

 * `time-code`: Enable timecode overlay: (`yes` or `no`).
<br/>*Default*: `time-code = no`
<br/><br/>

 * `time-code-margin`: Margin from edge in pixels.
<br/>*Default*: `time-code-margin = 5`
<br/><br/>

 * `time-code-font-scale`: Scale factor for text size.
<br/>*Default*: `time-code-font-scale = 2.0`
<br/><br/>

 * `time-code-font-thickness`: Thickness of font (integer values only).
<br/>*Default*: `time-code-font-thickness = 2`
<br/><br/>

 * `time-code-font-color`: Text color.
<br/>*Default*: `time-code-font-color = 255, 255, 255`
<br/><br/>

 * `time-code-bg-color`: Background color.
<br/>*Default*: `time-code-bg-color = 0, 0, 0`

#### Bounding Box Overlay

 * `bounding-box`: Enable bounding box overlay: (`yes` or `no`).
<br/>*Default*: `bounding-box = no`
<br/><br/>

 * `bounding-box-color`: Box edge color.
<br/>*Default*: `bounding-box-color = 255, 0, 0`
<br/><br/>

 * `bounding-box-thickness`: Thickness of bounding box, relative to largest edge of input video.
<br/>*Default*: `bounding-box-thickness = 0.0032`
<br/><br/>

 * `bounding-box-smooth-time`: Amount of temporal smoothing to apply (seconds or frames).
<br/>*Default*: `bounding-box-smooth-time = 0.1s`
<br/><br/>

 * `bounding-box-min-size`: Minimum side length of bounding box, relative to largest edge of input video.
<br/>`bounding-box-min-size = 0.032`
