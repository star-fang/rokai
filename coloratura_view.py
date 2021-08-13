from multiprocessing import Queue
from PyQt5.QtWidgets import QProgressBar, QSlider, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import QObject, QRunnable, Qt, pyqtBoundSignal, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from pyautogui import run
from coloratura import Coloratura, ColoraturaProcessRunner
from matplotlib import pyplot as plt # thread - unsafe
from log import make_q_handled_logger

class ViewSignals(QObject):
    #view-> amu
    changeSatatusMessage = pyqtSignal(str)
    addRunner = pyqtSignal(QRunnable)

class ColoraturaView(QWidget):
    Button_LOCATION = 2
    Button_CRACK = 3
    Button_FIND = 4
    WORKFLOW_LEVELS = ['상태감지', '마우스 동작', '루비찾기', '인증풀기', '반복']
    def __init__(self, loggingQueue:Queue, coloratura: Coloratura, parent=None):
        QWidget.__init__(self, parent)
        self.signals = ViewSignals()
        self.coloratura = coloratura
        self.initUi()
        self.connectColoraturaSignals()
        self.loggingQueue = loggingQueue
        self.logger = make_q_handled_logger(loggingQueue, 'coloratura_view')

    def connectColoraturaSignals( self ):
        self.coloratura.changeTemplate.connect( lambda mat:self.setTemplateImage(mat) )
        self.coloratura.changeTmRatio.connect( lambda v:self.setRatioVal(v) )
        self.coloratura.changeTmRotate.connect( lambda v:self.setAngleVal(v) )
        self.coloratura.changeState.connect( lambda s:self.onStateChanged(s))
        self.coloratura.plotPlt.connect( self.histShow )

    def histShow( self, mat ):
        plt.hist( mat.ravel(), 256, [0,256])
        plt.show()

    def initUi(self):
        self.templateView = QLabel()
        self.tm_ratioBar = QProgressBar()
        self.tm_ratioBar.setTextVisible(False)
        self.tm_ratioBar.setMinimum(0)
        self.tm_ratioBar.setMaximum(100)
        self.tm_angleBar = QProgressBar()
        self.tm_angleBar.setTextVisible(False)
        self.tm_angleBar.setMinimum(0)
        self.tm_angleBar.setMaximum(360)

        layout = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget( self.templateView)
        vbox_rr = QVBoxLayout()
        hbox_ra = QHBoxLayout()
        hbox_ro = QHBoxLayout()
        hbox_ra.addWidget(self.tm_ratioBar)
        hbox_ro.addWidget(self.tm_angleBar)
        vbox_rr.addLayout(hbox_ra)
        vbox_rr.addLayout(hbox_ro)
        hbox.addLayout(vbox_rr)
        layout.addLayout( hbox )

        hbox_flow = QHBoxLayout()
        self.flow_slider = QSlider(Qt.Orientation.Horizontal)
        self.flow_slider.setMinimum(1)
        self.flow_slider.setMaximum(len(self.WORKFLOW_LEVELS))
        self.flow_slider.setValue(1)
        self.flow_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.flow_slider.setTickInterval(1)
        self.flow_slider.valueChanged.connect(self.sliderLevelChanged)
        self.flow_btn = QPushButton('RUN')
        self.flow_btn.setFixedHeight(30)
        self.flow_btn.clicked.connect( lambda: self.onFlowButtonClicked( self.flow_slider.value() ) )
        hbox_flow.addWidget(self.flow_slider)
        hbox_flow.addWidget(self.flow_btn)
        layout.addLayout( hbox_flow )
        self.setLayout(layout)
    
    def sliderLevelChanged( self, level ):
        try:
            self.signals.changeSatatusMessage.emit( f'Workflow level{level}: {self.WORKFLOW_LEVELS[level-1]}')
        except IndexError:
            pass

    def onFlowButtonClicked( self, level ):
        self.flow_btn.setEnabled(False)
        runner = ColoraturaProcessRunner( self.loggingQueue, self.coloratura, level = level )
        if isinstance(runner.finSignal.finished, pyqtBoundSignal ):
            runner.finSignal.finished.connect(lambda: self.flow_btn.setEnabled(True))
            self.signals.addRunner.emit(runner)
        else:
            self.flow_btn.setEnabled(True)

    def onStateChanged(self, state):
        pass

    def setTemplateImage(self, mat):
        pixmap = mat2QPixmap( mat )
        self.templateView.setFixedHeight( 30 )
        self.templateView.setPixmap( pixmap.scaledToHeight( 30 ) )
         
    def setRatioVal(self, val):
        self.tm_ratioBar.setValue(val)

    def setAngleVal(self, val):
        self.tm_angleBar.setValue(val)
      
def mat2QPixmap(matObj):
    
    if hasattr(matObj, 'mode'):
        if matObj.mode == "RGB":
            r, g, b = matObj.split()
            im = Image.merge("RGB", (b, g, r))
        elif  matObj.mode == "RGBA":
            r, g, b, a = matObj.split()
            im = Image.merge("RGBA", (b, g, r, a))
        elif matObj.mode == "L":
            im = matObj.convert("RGBA")
    else: # for np array
        im = Image.fromarray(matObj)

    # Bild in RGBA konvertieren, falls nicht bereits passiert
    im2 = im.convert("RGBA")
    data = im2.tobytes("raw", "RGBA")
    qim = QImage(data, im.size[0], im.size[1], QImage.Format_ARGB32)
    qpixmap = QPixmap.fromImage(qim)
    return qpixmap