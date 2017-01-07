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



class FrameTimecode(object):

    def __init__(self, fps, timecode):
        if not isinstance(fps, (int, float)):
            raise TypeError('Framerate must be of type int/float.')
        self.framerate = float(fps)
        self.frame_num = -1
        if isinstance(timecode, int):
            if timecode < 0:
                raise ValueError('Timecode value must be positive.')
            self.frame_num = int(timecode)
        elif isinstance(timecode, float):
            if timecode < 0.0:
                raise ValueError('Timecode value must be positive.')
            self.frame_num = int(timecode * self.framerate)
        elif isinstance(timecode, (list, tuple)) and len(timecode) == 3:
            if any(not isinstance(x, (int, float)) for x in timecode):
                raise ValueError('Timecode components must be of type int/float.')
            hrs, mins, secs = timecode
            if not (hrs >= 0 and mins >= 0 and secs >= 0 and mins < 60
                    and secs < 60):
                raise ValueError('Timecode components must be positive.')
            secs += (((hrs * 60.0) + mins) * 60.0)
            self.frame_num = int(secs * self.framerate)
        elif isinstance(timecode, str):
            if timecode.endswith('s'):
                secs = timecode[:-1]
                if not secs.replace('.', '').isdigit():
                    raise ValueError('All characters in timecode seconds string must be digits.')
                secs = float(secs)
                if secs < 0.0:
                    raise ValueError('Timecode seconds value must be positive.')
                self.frame_num = int(secs * self.framerate)
            else:
                tc_val = timecode.split(':')
                if not (len(tc_val) == 3 and tc_val[0].isdigit() and tc_val[1].isdigit()
                        and tc_val[2].replace('.', '').isdigit()):
                    raise TypeError('Improperly formatted timecode string.')
                hrs, mins = int(tc_val[0]), int(tc_val[1])
                secs = float(tc_val[2]) if '.' in tc_val[2] else int(tc_val[2])
                if not (hrs >= 0 and mins >= 0 and secs >= 0 and mins < 60
                        and secs < 60):
                    raise ValueError('Invalid timecode range.')
                secs += (((hrs * 60.0) + mins) * 60.0)
                self.frame_num = int(secs * self.framerate)
        else:
            raise TypeError('Timecode format unrecognized.')

    #def get_frame_num(self):
    #    return self.frame_num

    def get_seconds(self):
        return float(self.frame_num) / self.framerate


