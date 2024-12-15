
# :fontawesome-solid-circle-info: User Guide

## :fontawesome-solid-terminal:Running DVR-Scan

After installation, the `dvr-scan` command should be available from a terminal or command prompt. Try running `dvr-scan --help`.

!!! info "For portable versions, replace `dvr-scan` with the path to `dvr-scan.exe` in the extracted files on your system."

To extract all motion events from a video, you can start with:

    dvr-scan -i video.mp4

This will produce output events in your working directory starting with the prefix `video.DSME_` (e.g. `video.DSME_0001.avi`). If you want to limit scanning to a particular part of the video frame, you can use the [region editor](#region-editor):

    dvr-scan -i video.mp4 -r

DVR-Scan should provide good results for most use cases, but can be fine tuned for specific use cases. There are two main categories of these settings: [detection and sensitivity](docs.md#detection), and [event parameters](docs.md#events).

See [the documentation](docs.md) for a complete list of all command-line and configuration file options which can be set. You can also type `dvr-scan --help` for an overview of command line options. Lastly, most program options can be set [using a config file](docs.md#config-file).  DVR-Scan also looks for a `dvr-scan.cfg` file in the following locations:

 * Windows: `C:/Users/%USERNAME%/AppData/Local/DVR-Scan/dvr-scan.cfg`
 * Linux: `~/.config/DVR-Scan/dvr-scan.cfg` or `$XDG_CONFIG_HOME/dvr-scan.cfg`
 * OSX: `~/Library/Preferences/DVR-Scan/dvr-scan.cfg`

These settings will be used by default each time you run DVR-Scan, unless you override them.

### Running Without Terminal

A GUI is being developed for DVR-Scan but is not yet available. In the meantime, Windows users can see [Issue #178](https://github.com/Breakthrough/DVR-Scan/issues/178) for instructions on how to create drag-and-drop shortcuts to run DVR-Scan without needing to type commands.

### Multiple Videos

You can specify multiple input videos as long as they have the same resolution and framerate:

    dvr-scan -i video1.mp4 video2.mp4 video*.mp4

Wildcards are also supported:

    dvr-scan -i video*.mp4

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

### Output Format

By default, DVR-Scan uses the OpenCV VideoWriter for video output. This usually requires the output files be in .AVI format of some kind.

DVR-Scan also supports using `ffmpeg` to extract motion events. This is done by setting `-m`/`--output-mode` to `ffmpeg` (reencode) or `copy` (codec copy mode, may not be frame accurate). For example:

    dvr-scan -i video.mp4 -m ffmpeg

You can customize the options passed to `ffmpeg` using a [config file](docs.md#config-file) (see [the `ffmpeg-input-args` and `ffmpeg-output-args`](docs.md#output)) settings).

Setting output mode to `ffmpeg` or `copy` has the following caveats:

 - inputs that have a variable framerate (VFR) may not be  extracted reliably
 - input concatenation is not supported
 - overlays are not supported

You can customize the options passed to `ffmpeg` using a [config file](docs.md#config-file) (see [the `ffmpeg-input-args` and `ffmpeg-output-args`](docs.md#options)) settings).

### VFR (Variable Framerate)

!!! warning "Variable framerate (VFR) video support is still under development and may produce incorrect results."

Variable framerate (VFR) videos are *not well supported*, but basic functionality does work. Motion detection and event extraction should work correctly with default settings. Note however that calculated timestamps may be incorrect, and extracted footage may playback at the wrong speed.

Frame numbers will be accurate, but timestamps will not.  This can yield incorrect results when setting output mode to `ffmpeg` or `copy`, as well as inaccurate timestamps when using overlays. This issue is [tracked on Github](https://github.com/Breakthrough/PySceneDetect/issues/168).  If this workflow is required, you can re-encode the source material into fixed framerate before processing.


## :fontawesome-solid-crop-simple:Region Editor

With the Region Editor, you can limit motion detection to specific areas of the frame.  You can launch the region editor when starting DVR-Scan by adding `-r`/`--region-editor`:

    dvr-scan -i video.mp4 -r

The region editor will open and display a rectangle over the first frame:

<img alt="[Region Editor Startup Window]" src="../assets/region-editor-start.jpg"/>

You can use the mouse to add or move points when editing regions. Left click to add a new point, or drag an existing one. Right click can be used to delete a point, and to add/remove shapes.

To begin scanning, click File -> Start Scan. You will be prompted to save the regions you have created before scanning so you can re-use them if required.

### Regions

Regions are a set of points creating a closed shape. A rectangle will be created by default for you to modify.

<img alt="[Non-Rectangular Region Example]" src="../assets/region-editor-region.jpg"/>

Regions are edited individually, but all regions are used when scanning. To add a new shape, right click anywhere on the frame.

<img alt="[Multiple Region Example]" src="../assets/region-editor-multiple.jpg"/>

Regions can be selected using the Active Region selector at the bottom left, or cycled by using the `Tab` key. Note that only one region can be edited at a time.

By enabling mask mode (Toggle Mask at the bottom right), you can see the exact areas of the frame that DVR-Scan will consider for motion:

<img alt="[Mask Mode View]" src="../assets/region-editor-mask.jpg"/>

Regions can be saved/loaded for reusing across videos or editing via the File menu.

### Controls

Click Help -> Show Controls or press `Ctrl + H` (`Command + H` on Mac) to display all keyboard and mouse controls. You can move the canvas by holding `Ctrl` (`Command` on Mac) and dragging with left-click. The cursor icon should change depending on what mode the editor is in.

Most actions have keyboard shortcuts displayed beside the menu item. You can undo/redo any modifications or deletions when working on the regions by clicking Edit -> Undo/Redo or using your system's undo/redo keys.
