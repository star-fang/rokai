from pynput.mouse import Listener, Button
from PyQt5.QtCore import QObject, pyqtSignal
from threading import Lock

class Tracker(QObject):
    mouseClicked = pyqtSignal(int,int,int)
    setCountDown = pyqtSignal(int)
    setBoundary = pyqtSignal(tuple)
    def __init__(self, clickCountDown = 0, parent = None):
        QObject.__init__(self, parent)
        self.bbox = None
        self.clickCountDown = clickCountDown
        self.setCountDown.connect( self.setClickCountDown )
        self.setBoundary.connect( self.setBbox )
        listener = Listener(on_click = self.on_click)
        listener.start()
        self.mutex = Lock()

    def setClickCountDown( self, n ):
        with self.mutex:
            self.clickCountDown = n

    def setBbox( self, bbox ):
        self.bbox = bbox

    def on_click(self, x,y, button, pressed):
        if self.bbox is None:
            return
        x1, y1, x2, y2 = self.bbox
        if x > x1 and x < x2 and y > y1 and y < y2:
            with self.mutex:
                if not pressed and button == Button.left:
                    self.clickCountDown -= 1
                    self.mouseClicked.emit(x,y,self.clickCountDown)

    
        
    
