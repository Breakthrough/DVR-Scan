#
#       DVR-Scan: Find & Export Motion Events in Video Footage
#   --------------------------------------------------------------
#     [  Site: https://github.com/Breakthrough/DVR-Scan/   ]
#     [  Documentation: http://dvr-scan.readthedocs.org/   ]
#
# This file contains all code related to timecode formats, interpreting,
# parsing, and conversion.
#
# Copyright (C) 2016-2017 Brandon Castellano <http://www.bcastell.com>.
#
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file or visit one of the following pages for details:
#  - https://github.com/Breakthrough/DVR-Scan/
#
# This software uses Numpy and OpenCV; see the LICENSE-NUMPY and
# LICENSE-OPENCV files or visit the above URL for details.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#


def get_string(time_msec, show_msec = True):
    """ Formats a time, in ms, into a timecode of the form HH:MM:SS.nnnn.

    This is the default timecode format used by mkvmerge for splitting a video.

    Args:
        time_msec:  Integer representing milliseconds from start of video.
        show_msec:  If False, omits the milliseconds part from the output.
    Returns:
        A string with a formatted timecode (HH:MM:SS.nnnn).
    """
    out_nn, timecode_str = int(time_msec), ''

    base_msec = 1000 * 60 * 60  # 1 hour in ms
    out_HH = int(out_nn / base_msec)
    out_nn -= out_HH * base_msec

    base_msec = 1000 * 60       # 1 minute in ms
    out_MM = int(out_nn / base_msec)
    out_nn -= out_MM * base_msec

    base_msec = 1000            # 1 second in ms
    out_SS = int(out_nn / base_msec)
    out_nn -= out_SS * base_msec

    if show_msec:
        timecode_str = "%02d:%02d:%02d.%03d" % (out_HH, out_MM, out_SS, out_nn)
    else:
        timecode_str = "%02d:%02d:%02d" % (out_HH, out_MM, out_SS)

    return timecode_str


def frame_to_timecode(frames, fps, show_msec = True):
    """ Converts a given frame/FPS into a timecode of the form HH:MM:SS.nnnn.

    Args:
        frames:     Integer representing the frame number to get the time of.
        fps:        Float representing framerate of the video.
        show_msec:  If False, omits the milliseconds part from the output.
    Returns:
        A string with a formatted timecode (HH:MM:SS.nnnn).
    """
    time_msec = 1000.0 * float(frames) / fps
    return get_string(time_msec, show_msec)

