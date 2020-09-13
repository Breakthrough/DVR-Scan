from PyQt5.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget, QListWidget, QFileDialog
from gui.args import Args


class SettingsWindow(QMainWindow):
    def addClicked(self):
        videos, _ = QFileDialog.getOpenFileNames(
            self, "Select videos:", "", "Videos (*.mp4 *.avi *.mkv)")
        if videos:
            self.args.addVideos(videos)
            self.updateVideoList()

    def updateVideoList(self):
        self.videoList.clear()
        video_paths = [input_file.name for input_file in self.args.input]
        for video_path in video_paths:
            self.videoList.addItem(video_path)

    def __init__(self):
        super().__init__()
        self.args = Args()
        self.centralWidget = QWidget()
        self.videoList = QListWidget(self.centralWidget)
        self.videoList.setGeometry(20, 20, 200, 200)
        self.addButton = QPushButton('Select videos', self.centralWidget)
        self.addButton.clicked.connect(self.addClicked)
        self.layout = QVBoxLayout(self.centralWidget)
        self.layout.addWidget(self.addButton)
        self.layout.addWidget(self.videoList)
        self.setCentralWidget(self.centralWidget)
