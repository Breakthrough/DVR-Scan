
<h2>Frequently Asked Questions (FAQ)</h2>

This FAQ is a supplement to the user guide, and is intended to help solve the most common issues you may encounter when using DVR-Scan.  The topics covered on this page range from installation problems to methods for processing corrupted video files.


----------------------------------------------------------


### Why won't DVR-Scan open any video files?

If you're unable to get DVR-Scan to process any video files, including those available in the examples section, than you are either missing or have an improperly configured software dependency.

This usually happens because DVR-Scan is not able to find the OpenCV FFMPEG DLL, which is required to decode videos.  Try reinstalling OpenCV, ensuring that when finished, all of the compiled `opencv*.dll` binaries can be found somewhere in your system's `%PATH%` environment variable.

Windows users can also try downloading a binary/portable distribution, which includes DVR-Scan and all dependencies in a single .ZIP archive.  Note that the portable version can be "installed" after extracting by adding the folder containing `dvr-scan.exe` to your system's `%PATH%` environment variable, allowing you to use the `dvr-scan` command system-wide.


----------------------------------------------------------


### How can I improve the performance of DVR-Scan?

On the Getting Started & Examples page, see the [Performance section](examples.md#performance) under Motion Detection Parameters.  Additional performance improvements are being worked on for future versions (parallel processing, utilization of GPU, etc...).


----------------------------------------------------------


### How can I join/concatenate two or more video files for processing?

If you have a series of video clips from the same source, you can append subsequent video clips to the DVR-Scan input by including another `-i` flag for each file.  For example, to process three videos sequentially:

    dvr-scan -i first_video.mp4 -i second_video.mp4 -i third_video.mp4

The videos are processed in the same order as they appear in the command.  Note that each clip specified by `-i` must have the same resolution and framerate.


----------------------------------------------------------


### How can I fix a video that's corrupted, shows the wrong duration, or won't let me seek/fast-forward?

Video files with corrupted/malformed headers can sometimes be fixed by re-muxing them into a new container.  One tool you can use for this is `mkvtoolnix` (cross platform), using `mkvmerge` or the GUI to add the video and save it into a new `.mkv` file.

If all is successful, the output video should be roughly the same size as the original, and playback fine in most media players.  Specifically, it should also report the video's length accurately, and allow seeking throughout the video.


----------------------------------------------------------


### How do I run this in a Docker container?

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


### How do I submit bug reports, feature requests, or code changes?

Please submit any bug reports or feature requests to <a href="https://github.com/Breakthrough/DVR-Scan/issues" target="_blank" alt="DVR-Scan Issue Tracker @ Github">the issue tracker on Github</a>.

Code changes and pull requests are accepted and welcome, provided that the changes include fixes or improvements to the codebase, rather than just cosmetic changes, and that the changes meet or exceed the quality of the application codebase and standards guiding its development.

