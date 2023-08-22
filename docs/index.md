---
hide:
  - navigation
  - toc
---

<img alt="DVR-Scan Logo" src="assets/dvr-scan.png" width="200rem"/>

<h1 id="dvr-scan-title">DVR-Scan</h1>
<h3 id="dvr-scan-subtitle">Find and extract motion events in videos.</h3>

------------------------------------------------------

!!! success "Latest Version: 1.5.1 (August 15, 2022)"

    <div class="buttongrid">[:fontawesome-solid-download: &nbsp; Download](download.md){ .md-button #download-button }[:fontawesome-solid-book: Documentation](docs.md){ .md-button #changelog-button }[:fontawesome-solid-bars: &nbsp; Changelog](changelog.md){ .md-button #documentation-button }[:fontawesome-solid-gear: &nbsp; Resources](resources.md){ .md-button #quickstart-button }</div>

------------------------------------------------------

DVR-Scan is a command-line application that **automatically detects motion events in video files** (e.g. security camera footage).  DVR-Scan looks for areas in footage containing motion, and saves each event to a separate video clip.  DVR-Scan is free and open-source software, and works on Windows, Linux, and Mac.

## :fontawesome-solid-person-running:Quickstart

Scan `video.mp4` (separate clips for each event):

    dvr-scan -i video.mp4

Only scan a region of interest (select with mouse):

    dvr-scan -i video.mp4 -roi

Draw boxes around motion:

    dvr-scan -i video.mp4 -bb

Use `ffmpeg` to extract events:

    dvr-scan -i video.mp4 -m ffmpeg

See [the documentation](docs.md) for a complete list of all command-line and configuration file options which can be set. You can also type `dvr-scan --help` for an overview of command line options. Some program options can also be set [using a config file](docs.md#config-file).
