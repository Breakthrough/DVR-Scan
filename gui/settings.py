from PyQt5.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QLineEdit, QHBoxLayout, QWidget, QListWidget, QFileDialog, QLabel
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from gui.args import Args
from gui.scanning import ScanningWindow
from gui.RoiSelector import RoiSelector


class SettingsWindow(QMainWindow):
    def addClicked(self):
        videos, _ = QFileDialog.getOpenFileNames(
            self, "Select videos:", "", "Videos (*.mp4 *.avi *.mkv *.mov)")
        if videos:
            self.args.addVideos(videos)
            self.updateVideoList()

    def scanFinished(self):
        self.scanButton.setEnabled(True)

    def scanClicked(self):
        skipInput = self.skipInput.text()
        if(len(skipInput) > 0):
            self.args.setFrameSkip(skipInput)
        self.args.setTreshold(self.tresholdInput.text())
        self.args.roi = self.roiImage.get_roi()
        self.scanWindow = ScanningWindow(self.args, self)
        self.scanWindow.show()
        self.scanButton.setEnabled(False)

    def updateVideoList(self):
        self.videoList.clear()
        video_paths = [input_file.name for input_file in self.args.input]
        for video_path in video_paths:
            self.videoList.addItem(video_path)
        if(len(video_paths) > 0):
            self.roiImage.set_image(video_paths[0])
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

    def videoSelected(self):
        selectedVideo = self.videoList.selectedItems()[
            0].text()
        self.roiImage.set_image(selectedVideo)

    def __init__(self):
        super().__init__()
        self.setGeometry(50, 50, 1200, 800)
        self.setWindowTitle("DVR Scan")
        # setup scan arguments model
        self.args = Args()

        # initialize widgets
        self.scanWindow = None
        self.centralWidget = QWidget()
        self.videoList = QListWidget(self.centralWidget)
        self.videoList.resize(640, 480)

        self.addButton = QPushButton('Select videos', self.centralWidget)

        self.targetLabel = QLabel('No target file selected.')
        self.targetButton = QPushButton('Select target')
        self.skipLabel = QLabel("Skip frames: ")
        self.skipInput = QLineEdit()
        self.skipInput.setValidator(QIntValidator())
        self.tresholdLabel = QLabel("Threshold:")
        self.tresholdInput = QLineEdit()
        self.tresholdInput.setText('0.15')
        self.tresholdInput.setValidator(QDoubleValidator())
        self.scanButton = QPushButton('Start scan', self.centralWidget)
        self.scanButton.setEnabled(False)
        self.roiImage = RoiSelector()

        # setup event handling
        self.videoList.itemClicked.connect(self.videoSelected)
        self.addButton.clicked.connect(self.addClicked)
        self.targetButton.clicked.connect(self.targetFileClicked)
        self.scanButton.clicked.connect(self.scanClicked)

        # layouting
        self.layout = QHBoxLayout(self.centralWidget)
        self.settingsLayout = QVBoxLayout()
        self.listActionsLayout = QHBoxLayout()
        self.listActionsLayout.addWidget(self.addButton)
        self.targetLayout = QVBoxLayout()
        self.targetLayout.addWidget(self.targetLabel)
        self.targetLayout.addWidget(self.targetButton)
        self.skipLayout = QVBoxLayout()
        self.skipLayout.addWidget(self.skipLabel)
        self.tresholdLayout = QVBoxLayout()
        self.tresholdLayout.addWidget(self.tresholdLabel)
        self.tresholdLayout.addWidget(self.tresholdInput)
        self.skipLayout.addWidget(self.skipInput)
        self.roiLayout = QVBoxLayout()
        self.roiLayout.addWidget(self.roiImage)
        self.layout.addLayout(self.settingsLayout, 1)
        self.layout.addLayout(self.roiLayout, 1)
        self.settingsLayout.addWidget(self.videoList)
        self.settingsLayout.addLayout(self.listActionsLayout)
        self.settingsLayout.addLayout(self.targetLayout)
        self.settingsLayout.addLayout(self.skipLayout)
        self.settingsLayout.addLayout(self.tresholdLayout)
        self.settingsLayout.addWidget(self.scanButton)
        self.setCentralWidget(self.centralWidget)
