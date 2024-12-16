---
hide:
  - navigation
  - toc
---

<img alt="DVR-Scan Logo" src="assets/dvr-scan.png" width="200rem"/>

<h1 id="dvr-scan-title">DVR-Scan</h1>
<h3 id="dvr-scan-subtitle">Find and extract motion events in videos.</h3>

------------------------------------------------------

!!! success "Latest Version: 1.6.2 (December 16, 2024)"

    <div class="buttongrid">[:fontawesome-solid-download: &nbsp; Download](download.md){ .md-button #download-button }[:fontawesome-solid-book: User Guide](guide.md){ .md-button #changelog-button }[:fontawesome-solid-bars: &nbsp; Documentation](docs.md){ .md-button #documentation-button }[:fontawesome-solid-gear: &nbsp; Resources](changelog.md){ .md-button #quickstart-button }</div>

------------------------------------------------------

DVR-Scan is a command-line application that **automatically detects motion events in video files** (e.g. security camera footage).  DVR-Scan looks for areas in footage containing motion, and saves each event to a separate video clip.  DVR-Scan is free and open-source software, and works on Windows, Linux, and Mac.

## :fontawesome-solid-person-running:Quickstart

Scan `video.mp4` (separate clips for each event):

    dvr-scan -i video.mp4

Only scan a region of interest ([see user guide](guide.md#region-editor) or hit `Ctrl + H` for controls):

    dvr-scan -i video.mp4 -r

<img alt="overlay example" src="assets/region-editor-multiple.jpg" width="480"/>

Draw boxes around motion:

    dvr-scan -i video.mp4 -bb

<img alt="overlay example" src="assets/bounding-box.gif" width="480"/>

Use `ffmpeg` to extract events:

    dvr-scan -i video.mp4 -m ffmpeg

Once installed, see [the user guide](guide.md) to get started, try one of the examples above, or type `dvr-scan --help`. Press `Ctrl + C` to stop processing at any time.

See the [documentation](docs.md) for a complete description of all [command-line](docs.md#dvr-scan-options) and [config file](docs.md#config-file) settings.
