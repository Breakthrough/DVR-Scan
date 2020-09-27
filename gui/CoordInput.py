from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import pyqtSignal, QObject


class CoordInputCommunicate(QObject):
    value_changed = pyqtSignal()


class CoordInput(QWidget):
    def __init__(self, label_name, max=None, min=0, *args, **kwargs):
        super(CoordInput, self).__init__(*args, **kwargs)
        self._max = max
        self._min = min

        # initialize widgets
        self.label = QLabel(label_name)
        self.input = QLineEdit()

        # event handling
        self.input.textChanged.connect(self.make_valid)
        self.input.editingFinished.connect(self.emit_value_changed)

        self.communicate = CoordInputCommunicate()
        self.input.setValidator(QIntValidator())

        # layouting
        self.layout = QHBoxLayout()
        self.layout.setSpacing(0)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.input)
        self.setLayout(self.layout)

    def text(self):
        return self.input.text()

    def setText(self, text):
        return self.input.setText(str(text))

    def set_max(self, max):
        self._max = max

    def set_min(self, min):
        self._min = min

    def show_max(self):
        try:
            self.input.setText(str(self._max))
        except:
            self.input.setText("")

    def show_min(self):
        try:
            self.input.setText(str(self._min))
        except:
            self.input.setText("")

    def is_invalid(self):
        if(len(self.input.text()) == 0):
            return True
        value = int(self.input.text())
        if(value > self._max):
            print('too large')
            return True
        if(value < self._min):
            print('too small')
            return True
        return False

    def make_valid(self):
        try:
            value = int(self.input.text())
            if(value < self._min):
                self.input.setText(str(self._min))
            if(value > self._max):
                self.input.setText(str(self._max))
        except:
            if(self.input.text() == "-"):
                self.input.setText(str(self._min))

    def value(self):
        try:
            return int(self.input.text())
        except:
            return 0

    def emit_value_changed(self):
        self.communicate.value_changed.emit()
