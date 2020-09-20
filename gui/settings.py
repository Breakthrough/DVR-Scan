from PyQt5.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QListWidget, QFileDialog, QLabel
from gui.args import Args
from gui.scanning import ScanningWindow


class SettingsWindow(QMainWindow):
    def addClicked(self):
        videos, _ = QFileDialog.getOpenFileNames(
            self, "Select videos:", "", "Videos (*.mp4 *.avi *.mkv *.mov)")
        if videos:
            self.args.addVideos(videos)
            self.updateVideoList()

    def scanFinished(self):
        print('scan finished')

    def scanClicked(self):
        self.scanWindow = ScanningWindow(self.args, self)
        self.scanWindow.show()

    def updateVideoList(self):
        self.videoList.clear()
        video_paths = [input_file.name for input_file in self.args.input]
        for video_path in video_paths:
            self.videoList.addItem(video_path)
        if len(video_paths) > 0:
            self.scanButton.setEnabled(True)

    def targetFileClicked(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Select target file.", "", "Video Files (*.avi)", options=options)
        if fileName:
            self.args.setTarget(fileName)
            self.targetLabel.setText(fileName)

    def __init__(self):
        super().__init__()
        self.setGeometry(50, 50, 500, 500)
        self.setWindowTitle("DVR Scan")
        # setup scan arguments model
        self.args = Args()

        # initialize widgets
        self.scanWindow = None
        self.centralWidget = QWidget()
        self.videoList = QListWidget(self.centralWidget)
        self.videoList.setGeometry(20, 20, 400, 400)

        self.addButton = QPushButton('Select videos', self.centralWidget)

        self.targetLabel = QLabel('No target file selected.')
        self.targetButton = QPushButton('Select target')
        self.scanButton = QPushButton('Start scan', self.centralWidget)
        self.scanButton.setEnabled(False)

        # setup event handling
        self.addButton.clicked.connect(self.addClicked)
        self.scanButton.clicked.connect(self.scanClicked)
        self.targetButton.clicked.connect(self.targetFileClicked)
        # layouting
        self.layout = QVBoxLayout(self.centralWidget)
        self.listActionsLayout = QHBoxLayout()
        self.listActionsLayout.addWidget(self.addButton)
        self.targetLayout = QVBoxLayout()
        self.targetLayout.addWidget(self.targetLabel)
        self.targetLayout.addWidget(self.targetButton)

        self.layout.addWidget(self.videoList)
        self.layout.addLayout(self.listActionsLayout)
        self.layout.addLayout(self.targetLayout)
        self.layout.addWidget(self.scanButton)
        self.setCentralWidget(self.centralWidget)
