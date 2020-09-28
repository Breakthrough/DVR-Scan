import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit
from PyQt5.QtCore import Qt
from gui.CoordInput import CoordInput
from gui.PreviewImage import PreviewImage


class RoiSelector(QWidget):
    def __init__(self, *args, **kwargs):
        super(RoiSelector, self).__init__(*args, **kwargs)

        # initializing widgets
        self.x1_input = CoordInput('X1:')
        self.y1_input = CoordInput('Y1:')
        self.x2_input = CoordInput('X2:')
        self.y2_input = CoordInput('Y2:')
        self.preview_image = PreviewImage()

        # event handling
        self.x1_input.communicate.value_changed.connect(self.update_roi)
        self.y1_input.communicate.value_changed.connect(self.update_roi)
        self.x2_input.communicate.value_changed.connect(self.update_roi)
        self.y2_input.communicate.value_changed.connect(self.update_roi)
        # initialize layouting
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)
        self.input_row = QHBoxLayout()
        self.input_row.setAlignment(Qt.AlignTop)
        self.layout.addLayout(self.input_row)
        self.input_row.addWidget(self.x1_input)
        self.input_row.addWidget(self.y1_input)
        self.input_row.addWidget(self.x2_input)
        self.input_row.addWidget(self.y2_input)
        self.layout.addWidget(self.preview_image)
        self.setLayout(self.layout)

    def update_roi(self):
        self.preview_image.update_roi(self.get_roi())

    # get called when image changes. if a valid ROI is set does nothing
    # else puts ROI values for whole image
    def normalize_input(self, width, height):
        self.x1_input.set_max(width)
        self.x2_input.set_max(width)
        self.y1_input.set_max(height)
        self.y2_input.set_max(height)
        if(self.x1_input.is_invalid()):
            self.x1_input.show_min()
        if(self.y1_input.is_invalid()):
            self.y1_input.show_min()
        if(self.x2_input.is_invalid()):
            self.x2_input.show_max()
        if(self.y2_input.is_invalid()):
            self.y2_input.show_max()
        self.preview_image.update_roi(self.get_roi())

    def set_image(self, path):
        self.preview_image.update_img(path, self.get_roi())
        height, width = self.preview_image.get_dimensions()
        self.normalize_input(width, height)

    def get_roi(self):
        return [self.x1_input.value(), self.y1_input.value(), self.x2_input.value(), self.y2_input.value()]

    # TODO get_roi function + draw roi
