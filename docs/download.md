---
hide:
  - navigation
  - toc
---


# :fontawesome-solid-download:Download

-------------------------------

## GUI Release (Beta)

A new GUI is under development for the next version of DVR-Scan and is available now for beta testing. The beta release can be [downloaded from Github](https://github.com/Breakthrough/DVR-Scan/releases/tag/v1.7-dev1). All current stable versions of DVR-Scan are command-line only.

Feedback for the new GUI is welcome. Users can download and install the beta ontop of an existing DVR-Scan installation, and it is compatible with all existing config and region files.

-------------------------------

## Python <span class="dvr-scan-download-icons">:fontawesome-brands-windows::fontawesome-brands-apple::fontawesome-brands-linux:</span>

!!! python-download "**1.6.2**<span class="dvr-scan-release-date">December 17, 2024</span>"

    <h3>pipx (recommended):</h3>

        pipx install dvr-scan[opencv]

    <h3>pip:</h3>

        python3 -m pip install dvr-scan[opencv]

DVR-Scan requires Python 3.9 or higher to run, and works on Windows, Linux, and OSX. [`pipx` is recommended](https://pipx.pypa.io/stable/installation/) for installing DVR-Scan, however installing via `pip` or from source is also supported.

Linux users may need to install the `python3-tk` package (e.g. `sudo apt install python3-tk`) to run the region editor.

-------------------------------

## Windows Distribution<span class="dvr-scan-download-icons">:fontawesome-brands-windows:</span>

!!! windows-download "**1.6.2**<span class="dvr-scan-release-date">December 17, 2024</span>"

    <div class="buttongrid buttongrid-download">[:fontawesome-solid-download: &nbsp; Installer `.msi`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.6.2-release/dvr-scan-1.6.2-win64.msi){ .md-button #download-button }[:fontawesome-solid-file-zipper: &nbsp; Portable `.zip`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.6.2-release/dvr-scan-1.6.2-win64.zip){ .md-button #changelog-button }</div>


The installer is recommended for most users.  Windows builds include all required dependencies to run DVR-Scan.  Only 64-bit builds are available.

-------------------------------

## Servers and Headless Systems

For installation on servers and other headless systems that do not require a GUI, install `dvr-scan[opencv-headless]` instead of `dvr-scan[opencv]`.  This will make sure that [the headless version of OpenCV](https://pypi.org/project/opencv-python-headless/) is installed, which avoids any dependencies on X11 libraries or any other GUI components.  This allows DVR-Scan to run with less dependencies, and can result in smaller Docker images.

-------------------------------

## Source

The source code for [DVR-Scan is available on Github](https://github.com/Breakthrough/DVR-Scan). It can be run directly from source (`python -m dvr_scan`), or built locally (`python -m build`).

-------------------------------


## CUDA®-Enabled Builds

GPU support currently requires a development environment setup including the Nvidia CUDA® SDK.

DVR-Scan works with CUDA graphics cards if you are using the Python distribution, and you have a CUDA-enabled verison of the `opencv-python` package. Unfortunately pre-built binaries are not available, so this requires that you build from source (there are various tutorials online for how to do this).

When available, you should see `cv2.cuda: Installed` under the features list when running `dvr-scan --version`. Make sure to set `-b MOG2_CUDA` when running DVR-Scan (e.g. `dvr-scan -i video.mp4 -b MOG2_CUDA`).

-------------------------------


<h3>Code Signing Policy</h3>

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).
