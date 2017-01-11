

After installation, you can run DVR-Scan from any terminal/command prompt by typing `dvr-scan` (try running `dvr-scan --version` to verify that everything was installed correctly).  If using a binary distribution on Windows, you need to run the program from the folder containing the `dvr-scan.exe` file, unless you perform the steps below.

------------------------------------------------

## Installation from Source (all platforms)

Start by downloading the latest release of DVR-Scan and extracting it to a location of your choice.  Make sure you have the appropriate [system requirements](#installing-dependencies) installed before continuing.  To ensure you have all the requirements installed, open a `python` interpreter, and ensure you can run `import numpy` and `import cv2` without any errors.

Once this is done, DVR-Scan can then be installed by running the following command in the location of the extracted files:

```md
sudo python setup.py install
```

Once finished, DVR-Scan will be installed, and you should be able to run the `dvr-scan` command from any terminal/command prompt.  To verify that everything was installed properly, try calling the following command:

```md
dvr-scan --version
```

To get familiar with DVR-Scan, try running `dvr-scan --help`, or see the [Getting Started & Examples](guide/examples.md) section.  If you encounter any runtime errors while running DVR-Scan, ensure that you have all the required dependencies listed in the System Requirements section above (again, you should be able to `import numpy` and `import cv2`).


### Installing Dependencies

If installing from source, DVR-Scan requires [Python 2 or 3](https://www.python.org/) (tested on 2.7.X, untested but should work on 2.X) and the following libraries ([quick install guide](http://breakthrough.github.io/Installing-OpenCV/)):

 - [OpenCV](http://opencv.org/) (compatible with both 2.X or 3.X) and the Python module (`cv2`)
 - [Numpy](http://sourceforge.net/projects/numpy/) Python module (`numpy`)

You can [click here](http://breakthrough.github.io/Installing-OpenCV/) for a quick guide (OpenCV + Numpy on Windows & Linux) on installing the latest versions of OpenCV/Numpy on [Windows (using pre-built binaries)](http://breakthrough.github.io/Installing-OpenCV/#installing-on-windows-pre-built-binaries) and [Linux (compiling from source)](http://breakthrough.github.io/Installing-OpenCV/#installing-on-linux-compiling-from-source).  If the Python module that comes with OpenCV on Windows is incompatible with your system architecture or Python version, [see this page](http://www.lfd.uci.edu/~gohlke/pythonlibs/#opencv) to obtain a pre-compiled (unofficial) module.

Note that some Linux package managers still provide older, dated builds of OpenCV (pre-3.0).  DVR-Scan is compatible with both versions, but if you want to ensure you have the latest version, it's recommended that you [build and install OpenCV from source](http://breakthrough.github.io/Installing-OpenCV/#installing-on-linux-compiling-from-source) on Linux.

------------------------------------------------

## Updating DVR-Scan

To update DVR-Scan when newer versions are released, follow the instructions for your installation method again.  You do not need to uninstall or remove any older versions of DVR-Scan when upgrading.

If using a binary/portable distribution, you can safely overwrite any existing files with the ones included with the new version.  If installing from source, running the installation command will automatially upgrade the existing DVR-Scan installation on the system.

