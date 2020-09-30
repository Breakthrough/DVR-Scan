from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QMainWindow, QProgressBar, QLabel, QPushButton, QVBoxLayout, QWidget
from dvr_scan.scanner import ScanContext


class ScanThread(QThread):
    def __init__(self, args, scan_window):
        super().__init__()
        self.args = args
        self.sctx = None
        self.scan_window = scan_window
        self.update_timer = QTimer()
        self.update_timer.setInterval(int(100))
        self.update_timer.start()
        self.update_timer.timeout.connect(self.update_progress)

    def run(self):
        self.sctx = ScanContext(self.args)
        self.scan_window.progress.setMaximum(self.sctx.frames_total)
        self.sctx.scan_motion()

    def update_progress(self):
        if self.sctx:
            self.scan_window.progress.setValue(self.sctx.frames_read)
            total = self.sctx.frames_total
            read = self.sctx.frames_read
            percentage = read/total
            status_text = "Processed: {:.2%} - {}/{} frames.".format(
                percentage, read, total)
            self.scan_window.status_label.setText(status_text)

    def stop(self):
        self.sctx.running = False


class ScanningWindow(QMainWindow):
    def finished(self):
        self.settings_window.scan_finished()
        self.close()

    def cancel_clicked(self):
        self.scan_thread.stop()
        self.close()

    def __init__(self, args, settingsWindow):
        super().__init__()
        self.args = args
        self.setWindowTitle('Executing scan')
        self.setGeometry(50, 50, 400, 200)

        # initialize widgets
        self.central_widget = QWidget()
        self.settings_window = settingsWindow
        self.status_label = QLabel()
        self.cancel_button = QPushButton('Stop scan')
        self.cancel_button.clicked.connect(self.cancel_clicked)
        self.cancel_button.setGeometry(20, 175, 50, 20)
        self.progress = QProgressBar(self)
        self.progress.setGeometry(50, 20, 300, 25)

        # seperate thread for scanning keeps gui from freezing
        self.scan_thread = ScanThread(self.args, self)
        self.scan_thread.finished.connect(self.finished)
        self.scan_thread.start()

        # layout
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.progress)
        self.main_layout.addWidget(self.status_label)
        self.main_layout.addWidget(self.cancel_button)
        self.central_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.central_widget)
