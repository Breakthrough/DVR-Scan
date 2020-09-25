import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel
from PyQt5.QtGui import QIntValidator,   QPixmap, QImage
from PyQt5.QtCore import Qt


class RoiSelector(QWidget):
    def __init__(self, *args, **kwargs):
        super(RoiSelector, self).__init__(*args, **kwargs)

        # initializing widgets
        self.x1_label = QLabel("X1:")
        self.x1_input = QLineEdit()
        self.x1_input.setValidator(QIntValidator())
        self.y1_label = QLabel("Y1:")
        self.y1_input = QLineEdit()
        self.y1_input.setValidator(QIntValidator())
        self.x2_label = QLabel("X2:")
        self.x2_input = QLineEdit()
        self.x2_input.setValidator(QIntValidator())
        self.y2_label = QLabel("Y2:")
        self.y2_input = QLineEdit()
        self.y2_input.setValidator(QIntValidator())
        self.preview_image = QLabel()
        # initialize layouting
        self.layout = QVBoxLayout()
        self.input_row = QHBoxLayout()

        self.layout.addLayout(self.input_row)
        self.input_row.addWidget(self.x1_label)
        self.input_row.addWidget(self.x1_input)
        self.input_row.addWidget(self.y1_label)
        self.input_row.addWidget(self.y1_input)
        self.input_row.addWidget(self.x2_label)
        self.input_row.addWidget(self.x2_input)
        self.input_row.addWidget(self.y2_label)
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
            if(not self.roi_is_valid(h, w)):
                self.x1_input.setText('0')
                self.y1_input.setText('0')
                self.x2_input.setText(str(w))
                self.y2_input.setText(str(h))

    def roi_is_valid(self, height, width):
        if(not self.roi_is_set()):
            return False
        set_height = int(self.x2_input.text())
        set_width = int(self.x2_input.text())
        if(set_height < 0 or set_height > height):
            return False
        if(set_width < 0 or set_width > width):
            return False
        return True

    def roi_is_set(self):
        if(len(self.x2_input.text()) == 0 or len(self.y2_input.text()) == 0):
            return False
        else:
            return True

    # TODO get_roi function + draw roi
