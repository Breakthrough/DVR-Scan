from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QImage
import cv2


class RoiChanged(QObject):
    changed = pyqtSignal()


class PreviewImage(QLabel):
    def __init__(self, *args, **kwargs):
        super(PreviewImage, self).__init__(*args, **kwargs)
        self.first_frame = []
        self.image = []
        self.height = 0
        self.width = 0
        self.bytesPerLine = 0
        self.setFixedWidth(640)
        self.roi = []
        self.dragging_mode = False
        self.communicate = RoiChanged()

    # this function makes sure that x1 and y1 are top left
    def order_coordinates(self, roi):
        if roi[0] < roi[2]:
            x1 = roi[0]
            x2 = roi[2]
        else:
            x1 = roi[2]
            x2 = roi[0]
        if roi[1] < roi[3]:
            y1 = roi[1]
            y2 = roi[3]
        else:
            y1 = roi[3]
            y2 = roi[1]
        return [x1, y1, x2, y2]

    def get_roi(self):
        return self.order_coordinates(self.roi)

    def mousePressEvent(self, event):
        self.dragging_mode = True
        x1 = event.localPos().x()*2
        y1 = event.localPos().y()*2
        self.roi = [int(x1), int(y1), self.roi[2], self.roi[3]]

    def mouseMoveEvent(self, event):
        if(self.dragging_mode):
            x2 = event.localPos().x()*2
            y2 = event.localPos().y()*2
            self.roi = [self.roi[0], self.roi[1], int(x2), int(y2)]
            self.image = self.draw_roi(self.first_frame, self.roi)
            self.display_rgb_image(self.image)

    def mouseReleaseEvent(self, event):
        self.dragging_mode = False
        self.communicate.changed.emit()

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
        self.roi = roi
        self.image = self.draw_roi(self.first_frame.copy(), roi)
        self.display_rgb_image(self.image)

    def update_roi(self, roi):
        self.image = self.draw_roi(self.first_frame, roi)
        self.display_rgb_image(self.image)
