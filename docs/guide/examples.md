
## Basic Usage / Quick-Start

For a list of all options/arguments DVR-Scan will accept:

    dvr-scan --help

To see what version of DVR-Scan is installed:

    dvr-scan --version

----------------------

### Examples

To perform motion detection on a file `some_video.mp4`, saving each event to a separate video clip (default), specify the `-i` / `--input` option (required):

    dvr-scan -i some_video.mp4

To use scan-only mode, which doesn't create or change any files, use the `-so` / `--scan-only` option:

    dvr-scan -i some_video.mp4 -so

By default, scan-only mode outputs a list of comma-separated timecodes for each event. To output all motion events in a single video (must end in `.avi`) specify the `-o` / `--output` option:

    dvr-scan -i some_video.mp4 -o some_video_motion_only.avi

For users wanting finer control over the output video encoding method, the default timecode format (`HH:MM:SS.nnnn`) is compatible with most popular video tools, so in most cases the motion events DVR-Scan finds can be simply copied and pasted into another tool of your choice (e.g. `ffmpeg`, `avconv` or the `mkvtoolnix` suite).

----------------------


## Motion Detection Parameters

The following parameters directly affect the "sensitivity" of the detection algorithm, and may need to be adjusted for some video footage to achieve desirable results.

 - `-t` / `-threshold`: The threshold a frame's motion score must meet to trigger a motion event.  Default is 0.15, lower values (e.g. 0.08) will be more sensitive to changes, whereas higher values will be less sensitive (e.g. 0.5).  If the output contains scenes without any motion, or background movement causes false events to be detected, try raising the threshold value.
 - `-l` / `--min-event-length`: Number of frames in a row that must exceed the set threshold value in order to trigger a motion event (default is 2 frames).  Represents the size of the event detection window, should only need to be adjusted for footage with very low or high framerates.  In most cases the default value should be sufficient. 
 - `-k` / `--kernel-size`: The size of the noise reduction kernel, must be an odd integer, or -1 to set automatically (based on video resolution).  Default values are 3 for SD, 5 for 720p, and 7 for 1080p and above.  Higher values indicate more aggressive noise removal.  In most cases the default value should be sufficient.

The following two parameters can be adjusted to specify how much of the original video clip is included in the output events:

 - `-tp` / `--time-post-event`: Event continuation window size, or the number of frames to include after the frame's motion score falls below the threshold (default 2.0 seconds).  Any frames that score above the threshold during this interval will be added to the motion event, and reset the counter.
 - `-tb` / `--time-before-event`: Number of frames (or timecode/length) to include before a detected motion event (default 1.5 seconds), if possible.  Represents the maximum amount a given event's beginning timecode can be shifted back.  Unlike `-l` or `-tp`, this option has no effect on the actual detection process, only the starting timecode of the current event when output.

----------------------


For further options (such as input seeking or length limiting), after installing DVR-Scan, run `dvr-scan --help` to display the full list of options.

