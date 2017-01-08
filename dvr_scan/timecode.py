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
    """ Object for frame-based timecodes, using the video framerate
    to compute back and forth between frame number and second/timecode formats.

    The passed argument is declared valid if it meets one of three valid forms:
      1) Standard timecode HH:MM:SS[.nnn]:
            in string form 'HH:MM:SS' or 'HH:MM:SS.nnn', or
            in list/tuple form [HH, MM, SS] or [HH, MM, SS.nnn]
      2) Number of seconds S[.SSS], where S >= 0.0:
            in string form 'Ss' or 'S.SSSs' (e.g. '5s', '1.234s'), or
            in integer or floating point form S or S.SSS
      3) Exact number of frames N, where N >= 0:
            in either integer or string form N or 'N'

    Raises:
        TypeError, ValueError
    """

    def __init__(self, fps, timecode):
        if not isinstance(fps, (int, float)):
            raise TypeError('Framerate must be of type int/float.')
        self.framerate = float(fps)
        self.frame_num = -1
        if isinstance(timecode, int):
            if timecode < 0:
                raise ValueError('Timecode frame number must be positive.')
            self.frame_num = timecode
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
            elif timecode.isdigit():
                timecode = int(timecode)
                if timecode < 0:
                    raise ValueError('Timecode frame number must be positive.')
                self.frame_num = timecode
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

    def get_seconds(self):
        """ Get the frame's position in number of seconds.

        Returns:
            A float of the current time/position in seconds.
        """
        return float(self.frame_num) / self.framerate

    def get_timecode(self, precision = 3, use_rounding = True):
        """ Get a formatted timecode string of the form HH:MM:SS[.nnn].

        Args:
            precision:     The number of decimal places to include in the output [.nnn].
            use_rounding:  True (default) to round the output to the desired precision.

        Returns:
            A string with a formatted timecode (HH:MM:SS[.nnn]).
        """
        # Compute hours and minutes based off of seconds, and update seconds.
        secs = self.get_seconds()
        base = 60.0 * 60.0
        hrs = int(secs / base)
        secs -= (hrs * base)
        base = 60.0
        mins = int(secs / base)
        secs -= (mins * base)
        # Convert seconds into string based on required precision.
        if precision > 0:
            if use_rounding:
                secs = round(secs, precision)
            msec = format(secs, '.%df' % precision)[-precision:]
            secs = '%02d.%s' % (int(secs), msec)
        else:
            secs = '%02d' % int(round(secs, 0)) if use_rounding else '%02d' % int(secs)
        # Return hours, minutes, and seconds as a formatted timecode string.
        return '%02d:%02d:%s' % (hrs, mins, secs)


