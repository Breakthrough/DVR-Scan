from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage
import cv2


class PreviewImage(QLabel):
    def __init__(self, *args, **kwargs):
        super(PreviewImage, self).__init__(*args, **kwargs)
        self.first_frame = []
        self.image = []
        self.height = 0
        self.width = 0
        self.bytesPerLine = 0

    def get_first_frame(self, path):
        ret, firstFrame = cv2.VideoCapture(path).read()
        if ret:
            rgb_image = cv2.cvtColor(firstFrame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            self.bytesPerLine = ch * w
            self.height = h
            self.width = w
            return rgb_image

    def get_dimensions(self):
        return self.height, self.width

    def draw_roi(self, img, roi):
        img_roi = cv2.rectangle(img.copy(), (roi[0], roi[1]),
                                (roi[2], roi[3]), (255, 0, 0), 3)
        return img_roi

    def display_rgb_image(self, rgb_image):
        convert_to_QtFormat = QImage(
            rgb_image.data, self.width, self.height, self.bytesPerLine, QImage.Format_RGB888)
        ready_image = convert_to_QtFormat.scaled(
            640, 480, Qt.KeepAspectRatio)
        self.setPixmap(
            QPixmap.fromImage(ready_image))

    def update_img(self, path, roi):
        self.first_frame = self.get_first_frame(path)
        self.image = self.draw_roi(self.first_frame.copy(), roi)
        self.display_rgb_image(self.image)

    def update_roi(self, roi):
        self.image = self.draw_roi(self.first_frame, roi)
        self.display_rgb_image(self.image)
