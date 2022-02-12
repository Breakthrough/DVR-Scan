

## Installation using Windows binaries (64-bit only)

After installing or extracting DVR-Scan, you can run it from any terminal/command prompt by typing `dvr-scan` (try running `dvr-scan --version` to verify that everything was installed correctly).  If using a portable distribution on Windows, you need to run the program from the folder containing the `dvr-scan.exe` file, or add the folder to your system's `%PATH%` variable.  This is not required if using the installer, as the installer will update your `%PATH` variable automatically.

## Installation from Pip via Pypi (all platforms)

If you have Python & pip installed, you can get DVR-Scan the following two ways:

<div class="important">
<h4 class="wy-text-neutral"><span class="fa fa-angle-double-down wy-text-info"></span> Including all dependencies:</h4>
<h3 class="wy-text-neutral"><tt>pip install dvr-scan[opencv,progress_bar]</tt></h3>
<h4 class="wy-text-neutral"><span class="fa fa-angle-down wy-text-info"></span> Without extras (OpenCV installation required):</h4>
<h3 class="wy-text-neutral"><tt>pip install dvr-scan</tt></h3>
</div>

After installation, you should be able to execute `dvr-scan` from any terminal/command prompt.

## Installation from Source (all platforms)

Start by downloading the latest release of DVR-Scan and extracting it to a location of your choice.  Make sure you have the appropriate [system requirements](#installing-dependencies) installed before continuing.  DVR-Scan requires Python, Numpy, and OpenCV to function correctly.

### Installing Dependencies

If installing from source, DVR-Scan requires [Python 2 or 3](https://www.python.org/) (tested on 3.X, untested but should work on 2.X) and the following libraries ([quick install guide](http://breakthrough.github.io/Installing-OpenCV/)).  Note that starting with DVR-Scan v1.5, the minimum required Python version will be 3.6.

 - [OpenCV](http://opencv.org/) (requires version 3.0 and above) the Python module (`pip install opencv-python`) as well as `opencv-contrib-python` is required for some features (e.g. `-b CNT`)
 - [Numpy](http://sourceforge.net/projects/numpy/) Python module (`numpy`)
 - [tqdm](https://pypi.python.org/pypi/tqdm), *optional* Python module (`tqdm`) for displaying progress bar and estimated time remaining

You can [click here](http://breakthrough.github.io/Installing-OpenCV/) for a quick guide (OpenCV + Numpy on Windows & Linux) on installing the latest versions of OpenCV/Numpy on [Windows (using pre-built binaries)](http://breakthrough.github.io/Installing-OpenCV/#installing-on-windows-pre-built-binaries) and [Linux (compiling from source)](http://breakthrough.github.io/Installing-OpenCV/#installing-on-linux-compiling-from-source).  If the Python module that comes with OpenCV on Windows is incompatible with your system architecture or Python version, [see this page](http://www.lfd.uci.edu/~gohlke/pythonlibs/#opencv) to obtain a pre-compiled (unofficial) module.

Note that some Linux package managers still provide older, dated builds of OpenCV (pre-3.0); if you want to ensure you have the latest version, it's recommended that you [build and install OpenCV from source](http://breakthrough.github.io/Installing-OpenCV/#installing-on-linux-compiling-from-source) on Linux.

### Installing DVR-Scan

To ensure you have all the requirements installed, open a `python` interpreter, and ensure you can run `import numpy` and `import cv2.bgsegm` without any errors (optionally, if you installed tqdm, run `import tqdm` as well).

DVR-Scan can then be installed by running the following command in the location of the extracted files:

```md
sudo python setup.py install
```

Once finished, DVR-Scan will be installed, and you should be able to run the `dvr-scan` command from any terminal/command prompt.  To verify that everything was installed properly, try calling the following command:

```md
dvr-scan --version
```

To get familiar with DVR-Scan, try running `dvr-scan --help`, or see the [Getting Started & Examples](examples.md) section.  If you encounter any runtime errors while running DVR-Scan, ensure that you have all the required dependencies listed in the System Requirements section above (again, you should be able to `import numpy` and `import cv2`, and optionally, `import tqdm` if tqdm was installed).


------------------------------------------------


## Updating DVR-Scan

To update DVR-Scan when newer versions are released, follow the instructions for your installation method again.  You do not need to uninstall or remove any older versions of DVR-Scan when upgrading.

If using the MSI installer, older versions of DVR-Scan will be upgraded automatically.  If using a portable distribution, you can safely overwrite any existing files with the ones included with the new version.  If installing from source, running the installation command will automatially upgrade the existing DVR-Scan installation on the system.

