
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

Adjusting [motion detection settings](docs.md#motion-settings) can have a large effect on performance:

 - Limiting detection to a specific region of the frame with the region editor will also improve performance
 - Setting the output mode to either `ffmpeg` or `copy` can also improve performance compared to the default (`opencv`)
 - Downscaling high resolution videos can also improve performance greatly, at the expense of accuracy


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

Each video **must** have the same resolution and framerate. Videos are processed in the same order as they appear in the command, and extracted events will use the first video's filename as a template.

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

This will build the container, and then to run it on a file in the local directory, you'd run the command like this:

```
$ docker run --rm -it -v $(pwd):/videos/ dvr-scan -i your_video_file.mkv
```

The most important thing to keep in mind is the `-v` flag, which specifies the local folders to share. Inside the docker container `/videos/` is the working directory, so map that to wherever you want to process your files.


----------------------------------------------------------


### How can I submit a bug report?

Bug reports can be submitted to the <a href="https://github.com/Breakthrough/DVR-Scan/issues" target="_blank" alt="DVR-Scan Issue Tracker ">DVR-Scan issue tracker</a>.  Please provide as much information as possible to help triage the issue you are facing, and upload any sample material with the report when possible.



----------------------------------------------------------


### I have another question...

For technical help:

 - Try [starting a discussion](https://github.com/Breakthrough/DVR-Scan/discussions) on Github
 - Ask on the [DVR-Scan Discord server](https://discord.gg/69kf6f2Exb)
