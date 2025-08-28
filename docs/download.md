---
hide:
  - navigation
  - toc
---


# :fontawesome-solid-download:Download

-------------------------------

## Python<span class="dvr-scan-download-icons">:fontawesome-brands-windows::fontawesome-brands-apple::fontawesome-brands-linux:</span>

!!! python-download "**1.8.1**<span class="dvr-scan-release-date">August 27, 2025</span>"

    <h3>pipx (recommended):</h3>

        pipx install dvr-scan

    <h3>pip:</h3>

        python3 -m pip install dvr-scan

DVR-Scan requires Python 3.9 or higher to run, and works on Windows, Linux, and OSX. [`pipx` is recommended](https://pipx.pypa.io/stable/installation/) for installing DVR-Scan, however installing via `pip` or from source is also supported.

Linux users may need to install the `python3-tk` package (e.g. `sudo apt install python3-tk`) to run the region editor.

-------------------------------

## Windows<span class="dvr-scan-download-icons">:fontawesome-brands-windows:</span>

!!! windows-download "**1.8.1**<span class="dvr-scan-release-date">August 27, 2025</span>"

    <div class="buttongrid buttongrid-download">[:fontawesome-solid-download: &nbsp; Installer `.msi`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.8.1-release/dvr-scan-1.8.1-win64.msi){ .md-button #download-button }[:fontawesome-solid-file-zipper: &nbsp; Portable `.zip`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.8.1-release/dvr-scan-1.8.1-win64.zip){ .md-button #changelog-button }</div>


The installer is recommended for most users.  Windows builds include all required dependencies to run DVR-Scan.  Only 64-bit builds are available.

-------------------------------

## Servers

For headless systems that do not require the UI,  you can install `dvr-scan-headless`.  This will make sure that [the headless version of OpenCV](https://pypi.org/project/opencv-python-headless/) is installed, which avoids any dependencies on X11 libraries or any other GUI components.  This allows DVR-Scan to run with less dependencies, and can result in smaller Docker images.

-------------------------------

## Source

The source code for [DVR-Scan is available on Github](https://github.com/Breakthrough/DVR-Scan). It can be run directly from source (`python -m dvr_scan`), or built locally (`python -m build`).

-------------------------------


## CUDA® Support

DVR-Scan works with CUDA graphics cards *if* you are using the Python distribution, *and* you have a CUDA-enabled verison of the `opencv-python` package.

!!! warning "GPU support requires a development environment setup including the Nvidia CUDA® SDK."

It is recommended to build and install OpenCV with the CUDA module enabled (there are various tutorials online for how to do this).  There is also an [unofficial pre-built Python wheel](https://github.com/cudawarped/opencv-python-cuda-wheels/releases/tag/4.11.0.20250124) maintained by James Bowley which can be downloaded and installed via `pip`.

When available, you should see `cv2.cuda: Installed` under the features list when running `dvr-scan --version`. Make sure to set `-b MOG2_CUDA` when running DVR-Scan (e.g. `dvr-scan -i video.mp4 -b MOG2_CUDA`).  In the UI, under this can be found under Settings -> Motion -> Subtractor.

-------------------------------


<h3>Code Signing Policy</h3>

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).
