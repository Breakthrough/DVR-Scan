
# :fontawesome-solid-circle-info: User Guide

## :fontawesome-solid-terminal:Running `dvr-scan`

After installation, you can run DVR-Scan from any terminal or command-prompt.  To start, it helps to have a clip with some motion you can use for testing.  If the video is too long, or motion occurs mid-way through, you can [set the start/end/duration](docs.md#seekingduration) for processing.

DVR-Scan should provide good results for most use cases, but can be fine tuned for specific use cases. For example, DVR-Scan includes some footage before/after the motion event, but this can be disabled (or extended) by changing the [motion event parameters](docs.md#events).  Motion detection parameters, including sensitivity and other processing settings, [can also be configured](#tuning-detection).

See [the documentation](docs.md) for a complete list of all command-line and configuration file options which can be set. You can also type `dvr-scan --help` for an overview of command line options. Lastly, most program options can be set [using a config file](docs.md#config-file).  DVR-Scan also looks for a `dvr-scan.cfg` file in the following locations:

 * Windows: `C:/Users/%USERNAME%/AppData/Local/DVR-Scan/dvr-scan.cfg`
 * Linux: `~/.config/DVR-Scan/dvr-scan.cfg` or `$XDG_CONFIG_HOME/dvr-scan.cfg`
 * OSX: `~/Library/Preferences/DVR-Scan/dvr-scan.cfg`

These settings will be used by default each time you run DVR-Scan, unless you override them.

## Processing Multiple Videos

You can specify multiple input videos as long as they have the same resolution and framerate:

    dvr_scan -i video1.mp4 video2.mp4 video*.mp4

Wildcards are also supported:

    dvr_scan -i video*.mp4

Note that this will **concatenate** the videos together *in the order they are specified*.

This can be undesirable for some types of footage being analyzed.  For example, if a folder contains different dashcam footage clips, a significant amount of time can pass between clips (e.g. when the vehicle is shut off).  This can result in DVR-Scan generating false events between videos.

To avoid this, you can run DVR-Scan on each video in a loop. For example, on Windows:

    for /F %i in ('dir *.mp4 /b') do dvr-scan -i %i

Or on Linux/OSX:

    for f in /mnt/videos/*.mp4
    do
        dvr-scan -i $f
    done

Note that multiple inputs also do not support other output modes. You can use `ffmpeg` to [concatenate all input videos](https://trac.ffmpeg.org/wiki/Concatenate) before processing, or use a for-loop as above.

## Variable Framerate Videos

Variable framerate videos are not well supported, but some functionality does work.  Frame numbers will be accurate, but timestamps will not.  This can yield incorrect results when setting output mode to `ffmpeg` or `copy`, as well as inaccurate timestamps when using overlays. This issue is [tracked on Github](https://github.com/Breakthrough/PySceneDetect/issues/168).  If this workflow is required, you can re-encode the source material into fixed framerate before processing.


## :fontawesome-solid-crop-simple:Region Editor

DVR-Scan allows defining a region to limit detection.  For example, on a doorbell camera, you may want to limit detection to only your front porch. DVR-Scan includes a region editor which can be started by including `-r`/`--region-editor`:

    dvr-scan -i video.mp4 -r

This should show a window that appears similar to:

<img alt="region editor startup window" src="../assets/region-editor-start.jpg"/>

Press `H` to print a list of all controls.  Press `S` to save the current regions to a file, or `O` to load existing ones.  Regions can also be set, saved, and loaded [from the command line](docs.md#regions). Regions from the command line also appear in the the region editor, and any edits will be applied before processing.

When you are satisfied with the region, press space bar or enter/return to start processing the video.  Hit escape at any time to quit the program.

### Regions

You can use the left mouse button to add a new point to the current region, or drag existing points.  Points can be deleted by middle clicking (or right-click on Windows).  This allows you to create complex shapes, such as:

<img alt="example of non-rectangular region" src="../assets/region-editor-region.jpg"/>

You can hit `M` to view a cutout of the active mask:

<img alt="example of region mask" src="../assets/region-editor-mask.jpg"/>

A new region can be created by pressing `A`, and the selected region can be deleted by pressing `X`.  Regions can be selected using the number keys `1`-`9`, or by pressing `k`/`l` to select the previous/next region. Note that only one region can be active at a time (you must select an existing shape to modify it).

<img alt="example of region mask" src="../assets/region-editor-multiple.jpg"/>
