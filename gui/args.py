

class Args:
    def __init__(self, input=[], output=None, scan_only_mode=False, fourcc_str='xvid', threshold=1,
                 kernel_size=-1, min_event_len=2, time_post_event=2.0, time_pre_event=1.5,
                 quiet_mode=False, start_time=None, duration=None, end_time=None, downscale_factor=1,
                 frame_skip=4, draw_timecode=False, roi=[9, 240, 712, 456]):
        self.input = [open(input_file, 'r') for input_file in input]
        self.output = output
        self.scan_only_mode = scan_only_mode
        self.fourcc_str = fourcc_str
        self.threshold = threshold
        self.kernel_size = kernel_size
        self.min_event_len = min_event_len
        self.time_post_event = time_post_event
        self.time_pre_event = time_pre_event
        self.quiet_mode = quiet_mode
        self.start_time = start_time
        self.duration = duration
        self.end_time = end_time
        self.downscale_factor = downscale_factor
        self.frame_skip = frame_skip
        self.draw_timecode = draw_timecode
        self.roi = roi

    def add_videos(self, videos):
        videoPaths = set([input_file.name for input_file in self.input])
        for video in videos:
            if video not in videoPaths:
                self.input.append(open(video, 'r'))

    def remove_video(self, index):
        self.input.pop(index)

    def set_target(self, path):
        if path:
            self.output = open(path, 'w')

    def set_frame_skip(self, frames):
        if(len(frames) > 0):
            self.frame_skip = int(frames)

    def set_before_frames(self, frames):
        if(len(frames) > 0):
            self.time_pre_event = int(frames)

    def set_after_frames(self, frames):
        if(len(frames) > 0):
            self.time_post_event = int(frames)

    def set_downscale_factor(self, downscale_factor):
        if(len(downscale_factor) > 0):
            self.downscale_factor = float(downscale_factor)

    def set_min_len(self, min_len):
        try:
            self.min_event_len = int(min_len)
        except:
            self.min_event_len = 2

    def set_treshold(self, treshold):
        if(len(treshold) > 0):
            self.treshold = float(treshold)
        else:
            self.treshold = 0.15
