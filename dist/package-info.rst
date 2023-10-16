
DVR-Scan
==========================================================

Video Motion Event Detection and Extraction Tool
----------------------------------------------------------

.. image:: https://img.shields.io/github/actions/workflow/status/Breakthrough/DVR-Scan/build.yml
   :target: https://github.com/Breakthrough/DVR-Scan/actions

.. image:: https://img.shields.io/github/release/Breakthrough/DVR-Scan.svg
   :target: https://github.com/Breakthrough/DVR-Scan

.. image:: https://img.shields.io/pypi/status/dvr-scan.svg
   :target: https://github.com/Breakthrough/DVR-Scan

.. image:: https://raster.shields.io/pypi/l/dvr-scan.png
   :target: http://pyscenedetect.readthedocs.org/en/latest/copyright/

.. image:: https://img.shields.io/github/stars/Breakthrough/DVR-Scan.svg?style=social&label=View%20on%20Github
   :target: https://github.com/Breakthrough/DVR-Scan

----------------------------------------------------------

Website: http://www.dvr-scan.com/

Documentation: http://dvr-scan.readthedocs.org/

Github: https://github.com/Breakthrough/DVR-Scan/


DVR-Scan is a command-line application that **automatically detects motion events in video files** (e.g. security camera footage).  DVR-Scan looks for areas in footage containing motion, and saves each event to a separate video clip.  DVR-Scan is free and open-source software, and works on Windows, Linux, and Mac.

Quickstart
----------------------------------------------------------

Install using ``pip``:

   pip install --upgrade dvr-scan[opencv]

Scan ``video.mp4`` (separate clips for each event)::

    dvr-scan -i video.mp4

Only scan a region of interest (`see user guide <http://www.dvr-scan.com/guide/>`_ or hit `H` for controls)::

    dvr-scan -i video.mp4 -r

.. image:: https://raw.githubusercontent.com/Breakthrough/DVR-Scan/releases/1.6/docs/assets/region-editor-mask.jpg
  :width: 480
  :alt: overlay example

Draw boxes around motion::

    dvr-scan -i video.mp4 -bb

.. image:: https://raw.githubusercontent.com/Breakthrough/DVR-Scan/releases/1.6/docs/assets/bounding-box.gif
  :width: 480
  :alt: overlay example

Use ``ffmpeg`` to extract events::

    dvr-scan -i video.mp4 -m ffmpeg

For help or other issues, feel free to submit any bugs or feature requests to Github:

https://github.com/Breakthrough/DVR-Scan/issues

----------------------------------------------------------

Licensed under BSD 2-Clause (see the ``LICENSE`` file for details).

Copyright (C) 2016-2023 Brandon Castellano.
All rights reserved.

