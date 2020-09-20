from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QMainWindow, QProgressBar, QLabel, QPushButton, QVBoxLayout, QWidget
from dvr_scan.scanner import ScanContext


class ScanThread(QThread):
    def __init__(self, args, scanWindow):
        super().__init__()
        self.args = args
        self.sctx = None
        self.scanWindow = scanWindow
        self.updateTimer = QTimer()
        self.updateTimer.setInterval(int(100))
        self.updateTimer.start()
        self.updateTimer.timeout.connect(self.updateProgress)

    def run(self):
        self.sctx = ScanContext(self.args)
        self.scanWindow.progress.setMaximum(self.sctx.frames_total)
        self.sctx.scan_motion()

    def updateProgress(self):
        if self.sctx:
            self.scanWindow.progress.setValue(self.sctx.frames_read)
            total = self.sctx.frames_total
            read = self.sctx.frames_read
            percentage = read/total
            statusText = "Processed: {:.2%} - {}/{} frames.".format(
                percentage, read, total)
            self.scanWindow.statusLabel.setText(statusText)

    def stop(self):
        self.sctx.running = False


class ScanningWindow(QMainWindow):
    def finished(self):
        self.settingsWindow.scanFinished()
        self.close()

    def cancelClicked(self):
        self.scanThread.stop()
        self.close()

    def __init__(self, args, settingsWindow):
        super().__init__()
        self.args = args
        self.setWindowTitle('Executing scan')
        self.setGeometry(50, 50, 400, 200)

        # initialize widgets
        self.centralWidget = QWidget()
        self.settingsWindow = settingsWindow
        self.statusLabel = QLabel()
        self.cancelButton = QPushButton('Stop scan')
        self.cancelButton.clicked.connect(self.cancelClicked)
        self.cancelButton.setGeometry(20, 175, 50, 20)
        self.progress = QProgressBar(self)
        self.progress.setGeometry(50, 20, 300, 25)

        # seperate thread for scanning keeps gui from freezing
        self.scanThread = ScanThread(self.args, self)
        self.scanThread.finished.connect(self.finished)
        self.scanThread.start()

        # layout
        self.mainLayout = QVBoxLayout()
        self.mainLayout.addWidget(self.progress)
        self.mainLayout.addWidget(self.statusLabel)
        self.mainLayout.addWidget(self.cancelButton)
        self.centralWidget.setLayout(self.mainLayout)
        self.setCentralWidget(self.centralWidget)
