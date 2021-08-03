from threading import Lock
from PyQt5.QtWidgets import QDialog, QPlainTextEdit, QProgressBar, QSlider, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from sweeper import Sweeper, SweeperWorker, SweeperWorkFlow
from matplotlib import pyplot as plt

class LoggingDialog( QDialog ):
    def __init__(self, painTextEdit:QPlainTextEdit, parent=None):
        super().__init__(parent)
        self.initUI(painTextEdit)
    
    def initUI( self, pte ):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Log'))
        layout.addWidget(pte)
        self.setLayout(layout)
    
class SweeperViewSignals(QObject):
    hideSign = pyqtSignal()
    showLogger = pyqtSignal()

class SweeperView(QWidget):
    Button_LOCATION = 2
    Button_CRACK = 3
    Button_FIND = 4
    def __init__(self, sweeper: Sweeper, parent=None):
        QWidget.__init__(self, parent)
        self.sweeper = sweeper
        self.initUi()
        
        self.signals = SweeperViewSignals()
        self.signals.showLogger.connect(lambda: self.showLoggingDialog() )
        self.plainTextLogger = QPlainTextEdit()
        self.connectSweeperSignals()

    def showLoggingDialog(self):
        dialog = LoggingDialog(self.plainTextLogger, parent=self)
        dialog.show()
        dialog.raise_()

    def loggingPlainText(self, msg):
        with Lock():
            self.plainTextLogger.appendPlainText(msg)

    def connectSweeperSignals( self ):
        
        self.sweeper.logInfo.connect( lambda msg: self.loggingPlainText(msg) )
        self.sweeper.changeTemplate.connect( lambda mat:self.setTemplateImage(mat) )
        self.sweeper.changeTmRatio.connect( lambda v:self.setRatioVal(v) )
        self.sweeper.changeTmRotate.connect( lambda v:self.setAngleVal(v) )
        self.sweeper.changeState.connect( lambda s:self.onStateChanged(s))
        self.sweeper.plotPlt.connect( self.histShow )

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
        self.flow_slider.setMaximum(3)
        self.flow_slider.setValue(1)
        self.flow_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.flow_slider.setTickInterval(1)
        self.flow_btn = QPushButton('RUN')
        self.flow_btn.setFixedHeight(30)
        self.flow_btn.clicked.connect( lambda: self.onFlowButtonClicked( self.flow_slider.value() ) )
        hbox_flow.addWidget(self.flow_slider)
        hbox_flow.addWidget(self.flow_btn)
        layout.addLayout( hbox_flow )

        hbox_works = QHBoxLayout()
        self.location_btn = QPushButton('# X Y')
        self.location_btn.setFixedHeight(30)
        self.location_btn.clicked.connect( lambda: self.onWorkButtonClicked(self.Button_LOCATION))
        self.find_btn = QPushButton('RUBY')
        self.find_btn.setFixedHeight(30)
        self.find_btn.clicked.connect( lambda: self.onWorkButtonClicked( self.Button_FIND))
        self.find_btn.setEnabled(False)
        self.crack_btn = QPushButton('CRACK')
        self.crack_btn.setFixedHeight(30)
        self.crack_btn.clicked.connect( lambda: self.onWorkButtonClicked( self.Button_CRACK))
        self.crack_btn.setEnabled(False)
        hbox_works.addWidget(self.location_btn)
        hbox_works.addWidget(self.find_btn)
        hbox_works.addWidget(self.crack_btn)
        layout.addLayout( hbox_works )
        self.setLayout(layout)

    def requestWorker( self, *args, work: int ): # for runnable worker
        if( work > -1 ):
            worker = SweeperWorker( self.sweeper, args, work = work  )
            worker.signals.finished.connect(lambda: self.onWorkFinished(work))
            self.sweeper.queuing.emit(worker)

    def onFlowButtonClicked( self, level ):
        self.flow_btn.setEnabled(False)
        workflow = SweeperWorkFlow( self.sweeper, level = level ) 
        workflow.signals.finished.connect(lambda: self.flow_btn.setEnabled(True))
        self.sweeper.queuing.emit(workflow)

    def onWorkButtonClicked( self, which  ):
        work = -1
        if which == self.Button_LOCATION:
            self.location_btn.setEnabled(False)
            work = SweeperWorker.WORK_COORDINATES
        elif which == self.Button_CRACK:
            self.crack_btn.setEnabled(False)
            work = SweeperWorker.WORK_CRACK
        elif which == self.Button_FIND:
            self.find_btn.setEnabled(False)
            work = SweeperWorker.WORK_RUBY

        self.requestWorker( work = work )

    def onWorkFinished( self, work ):
        if( work == SweeperWorker.WORK_COORDINATES):
            self.location_btn.setEnabled(True)
        elif( work == SweeperWorker.WORK_CRACK ):
            self.setAngleVal(0)
            self.setRatioVal(0)
            self.crack_btn.setEnabled(True)
        elif( work == SweeperWorker.WORK_RUBY ):
            self.find_btn.setEnabled(True)

    def onStateChanged(self, state):
        if( state == Sweeper.NO_DIALOG ):
            self.crack_btn.setEnabled(False)
            self.find_btn.setEnabled(True)
        elif( state == Sweeper.DIALOG_ROBOT ):
            self.find_btn.setEnabled(False)
            self.crack_btn.setEnabled(True)
        else:
            self.find_btn.setEnabled(False)
            self.crack_btn.setEnabled(False)

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