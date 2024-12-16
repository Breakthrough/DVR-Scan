---
hide:
  - navigation
  - toc
---


# :fontawesome-solid-download:Download
-------------------------------

## Python <span class="dvr-scan-download-icons">:fontawesome-brands-windows::fontawesome-brands-apple::fontawesome-brands-linux:</span>

!!! python-download "**1.6.2**<span class="dvr-scan-release-date">December 16, 2024</span>"

    <h3>Regular Install:</h3>

        pip install dvr-scan[opencv]==1.6.2

    <h3>Headless (Servers):</h3>

        pip install dvr-scan[opencv-headless]==1.6.2

DVR-Scan works on Windows, Linux, and OSX, and requires Python 3.8 or higher. Linux users may need to install the `python3-tk` package (e.g. `sudo apt-get install python3-tk`) to run the region editor.

-------------------------------

## Windows Distribution<span class="dvr-scan-download-icons">:fontawesome-brands-windows:</span>

!!! windows-download "**1.6.2**<span class="dvr-scan-release-date">December 16, 2024</span>"

    <div class="buttongrid buttongrid-download">[:fontawesome-solid-download: &nbsp; Installer `.msi`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.6.2-release/dvr-scan-1.6.2-win64.msi){ .md-button #download-button }[:fontawesome-solid-file-zipper: &nbsp; Portable `.zip`](https://github.com/Breakthrough/DVR-Scan/releases/download/v1.6.2-release/dvr-scan-1.6.2-win64.zip){ .md-button #changelog-button }</div>


The installer is recommended for most users.  Windows builds include all required dependencies to run DVR-Scan.  Only 64-bit builds are available.


-------------------------------


<h3>CUDA®-Enabled Builds (Experimental)</h3>

GPU support currently requires a development environment setup including the Nvidia CUDA® SDK.

DVR-Scan works with CUDA graphics cards if you are using the Python distribution, and you have a CUDA-enabled verison of the `opencv-python` package. Unfortunately pre-built binaries are not available, so this requires that you build from source (there are various tutorials online for how to do this).

When available, you should see `cv2.cuda: Installed` under the features list when running `dvr-scan --version`. Make sure to set `-b MOG2_CUDA` when running DVR-Scan (e.g. `dvr-scan -i video.mp4 -b MOG2_CUDA`).


## Source

The source code for [DVR-Scan is available on Github](https://github.com/Breakthrough/DVR-Scan). It can be run directly from source (`python -m dvr_scan`), or built locally (`python -m build`).

-------------------------------


<h3>Code Signing Policy</h3>

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).
