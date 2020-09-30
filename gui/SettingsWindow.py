from PyQt5.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QLineEdit, QHBoxLayout, QWidget, QListWidget, QFileDialog, QLabel
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from gui.args import Args
from gui.ScanningWindow import ScanningWindow
from gui.RoiSelector import RoiSelector


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
        self.args.roi = self.roi_image.get_roi()
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

        self.target_label = QLabel('No target file selected.')
        self.target_button = QPushButton('Select target')
        self.skip_label = QLabel("Skip frames: ")
        self.skip_input = QLineEdit()
        self.skip_input.setValidator(QIntValidator())
        self.treshold_label = QLabel("Threshold:")
        self.treshold_input = QLineEdit()
        self.treshold_input.setText('0.15')
        self.treshold_input.setValidator(QDoubleValidator())
        self.scan_button = QPushButton('Start scan', self.central_widget)
        self.scan_button.setEnabled(False)
        self.roi_image = RoiSelector()

        # setup event handling
        self.video_list.itemClicked.connect(self.video_selected)
        self.add_button.clicked.connect(self.add_clicked)
        self.target_button.clicked.connect(self.target_file_clicked)
        self.scan_button.clicked.connect(self.scan_clicked)

        # layouting
        self.layout = QHBoxLayout(self.central_widget)
        self.settings_layout = QVBoxLayout()
        self.list_actions_layout = QHBoxLayout()
        self.list_actions_layout.addWidget(self.add_button)
        self.target_layout = QVBoxLayout()
        self.target_layout.addWidget(self.target_label)
        self.target_layout.addWidget(self.target_button)
        self.skip_layout = QVBoxLayout()
        self.skip_layout.addWidget(self.skip_label)
        self.treshold_layout = QVBoxLayout()
        self.treshold_layout.addWidget(self.treshold_label)
        self.treshold_layout.addWidget(self.treshold_input)
        self.skip_layout.addWidget(self.skip_input)
        self.roi_layout = QVBoxLayout()
        self.roi_layout.addWidget(self.roi_image)
        self.layout.addLayout(self.settings_layout, 1)
        self.layout.addLayout(self.roi_layout, 1)
        self.settings_layout.addWidget(self.video_list)
        self.settings_layout.addLayout(self.list_actions_layout)
        self.settings_layout.addLayout(self.target_layout)
        self.settings_layout.addLayout(self.skip_layout)
        self.settings_layout.addLayout(self.treshold_layout)
        self.settings_layout.addWidget(self.scan_button)
        self.setCentralWidget(self.central_widget)
