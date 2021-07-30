from PyQt5.QtWidgets import QMainWindow, QProgressBar, QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import QObject, QThreadPool
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from sweeper import Sweeper, SweeperWorker, SweeperWorkFlow
from threading import Lock
from matplotlib import pyplot as plt

class SweeperView(QMainWindow):
    Button_STATE = 1
    Button_LOCATION = 2
    Button_CRACK = 3
    Button_FIND = 4
    def __init__(self, signId:int, amuSignals: QObject, threadPool: QThreadPool, sweeper: Sweeper, mutex:Lock, parent=None):
        QMainWindow.__init__(self, parent)
        self.sweeper = sweeper
        self.initUi()
        
        self.amuSignals = amuSignals
        amuSignals.hideSign.connect(self.toggleWindow)
        amuSignals.closeSign.connect(self.requestClose)

        self._closeflag = False

        self.threadPool = threadPool
        self.signId = signId

        self.mutex = mutex

        self.connectSweeperSignals()

    def connectSweeperSignals( self ):
        
        self.sweeper.reportState.connect(lambda report, add:self.setStateText(report, add))
        self.sweeper.changeScreen.connect( lambda mat:self.setScreenImage(mat) )
        self.sweeper.changeTemplate.connect( lambda mat:self.setTemplateImage(mat) )
        self.sweeper.changeTmRatio.connect( lambda v:self.setRatioVal(v) )
        self.sweeper.changeTmRotate.connect( lambda v:self.setAngleVal(v) )
        self.sweeper.changeState.connect( lambda s:self.onStateChanged(s))
        self.sweeper.plotPlt.connect( self.histShow )

    def histShow( self, mat ):
        plt.hist( mat.ravel(), 256, [0,256])
        plt.show()

    def requestClose( self ):
        self._closeflag = True
        self.close()
    
    def toggleWindow( self, sign, hide):
        if sign == self.signId:
            if hide:
                self.hide()
            else:
                self.show()

    def hideEvent(self, event):
        print( str(self.__class__.__name__) + ' disappeared')
        return super().hideEvent(event)
    
    def closeEvent(self, event):
        if self._closeflag is False:
            self.amuSignals.closedSign.emit( self.signId )
            self.hide()
            event.ignore()
        else:
            print( str(self.__class__.__name__) + ' closed')
            event.accept()

    def initUi(self):
        widget = QWidget()
        self.setCentralWidget(widget)

        self.screenView = QLabel()
        self.templateView = QLabel()
        self.stateText = QTextEdit()
        self.resolutionText = QLabel('640 X 480')

        self.tm_ratioBar = QProgressBar()
        self.tm_ratioBar.setMinimum(0)
        self.tm_ratioBar.setMaximum(100)
        self.tm_angleBar = QProgressBar()
        self.tm_angleBar.setMinimum(0)
        self.tm_angleBar.setMaximum(360)

        layout = QVBoxLayout()
        
        self.w, self.h = self.geometry().getRect()[2:]
        self.screenView.setFixedSize( 360, 270 )

        layout.addWidget(self.screenView)
        layout.addWidget(self.resolutionText)
        layout.addWidget(self.stateText)

        hbox = QHBoxLayout()
        hbox.addWidget( self.templateView)
        vbox_rr = QVBoxLayout()
        hbox_ra = QHBoxLayout()
        hbox_ro = QHBoxLayout()
        hbox_ra.addWidget(QLabel('RA: '))
        hbox_ra.addWidget(self.tm_ratioBar)
        hbox_ro.addWidget(QLabel('RO: '))
        hbox_ro.addWidget(self.tm_angleBar)
        vbox_rr.addLayout(hbox_ra)
        vbox_rr.addLayout(hbox_ro)
        hbox.addLayout(vbox_rr)

        layout.addLayout( hbox )

        hbox_test = QHBoxLayout()
        hbox_test.addWidget(QLabel('테스트: '))

        self.state_btn = QPushButton('상태 체크')
        self.state_btn.setFixedHeight(30)
        self.state_btn.clicked.connect( lambda: self.onButtonCLicked(self.Button_STATE))
        #self.state_btn.setEnabled(False)

        self.location_btn = QPushButton('위치 확인')
        self.location_btn.setFixedHeight(30)
        self.location_btn.clicked.connect( lambda: self.onButtonCLicked(self.Button_LOCATION))

        self.find_btn = QPushButton('루비 찾기')
        self.find_btn.setFixedHeight(30)
        self.find_btn.clicked.connect( lambda: self.onButtonCLicked( self.Button_FIND))
        #self.find_btn.setEnabled(False)

        self.crack_btn = QPushButton('인증 풀기')
        self.crack_btn.setFixedHeight(30)
        self.crack_btn.clicked.connect( lambda: self.onButtonCLicked( self.Button_CRACK))
        #self.crack_btn.setEnabled(False)

        
        hbox_test.addWidget(self.state_btn)
        hbox_test.addWidget(self.location_btn)
        hbox_test.addWidget(self.find_btn)
        hbox_test.addWidget(self.crack_btn)

        layout.addLayout( hbox_test )

        self.centralWidget().setLayout(layout)

    def requestWorker( self, *args, work: int, flow: int ): # for runnable worker
        if( work > -1 ):
            worker = SweeperWorker( self.sweeper, args, work = work  )
            worker.signals.finished.connect(lambda: self.onWorkFinished(work))
            self.threadPool.start(worker)
        elif( flow > -1 ):
            workflow = SweeperWorkFlow( self.sweeper, args, flow = flow) 
            workflow.signals.finished.connect(lambda: self.onWorkFlowFinished(flow))
            self.threadPool.start(workflow)

    def onButtonCLicked( self, which ):
        work = -1
        flow = -1
        if which == self.Button_LOCATION:
            self.location_btn.setEnabled(False)
            work = SweeperWorker.WORK_WHERE
        elif which == self.Button_STATE:
            self.state_btn.setEnabled(False)
            flow = SweeperWorkFlow.FLOW_IDF_STATE
        elif which == self.Button_CRACK:
            self.crack_btn.setEnabled(False)
            work = SweeperWorker.WORK_CRACK
        elif which == self.Button_FIND:
            self.find_btn.setEnabled(False)
            work = SweeperWorker.WORK_RUBY

        self.requestWorker( work = work, flow = flow )
    
    def onWorkFlowFinished( self, flow ):
        if( flow == SweeperWorkFlow.FLOW_IDF_STATE ):
            print('identifing flow finished')
            self.state_btn.setEnabled(True)

    def onWorkFinished( self, work ):
        if( work == SweeperWorker.WORK_WHERE):
            print('where am I?')
            self.location_btn.setEnabled(True)
        elif( work == SweeperWorker.WORK_CRACK ):
            print('crack work finished')
            self.setAngleVal(0)
            self.setRatioVal(0)
            self.crack_btn.setEnabled(True)
        elif( work == SweeperWorker.WORK_RUBY ):
            print('find ruby work finished')
            self.find_btn.setEnabled(True)

    def onStateChanged(self, state):
        if( state == Sweeper.NO_DIALOG ):
            self.crack_btn.setEnabled(False)
            self.find_btn.setEnabled(True)
        elif( state == Sweeper.DIALOG_ROBOT2 ):
            self.find_btn.setEnabled(False)
            self.crack_btn.setEnabled(True)
        else:
            self.find_btn.setEnabled(False)
            self.crack_btn.setEnabled(False)

    def setScreenImage(self, mat):
        if mat is None:
            self.screenView.clear()
            return
        pixmap = mat2QPixmap( mat )
        sWidth,sHeight = self.screenView.geometry().getRect()[2:]
        
        if bool( sWidth > pixmap.width() ) and bool( sHeight > pixmap.height() ):
            self.screenView.setPixmap( pixmap )
        elif pixmap.width() * 2 > pixmap.height() * 3:
            self.screenView.setPixmap( pixmap.scaledToWidth( sWidth ) )
        else:
            self.screenView.setPixmap( pixmap.scaledToHeight( sHeight ) )

    def setTemplateImage(self, mat):
        pixmap = mat2QPixmap( mat )
        self.templateView.setFixedHeight( 30 )
        self.templateView.setPixmap( pixmap.scaledToHeight( 30 ) )
        
    def setStateText(self, text, add=True):
        if add:
            text = f'{self.stateText.toPlainText()}\n{text}'
        self.stateText.setText(text)
    
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