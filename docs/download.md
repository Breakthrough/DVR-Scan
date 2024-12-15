---
hide:
  - navigation
  - toc
---


# :fontawesome-solid-download:Download
-------------------------------

## Python <span class="dvr-scan-download-icons">:fontawesome-brands-windows::fontawesome-brands-apple::fontawesome-brands-linux:</span>

!!! python-download "**1.6.1**<span class="dvr-scan-release-date">May 18, 2024</span>"

    <h3>Regular Install:</h3>

        pip install dvr-scan[opencv]==1.6.1

    <h3>Headless (Servers):</h3>

        pip install dvr-scan[opencv-headless]==1.6.1

DVR-Scan works on Windows, Linux, and OSX, and requires Python 3.8 or higher. Linux users may need to install the `python3-tk` package (e.g. `sudo apt-get install python3-tk`) to run the region editor.

-------------------------------

## Windows Distribution<span class="dvr-scan-download-icons">:fontawesome-brands-windows:</span>

!!! windows-download "**1.6.1**<span class="dvr-scan-release-date">May 18, 2024</span>"

    <div class="buttongrid buttongrid-download">[:fontawesome-solid-download: &nbsp; Installer `.msi`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.6.1-release/dvr-scan-1.6.1-win64.msi){ .md-button #download-button }[:fontawesome-solid-file-zipper: &nbsp; Portable `.zip`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.6.1-release/dvr-scan-1.6.1-win64.zip){ .md-button #changelog-button }</div>


The installer is recommended for most users.  Windows builds include all required dependencies to run DVR-Scan.  Only 64-bit builds are available.


-------------------------------


<h3>CUDA®-Enabled Builds (Experimental)</h3>

Nvidia CUDA® builds experimental and outdated due to difficulty producing binary distributions covering all systems and GPU architectures. If you require CUDA support, the Python version of DVR-Scan is compatible with any CUDA® enabled version of the `opencv-python` module.  You can get better performance or use DVR-Scan on a wider variety of GPUs if you build the module on your system, with the latest SDK version.

!!! cuda-download "**1.5.1 (Not Latest)**<span class="dvr-scan-release-date">:fontawesome-solid-triangle-exclamation:</span>"

    <div class="buttongrid buttongrid-download">[:fontawesome-solid-flask: &nbsp; CUDA® Build `.zip`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.5.1-release/dvr-scan-1.5.1-win64-cuda.zip){ .md-button #changelog-button }</div>

Make sure to set `-b MOG2_CUDA` when running DVR-Scan (e.g. `dvr-scan -i video.mp4 -b MOG2_CUDA`).


## Source

The source code for [DVR-Scan is available on Github](https://github.com/Breakthrough/DVR-Scan). It can be run directly from source (`python -m dvr_scan`), or built locally (`python -m build`).

-------------------------------


<h3>Code Signing Policy</h3>

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).
