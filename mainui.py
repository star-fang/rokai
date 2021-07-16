from PyQt5.QtWidgets import QMainWindow, QProgressBar, QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from tracker import Tracker
from sweeper import Sweeper, SweeperWorkFlowSignals, SweeperWorker, SweeperWorkerSignals, SweeperWorkFlow
from minimap import MiniMap
from overlay import Overlay

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


class SweeperView(QMainWindow):
    Button_STATE = 1
    Button_LOCATION = 2
    Button_CRACK = 3
    Button_FIND = 4
    def __init__(self, signId:int, amuSignals: QObject, threadPool: QThreadPool, sweeper: Sweeper, parent=None):
        QMainWindow.__init__(self, parent)
        self.sweeper = sweeper
        self.initUi()
        
        self.amuSignals = amuSignals
        amuSignals.hideSign.connect(self.toggleWindow)
        amuSignals.closeSign.connect(self.requestClose)

        self._closeflag = False

        self.threadPool = threadPool
        self.signId = signId

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
            self.connectWorkerSignals(worker.getSignals(), work)
            self.threadPool.start(worker)
        elif( flow > -1 ):
            workflow = SweeperWorkFlow( self.sweeper, args, flow = flow) 
            self.connectWorkFlowSignals(workflow.getSignals(), workflow.getWorkerSignals(), flow)
            self.threadPool.start(workflow)
    
    def connectWorkFlowSignals( self, signals: SweeperWorkFlowSignals, workerSignals: SweeperWorkerSignals, flow:int ):
        if flow == SweeperWorkFlow.FLOW_IDF_STATE:
            workerSignals.reportState.connect(lambda report, add:self.setStateText(report, add))
            workerSignals.changeLocation.connect( lambda t:self.amuSignals.coordinatesSign.emit(t))
            workerSignals.changeScreen.connect( lambda mat:self.setScreenImage(mat) )
        
        signals.finished.connect(lambda: self.onWorkFlowFinished(flow))

    
    def connectWorkerSignals( self, signals: SweeperWorkerSignals, work: int ):
        if work == SweeperWorker.WORK_CRACK:
            signals.changeTemplate.connect( lambda mat:self.setTemplateImage(mat) )
            signals.changeTmRatio.connect( lambda v:self.setRatioVal(v) )
            signals.changeTmRotate.connect( lambda v:self.setAngleVal(v) )
        elif work == SweeperWorker.WORK_WHERE:
            signals.changeLocation.connect( lambda t:self.amuSignals.coordinatesSign.emit(t))

        signals.changeScreen.connect( lambda mat:self.setScreenImage(mat) )
        signals.finished.connect(lambda: self.onWorkFinished(work))
        


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
        elif( state == Sweeper.STATE_CHECK_ROBOT2 ):
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

class AmuSignals(QObject):
    SIGN_MINIMAP = 1
    SIGN_OVERLAY = 2
    SIGN_SWEEPER = 3
    SIGN_STOP = 4
    SIGN_PAUSE = 5
    SIGN_START = 6
    hideSign = pyqtSignal(int, bool)
    closeSign = pyqtSignal(int)
    coordinatesSign = pyqtSignal(tuple)
    closedSign = pyqtSignal(int)
    clicked = pyqtSignal(int,int,int)

class RokAMU(QMainWindow):
      
    def __init__(self, systemResolution: list, sweeper: Sweeper, parent = None):
        QMainWindow.__init__(self, parent)
        self.tracker = None

        mainWidget = QWidget(self)
        self.setCentralWidget(mainWidget)

        self.threadPool = QThreadPool( parent = self )
        self.threadPool.setMaxThreadCount(10)

        self.sweeper = sweeper
        self.resolutionOption = self.initResolutionOption( systemResolution )
        
        #self.initNputHandler()

        self.signals = AmuSignals()
        self.createSubWindows()
        self.connectSubSignals()
        self.initUI()

    def initNputHandler( self ):
        self.tracker = Tracker()
        self.tracker.setCountDown.emit(1)
        self.tracker.mouseClicked.connect(lambda a,b, c: print(f'a:{a}, b:{b}, c:{c}'))
        
    def initResolutionOption(self, resolution, marginRate = 0.7):
        detectionPartLimit = (2*resolution[0]//3, 2*resolution[1]//3)
        if bool( detectionPartLimit[0]*marginRate > 800 ) and bool( detectionPartLimit[1]*marginRate > 600):
            return (800,600,marginRate)
        elif bool( detectionPartLimit[0]*marginRate > 640 ) and bool( detectionPartLimit[1]*marginRate > 480):
            return (640,480,marginRate)
        else:
            return (480,360,marginRate)

    def closeEvent(self, e):
        self.threadPool.releaseThread()
        self.signals.closeSign.emit( AmuSignals.SIGN_MINIMAP )
        self.signals.closeSign.emit( AmuSignals.SIGN_OVERLAY )
        self.signals.closeSign.emit( AmuSignals.SIGN_SWEEPER )
        print( str(self.__class__.__name__) + ' closed')
        return super().closeEvent(e)

    def createSubWindows( self ):
        self.sweeperView = SweeperView( AmuSignals.SIGN_SWEEPER, self.signals, self.threadPool, self.sweeper, parent = self)
        self.overlay = Overlay( self.tracker, AmuSignals.SIGN_OVERLAY, self.signals, self.threadPool, self.sweeper, parent = self)
        self.rokMiniMap = MiniMap( AmuSignals.SIGN_MINIMAP, self.signals, self.threadPool, parent = self )

    def connectSubSignals( self):
        self.signals.closedSign.connect(lambda s:self.onSubWindowClosed(s))

    def initUI(self):

        initWidth = self.resolutionOption[0]/self.resolutionOption[2]
        initHeight = self.resolutionOption[1]/self.resolutionOption[2]

        self.sweeperView.setGeometry( initWidth+100, 0, 400, initHeight)
        self.sweeperView.show()

        self.overlay.setGeometry( 50, 50, initWidth - 50 , initHeight - 50 )
        self.overlay.show()
    
        #self.sweeper.setDetectionPart( 0, 0, initWidth, initHeight) 
        

        self.rokMiniMap.setGeometry(initWidth+100, initHeight + 50, 300, 300 )
        self.rokMiniMap.show()

        hbox = QHBoxLayout(self.centralWidget())

        self.minimap_btn = QPushButton('미니맵')
        self.minimap_btn.clicked.connect(lambda: self.onClickButton(AmuSignals.SIGN_MINIMAP))
        self.minimap_btn.setCheckable(True)
        self.minimap_btn.setChecked(True)
        self.minimap_btn.setStyleSheet('background-color: lightblue')
        hbox.addWidget(self.minimap_btn)

        self.overlay_btn = QPushButton('오버레이')
        self.overlay_btn.clicked.connect(lambda: self.onClickButton(AmuSignals.SIGN_OVERLAY))
        self.overlay_btn.setCheckable(True)
        self.overlay_btn.setChecked(True)
        self.overlay_btn.setStyleSheet('background-color: lightblue')
        hbox.addWidget(self.overlay_btn)

        self.sweeper_btn = QPushButton('탐지화면')
        self.sweeper_btn.clicked.connect(lambda: self.onClickButton(AmuSignals.SIGN_SWEEPER))
        self.sweeper_btn.setCheckable(True)
        self.sweeper_btn.setChecked(True)
        self.sweeper_btn.setStyleSheet('background-color: lightblue')
        hbox.addWidget(self.sweeper_btn)

        self.stop_btn = QPushButton('STOP')
        self.stop_btn.clicked.connect(lambda: self.onClickButton(AmuSignals.SIGN_STOP))
        self.stop_btn.setStyleSheet('background-color: lightgrey')
        hbox.addWidget(self.stop_btn)

        self.pause_btn = QPushButton('PAUSE')
        self.pause_btn.clicked.connect(lambda: self.onClickButton(AmuSignals.SIGN_PAUSE))
        self.pause_btn.setCheckable(True)
        self.pause_btn.setStyleSheet('background-color: lightgrey')
        hbox.addWidget(self.pause_btn)
        

        self.start_btn = QPushButton('START')
        self.start_btn.clicked.connect(lambda: self.onClickButton(AmuSignals.SIGN_START))
        self.start_btn.setCheckable(True)
        self.start_btn.setStyleSheet('background-color: lightgrey')
        hbox.addWidget(self.start_btn)

        self.move(0, initHeight + 50)

    

    def onStartButtonClicked( self ):
        if self.tracker is None:
            self.tracker = Tracker(2345, self.sweeper, self.bbox)
            self.tracker.start()
            print('start tracker first time')
        else:
            if self.tracker.isPaused():
                self.tracker.resume()
                print('resume tracker')
            elif self.tracker.isStopped():
                self.tracker.join()
                self.tracker = Tracker(2345, self.sweeper, self.bbox)
                self.tracker.start()
                print('re-start tracker')


    def selectButton(self, which):
        if which == AmuSignals.SIGN_OVERLAY:
            button = self.overlay_btn
        elif which == AmuSignals.SIGN_MINIMAP:
            button = self.minimap_btn
        elif which == AmuSignals.SIGN_SWEEPER:
            button = self.sweeper_btn
        elif which == AmuSignals.SIGN_START:
            button = self.start_btn
        elif which == AmuSignals.SIGN_PAUSE:
            button = self.pause_btn
        elif which == AmuSignals.SIGN_STOP:
            button = self.stop_btn
        else:
            button = None
        return button

    def onSubWindowClosed(self, which):
        button = self.selectButton(which)
        if button is not None:
            button.setChecked(False)
            button.setStyleSheet('background-color: lightgrey')     

    def onClickButton(self, which ):
        button = self.selectButton(which)
        
        if button is not None:
            if button.isChecked():
                self.signals.hideSign.emit( which, False)
                button.setStyleSheet('background-color: lightblue')
            else:
                self.signals.hideSign.emit( which, True)
                button.setStyleSheet('background-color: lightgrey')

    
    def onPauseButtonClicked( self ):
        if self.tracker is not None:
            self.tracker.pause()

    def onStopButtonClicked( self ):
        if self.tracker is not None:
            self.tracker.stop()
    
    


      
