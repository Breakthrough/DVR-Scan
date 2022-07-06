
## Quickstart

The following commands demonstrate some common use cases for DVR-Scan. You can also use `dvr-scan --help` for a complete listing of all options, or see the [Command-Line Reference](options.md). Note that the default program settings can be overriden by [creating a user config file](config_file.md).

To perform motion detection `video.mp4`, saving each motion event to a separate video in the current working directory:

    dvr-scan -i video.mp4

To save all output files in to a particular location, use `-d`/`--output-dir`:

    dvr-scan -i video.mp4 -d extracted_events/

To only perform detection on part of the frame, use the `-roi` flag:

    dvr-scan -i video.mp4 -roi

To draw a box around the areas of the frame containing motion:

    dvr-scan -i video.mp4 -bb

To use `ffmpeg` to extract motion events, set `-m`/`--output-mode` to `ffmpeg` (or `copy` to use stream copy mode):

    dvr-scan -i video.mp4 -m ffmpeg
    dvr-scan -i video.mp4 -m copy

The following section covers all the [command-line options](options.md) which can be used with DVR-Scan, including [motion event](options.md#motion-events)/[detection parameters](options.md#detection-parameters).
