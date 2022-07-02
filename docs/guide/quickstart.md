

## Quickstart

The following commands demonstrate some common use cases for DVR-Scan. You can also use `dvr-scan --help` for a complete listing of all options.

To perform motion detection on a file `video.mp4`, saving each motion event to a separate video in the current working directory:

    dvr-scan -i video.mp4

To save all files to a particular folder, use `-d`/`--output-dir`:

    dvr-scan -i video.mp4 -d extracted_events/

To only perform detection on part of the frame, use the `-roi` flag (can either specify a bounding box via command line, or leave blank for a pop-up window):

    dvr-scan -i video.mp4 -roi

To draw a box around the areas of the frame containing motion:

    dvr-scan -i video.mp4 -bb

By default, OpenCV is used for writing the output. If you have ffmpeg available and would prefer that, it can be used by setting `-m`/`--mode` to `ffmpeg`:

    dvr-scan -i video.mp4 -m ffmpeg

Encoding parameters can be specified via the `ffmpeg-output-args` option in a config file.  Codec copying mode is also supported using ffmpeg by specifying `--mode copy`.

The following section covers all the [command-line options](options.md) which can be used with DVR-Scan.
