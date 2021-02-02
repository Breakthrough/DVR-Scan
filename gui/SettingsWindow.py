from PyQt5.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QLineEdit, QHBoxLayout, QWidget, QListWidget, QFileDialog, QLabel, QCheckBox, QComboBox
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from gui.args import Args
from gui.ScanningWindow import ScanningWindow
from gui.RoiSelector import RoiSelector

# todo connect timecode checkbox/downscale input to args


class SettingsWindow(QMainWindow):
    def add_clicked(self):
        videos, _ = QFileDialog.getOpenFileNames(
            self, "Select videos:", "", "Videos (*.mp4 *.avi *.mkv *.mov)")
        if videos:
            self.args.add_videos(videos)
            self.update_video_list()

    def scan_finished(self):
        self.scan_button.setEnabled(True)

    def scan_clicked(self):
        skip_input = self.skip_input.text()
        if(len(skip_input) > 0):
            self.args.set_frame_skip(skip_input)
        self.args.set_treshold(self.treshold_input.text())
        self.args.draw_timecode = self.timecode_checkbox.checkState()
        self.args.set_downscale_factor(self.downscale_input.text())
        self.args.roi = self.roi_image.get_roi()
        self.args.fourcc_str = self.codec_select.currentText()
        self.args.set_before_frames(self.frames_before_input.text())
        self.args.set_after_frames(self.frames_after_input.text())
        self.args.set_min_len(self.min_len_input.text())
        self.scan_window = ScanningWindow(self.args, self)
        self.scan_window.show()
        self.scan_button.setEnabled(False)

    def update_video_list(self):
        self.video_list.clear()
        video_paths = [input_file.name for input_file in self.args.input]
        for video_path in video_paths:
            self.video_list.addItem(video_path)
        if(len(video_paths) > 0):
            self.roi_image.set_image(video_paths[0])
        if len(video_paths) > 0:
            self.scan_button.setEnabled(True)

    def target_file_clicked(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Select target file.", "", "Video Files (*.avi)", options=options)
        if file_name:
            self.args.set_target(file_name)
            self.target_label.setText(file_name)

    def video_selected(self):
        selected_video = self.video_list.selectedItems()[
            0].text()
        self.roi_image.set_image(selected_video)

    def remove_clicked(self):
        if(len(self.video_list.selectedItems()) > 0):
            del_index = self.video_list.row(self.video_list.selectedItems()[0])
            self.video_list.takeItem(del_index)
            self.args.remove_video(del_index)
            # check if videolist is empty and disable scan button
            if(len(self.args.input) == 0):
                self.scan_button.setEnabled(False)
            if(len(self.video_list.selectedItems()) > 0):
                new_item = self.video_list.item(
                    self.video_list.currentRow()).text()
                self.roi_image.set_image(new_item)

    def __init__(self):
        super().__init__()
        self.setGeometry(50, 50, 1200, 800)
        self.setWindowTitle("DVR Scan")
        # setup scan arguments model
        self.args = Args()

        # initialize widgets
        self.scan_window = None
        self.central_widget = QWidget()
        self.video_list = QListWidget(self.central_widget)
        self.video_list.resize(640, 480)

        self.add_button = QPushButton('Select videos', self.central_widget)
        self.remove_button = QPushButton('Remove')
        self.target_label = QLabel('No target file selected.')
        self.target_button = QPushButton('Select target')

        # Skip widgets
        self.skip_label = QLabel("Skip frames: ")
        self.skip_input = QLineEdit()
        self.skip_input.setValidator(QIntValidator())
        self.skip_input.setFixedWidth(40)

        # Treshold widgets
        self.treshold_label = QLabel("Threshold:")
        self.treshold_input = QLineEdit()
        self.treshold_input.setFixedWidth(40)
        self.treshold_input.setText('0.15')
        self.treshold_input.setValidator(QDoubleValidator())

        # Downscale widgets
        self.downscale_label = QLabel("Downscale factor:")
        self.downscale_input = QLineEdit()
        self.downscale_input.setFixedWidth(40)
        self.downscale_input.setText('1')
        self.downscale_input.setValidator(QIntValidator(1, 10))

        # Timecode widgets
        self.timecode_label = QLabel("Timecode:")
        self.timecode_checkbox = QCheckBox()

        # Codec widgets
        self.codec_label = QLabel("Codec:")
        self.codec_select = QComboBox()
        self.codec_select.addItem("XVID")
        self.codec_select.addItem("MP4V")
        self.codec_select.addItem("MP42")
        self.codec_select.addItem("H264")

        # Frames before & after event widgets
        self.frames_before_label = QLabel("Frames before:")
        self.frames_before_input = QLineEdit()
        self.frames_before_input.setFixedWidth(40)
        self.frames_before_input.setValidator(QIntValidator())

        self.frames_after_label = QLabel("Frames after:")
        self.frames_after_input = QLineEdit()
        self.frames_after_input.setFixedWidth(40)
        self.frames_after_input.setValidator(QIntValidator())

        # Minimum event length widgets
        self.min_len_label = QLabel("Minimum event length:")
        self.min_len_input = QLineEdit()
        self.min_len_input.setValidator(QIntValidator())
        self.min_len_input.setText("2")
        self.min_len_input.setFixedWidth(40)
        # Scan button
        self.scan_button = QPushButton('Start scan', self.central_widget)
        self.scan_button.setEnabled(False)
        self.roi_image = RoiSelector()

        # setup event handling
        self.video_list.itemClicked.connect(self.video_selected)
        self.add_button.clicked.connect(self.add_clicked)
        self.remove_button.clicked.connect(self.remove_clicked)
        self.target_button.clicked.connect(self.target_file_clicked)
        self.scan_button.clicked.connect(self.scan_clicked)

        # layouting
        self.layout = QHBoxLayout(self.central_widget)
        self.settings_layout = QVBoxLayout()
        self.list_actions_layout = QHBoxLayout()
        self.list_actions_layout.addWidget(self.add_button)
        self.list_actions_layout.addWidget(self.remove_button)
        self.target_layout = QVBoxLayout()
        self.target_layout.addWidget(self.target_label)
        self.target_layout.addWidget(self.target_button)

        # Option layouting
        self.option_1_layout = QHBoxLayout()
        self.option_1_layout.addWidget(self.skip_label)
        self.option_1_layout.addWidget(self.skip_input)
        self.option_1_layout.addWidget(self.treshold_label)
        self.option_1_layout.addWidget(self.treshold_input)
        self.option_1_layout.addWidget(self.downscale_label)
        self.option_1_layout.addWidget(self.downscale_input)
        self.option_1_layout.addWidget(self.timecode_label)
        self.option_1_layout.addWidget(self.timecode_checkbox)

        self.option_2_layout = QHBoxLayout()
        self.option_2_layout.addWidget(self.codec_label)
        self.option_2_layout.addWidget(self.codec_select)
        self.option_2_layout.addWidget(self.frames_before_label)
        self.option_2_layout.addWidget(self.frames_before_input)
        self.option_2_layout.addWidget(self.frames_after_label)
        self.option_2_layout.addWidget(self.frames_after_input)
        self.option_2_layout.addWidget(self.min_len_label)
        self.option_2_layout.addWidget(self.min_len_input)

        # Layout for the roi input's and manual ROI selection widget
        self.roi_layout = QVBoxLayout()
        self.roi_layout.addWidget(self.roi_image)

        self.layout.addLayout(self.settings_layout, 1)
        self.layout.addLayout(self.roi_layout, 1)
        self.settings_layout.addWidget(self.video_list)
        self.settings_layout.addLayout(self.list_actions_layout)
        self.settings_layout.addLayout(self.target_layout)
        self.settings_layout.addLayout(self.option_1_layout)
        self.settings_layout.addLayout(self.option_2_layout)
        self.settings_layout.addWidget(self.scan_button)
        self.setCentralWidget(self.central_widget)
