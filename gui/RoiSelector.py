import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel
from PyQt5.QtGui import QIntValidator,   QPixmap, QImage
from PyQt5.QtCore import Qt
from gui.CoordInput import CoordInput


class RoiSelector(QWidget):
    def __init__(self, *args, **kwargs):
        super(RoiSelector, self).__init__(*args, **kwargs)

        # initializing widgets
        self.x1_input = CoordInput('X1:')
        self.y1_input = CoordInput('Y1:')
        self.x2_input = CoordInput('X2:')
        self.y2_input = CoordInput('Y2:')

        self.preview_image = QLabel()

        # initialize layouting
        self.layout = QVBoxLayout()
        self.input_row = QHBoxLayout()

        self.layout.addLayout(self.input_row)
        self.input_row.addWidget(self.x1_input)
        self.input_row.addWidget(self.y1_input)
        self.input_row.addWidget(self.x2_input)
        self.input_row.addWidget(self.y2_input)
        self.layout.addWidget(self.preview_image)
        self.setLayout(self.layout)

    def set_image(self, path):
        ret, firstFrame = cv2.VideoCapture(path).read()
        if ret:
            rgb_image = cv2.cvtColor(firstFrame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytesPerLine = ch * w
            convert_to_QtFormat = QImage(
                rgb_image.data, w, h, bytesPerLine, QImage.Format_RGB888)
            ready_image = convert_to_QtFormat.scaled(
                640, 480, Qt.KeepAspectRatio)
            self.preview_image.setPixmap(
                QPixmap.fromImage(ready_image))
            self.x1_input.set_max(w)
            self.x2_input.set_max(w)
            self.y1_input.set_max(h)
            self.y2_input.set_max(h)
            if(self.x1_input.is_invalid()):
                self.x1_input.show_min()
            if(self.y1_input.is_invalid()):
                self.y1_input.show_min()
            if(self.x2_input.is_invalid()):
                self.x2_input.show_max()
            if(self.y2_input.is_invalid()):
                self.y2_input.show_max()

    def get_roi(self):
        return [self.x1_input.value(), self.y1_input.value(), self.x2_input.value(), self.y2_input.value()]
    # TODO get_roi function + draw roi
