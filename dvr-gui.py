#from dvr_scan.scanner import ScanContext
#from gui.args import Args

# settings = Args(
#    input=['/Users/andyverstraeten/Downloads/CH01_2020-08-27_095946_2020-08-27_112859_ID34.MP4'])
#sctx = ScanContext(settings)
# if sctx.initialized is True:
#    sctx.scan_motion()

from PyQt5.QtWidgets import QApplication, QMainWindow
from gui.SettingsWindow import SettingsWindow

app = QApplication([])
win = SettingsWindow()
win.show()
app.exit(app.exec_())
