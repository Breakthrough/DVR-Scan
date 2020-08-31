<img alt="DVR-Scan Logo" src="img/dvr-scan-logo_small.png"/>
<h4 class="wy-text-info" style="margin-top:-1em;">Find and extract motion events in videos.</h4>

<div class="important">
<h3 class="wy-text-neutral"><span class="fa fa-info-circle wy-text-info"></span>&nbsp; Latest Release: <b>v1.1</b> (July 12, 2020)</h3>
<a href="download/" class="btn btn-info" style="margin-bottom:8px;" role="button"><span class="fa fa-download"></span>&nbsp; <b>Download</b>&nbsp;&nbsp;(all platforms)</a> &nbsp;&nbsp;&nbsp;&nbsp; <a href="guide/installing/" class="btn btn-success" style="margin-bottom:8px;" role="button"><span class="fa fa-gear"></span>&nbsp; <b>Installation</b></a> &nbsp;&nbsp;&nbsp;&nbsp; <a href="guide/examples/" class="btn btn-warning" style="margin-bottom:8px;" role="button"><span class="fa fa-book"></span>&nbsp; <b>Getting Started</b></a>
</div>


**DVR-Scan** is a cross-platform command-line (CLI) application that **automatically detects motion events in video files** (e.g. security camera footage).  In addition to locating both the time and duration of each motion event, DVR-Scan will save the footage of each motion event to a new, separate video clip.  Not only is DVR-Scan free and open-source software (you can find [DVR-Scan on Github](https://github.com/Breakthrough/DVR-Scan)), it's written in Python, based on Numpy and OpenCV, and was built to be extendable and hackable.

For users wanting finer control over the output video encoding method, the default timecode format (`HH:MM:SS.nnnn`) is compatible with most popular video tools, so in most cases the motion events DVR-Scan finds can be simply copied and pasted into another tool of your choice (e.g. `ffmpeg`, `avconv` or the `mkvtoolnix` suite).
