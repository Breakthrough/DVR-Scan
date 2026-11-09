
# :fontawesome-solid-keyboard:Frequently Asked Questions


## Command-Line Interface


----------------------------------------------------------


### How can I stop DVR-Scan?

Hit `Ctrl + C` on your keyboard to exit DVR-Scan.


----------------------------------------------------------


### Where is the output saved?

DVR-Scan saves all files in the current working directory (the location you are invoking the `dvr-scan` command from). You can override the output directory by setting [the `-d`/`--output-dir` option](docs.md#output):

```
dvr-scan -i video.mp4 -d events_folder/
```

This can also be done [with a config file](docs.md#config-file).


----------------------------------------------------------


### How can I scan all videos in a folder?

You can use a wildcard in the input path to select multiple videos:

```
dvr-scan -i folder/*.mp4

```

You can also specify multiple paths directly.  Multiple inputs are not supported when `-m`/`--output-mode` is set to `ffmpeg` or `copy`. You can use `ffmpeg` to [concatenate all input videos](https://trac.ffmpeg.org/wiki/Concatenate) *before* using DVR-Scan as a workaround.

Note that DVR-Scan will **concatenate** the videos together **in the order they are specified** (or expanded if using wildcards). To avoid this, you can run DVR-Scan on each video in a loop. For example, on Windows:

```
for /F %i in ('dir *.mp4 /b') do dvr-scan -i %i
```

Or on Linux/OSX:

```
target="/some/folder"
for f in "$target"*
do
   dvr-scan -i $f
done
```


----------------------------------------------------------


### How can I improve scanning performance?

Adjusting [motion detection settings](docs.md#motion) can have a large effect on performance:

 - Limiting detection to a specific region of the frame with the region editor will also improve performance
 - Setting the output mode to either `ffmpeg` or `copy` can also improve performance compared to the default (`encode`), since they avoid re-encoding every frame
 - Downscaling high resolution videos can also improve performance greatly, at the expense of accuracy


----------------------------------------------------------


### Why is some motion not detected (or why are there false detections)?

For each frame, DVR-Scan calculates a *motion score* and compares it against the [`-t`/`--threshold`](docs.md#motion) setting (default `0.15`). The score is the average value of the motion mask (`0` for background, `255` for motion) over every pixel in the frame, or over the detection regions if any are set. For example, a moving object covering 1% of the frame scores about `2.5`, and the default threshold is reached when roughly 0.06% of the pixels are moving.

Because the score is an average, the same object scores lower the larger the area it is averaged over. A small or distant subject (e.g. a person at the far end of a long hallway) can be picked up perfectly by the background subtractor and still score below the threshold. Limiting detection to a smaller region around where the motion happens raises its score.

**If motion is missed**, try the following, in order:

 1. Lower the threshold (e.g. `-t 0.05`, or lower for very small or distant subjects).
 2. Set the noise reduction kernel size to `-k 3`, or disable it with `-k 0`. The default (`auto`) uses a larger kernel for high resolution videos (`7` for 1080p or higher), which removes moving objects smaller than the kernel.
 3. Do not downscale or skip frames: keep `-df`/`--downscale-factor` and `-fs`/`--frame-skip` at their defaults (no downscaling, no frame skipping).
 4. Limit detection to a smaller region around the area of interest (see [Regions](docs.md#regions) and the [region editor](guide.md#region-editor)).
 5. In the app, start from the <b>High Sensitivity</b> [preset](docs.md#presets).

**If there are too many false detections** (e.g. from foliage, shadows, rain, or lighting changes):

 - Raise the threshold.
 - Raise `-l`/`--min-event-length` so short bursts of noise do not trigger an event.
 - Raise the `variance-threshold` [config option](docs.md#config-file) (MOG2 only).
 - Use a larger kernel size (e.g. `-k 5` or `-k 7`).
 - Use regions to exclude areas with constant movement (trees, busy roads, screens).
 - In the app, start from the <b>Low Sensitivity</b> [preset](docs.md#presets).

**Use the motion mask to find the cause.** Generate a motion mask video without extracting any events:

```
dvr-scan -i video.mp4 -so -fm -mo mask.mp4
```

The mask shows what the detector sees after downscaling and noise reduction: moving pixels are white, the background is black, and areas outside the detection regions are gray. If the subject is visible in the mask but no event is detected, the threshold is too high for the size of the frame or region. If the subject is missing from the mask, reduce the kernel size or downscale factor. The `-fm`/`--frame-metrics` flag draws the motion score of each frame in the top right corner (of the mask, and of extracted events), which helps when choosing a threshold. The mask is encoded using ffmpeg when it is available; otherwise it is written with OpenCV, in which case use an `.avi` filename (e.g. `-mo mask.avi`).

The detection parameters in use (threshold, kernel size, downscale factor, frame skip, etc.) are logged at the start of every scan, which is useful to include when asking for help.

Subjects close to the camera produce much higher scores than distant ones, so a single threshold may not suit both. All regions in a scan are combined into a single area for scoring, so if both matter, run separate scans, each with its own region and threshold (e.g. a small region around the distant area with a lower threshold).


----------------------------------------------------------


### How can I join several videos together when processing?

If you have a series of video clips from the same source, you can append subsequent video clips to the DVR-Scan input by including multiple files after `-i`.  For example:

```
dvr-scan -i video0000.mp4 video0001.mp4 video0002.mp4

```

You can also use wildcards in the input path:

```
dvr-scan -i video*.mp4

```

Each video **must** have the same resolution (framerates do not need to match exactly). Videos are processed in the same order as they appear in the command (wildcard matches are sorted by filename), and each extracted event is named after the input video containing the start of the event.

Multiple input videos are not supported when output mode `-m`/`--output-mode` is set to either `ffmpeg` or `copy`. As a workaround, you can [use ffmpeg to concatenate all input videos](https://trac.ffmpeg.org/wiki/Concatenate) before using DVR-Scan to process them.


----------------------------------------------------------


### How can I fix a video that plays but cannot be scanned?

Video files with corrupted/malformed headers can sometimes be fixed by re-muxing them into a new container.  This can be done using either `ffmpeg` or `mkvmerge` (both tools support codec copying mode).

If the process is successful, the output video should be roughly the same size as the original, and playback fine in most media players.  Specifically, it should also report the video's length accurately, and allow seeking throughout the video.


----------------------------------------------------------


### How do I run DVR-Scan in a Docker container?

DVR-Scan comes with a Dockerfile so you can easily get things working without worrying about installing dependencies locally. Simply [install Docker](https://docs.docker.com/get-docker/), then run the following in the root of the project:

```
$ docker build -t dvr-scan .
```

This will build an image containing the latest release of DVR-Scan (from PyPI) along with ffmpeg. To run it on a file in the current directory, you'd run the command like this:

```
$ docker run --rm -it -v "$(pwd):/videos/" dvr-scan -i your_video_file.mkv -d motion_events
```

The most important thing to keep in mind is the `-v` flag, which specifies the local folder to share with the container (use `${PWD}` instead of `$(pwd)` in PowerShell, or `%cd%` in the Windows command prompt). Inside the container `/videos/` is the working directory, so map that to wherever your files are: relative paths passed to `dvr-scan` (e.g. the input file above and the `-d`/`--output-dir` folder) are then resolved inside that folder. Extracted events are written to the shared folder (here `motion_events/` in the current directory), which is also where DVR-Scan looks for files when you run it with a wildcard:

```
$ docker run --rm -it -v "$(pwd):/videos/" dvr-scan -i "*.mp4" -d motion_events
```

The wildcard should be quoted so that it is expanded by DVR-Scan inside the container rather than by your shell, which only sees paths on the host.


----------------------------------------------------------


### How can I submit a bug report?

Bug reports can be submitted to the <a href="https://github.com/Breakthrough/DVR-Scan/issues" target="_blank" alt="DVR-Scan Issue Tracker ">DVR-Scan issue tracker</a>.  Please provide as much information as possible to help triage the issue you are facing, and upload any sample material with the report when possible.



----------------------------------------------------------


### I have another question...

For technical help:

 - Try [starting a discussion](https://github.com/Breakthrough/DVR-Scan/discussions) on Github
 - Ask on the [DVR-Scan Discord server](https://discord.gg/69kf6f2Exb)
