from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QGridLayout, QMainWindow, QWidget

class MiniMap(QMainWindow):

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)

        widget = QWidget(self)
        layout = QGridLayout(widget)
        
        self.setCentralWidget(widget)
        self.overlay = Overlay(self.centralWidget())

        self.hide()

    def resizeEvent(self, event):
        self.overlay.resize(event.size())
        #event.accpet()


class Overlay(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self,parent)
        palette = QPalette(self.palette())
        palette.setColor(palette.Background, Qt.transparent)
        self.setPalette(palette)


