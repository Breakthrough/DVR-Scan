<h1 class="wy-text-neutral">DVR-Scan &nbsp;<span class="fa fa-film wy-text-info"></span></h1>

<div class="important">
<h3 class="wy-text-neutral"><span class="fa fa-info-circle wy-text-info"></span>&nbsp; Latest Release: <b>v0.1</b> (TBD)</h3>
</div>


**DVR-Scan** is a cross-platform command-line (CLI) application that **automatically detects motion events in video files** (e.g. security camera footage), for both finding the time/location of each motion event, as well as exporting each to a new, separate video file.  Not only is DVR-Scan free and open-source software (FOSS), it is written in Python, based on OpenCV and Numpy, and is easily extendable.

For users wanting finer control over the output video encoding method, the default timecode format (`HH:MM:SS.nnnn`) is compatible with most popular video tools, so in most cases the motion events DVR-Scan finds can be simply copied and pasted into another tool of your choice (e.g. `ffmpeg`, `avconv` or the `mkvtoolnix` suite).
