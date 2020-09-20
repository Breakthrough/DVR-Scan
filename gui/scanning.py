from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QMainWindow, QProgressBar
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


class ScanningWindow(QMainWindow):
    def finished(self):
        self.settingsWindow.scanFinished()
        self.close()

    def __init__(self, args, settingsWindow):
        super().__init__()
        self.args = args
        self.settingsWindow = settingsWindow
        self.progress = QProgressBar(self)
        self.progress.setGeometry(0, 0, 300, 25)
        self.scanThread = ScanThread(self.args, self)
        self.scanThread.finished.connect(self.finished)
        self.scanThread.start()
