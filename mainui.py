from PyQt5.QtWidgets import QMainWindow, QProgressBar, QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from tracker import Tracker
from sweeper import Sweeper, Worker
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

class SweeperSignals(QObject):
    locationSign = pyqtSignal(int, int, int)
    closeButtonSignal = pyqtSignal()

class SweeperView(QMainWindow):
    Button_SCREEN = 1
    Button_STATE = 2
    Button_CRACK = 3
    Button_FIND = 4
    def __init__(self, amuSignals, sweeper,parent=None):
        QMainWindow.__init__(self, parent)
        self.sweeper = sweeper
        self.signals = SweeperSignals()
        self.initUi()
        
        amuSignals.hideSign.connect(self.toggleWindow)
        amuSignals.closeSign.connect(self.requestClose)

        self._closeflag = False

    def requestClose( self ):
        self._closeflag = True
        self.close()
    
    def getSignals(self):
        return self.signals
    
    def toggleWindow( self, sign, hide):
        if sign == AmuSignals.SIGN_SWEEPER:
            if hide:
                self.hide()
            else:
                self.show()

    def hideEvent(self, event):
        print( str(self.__class__.__name__) + ' disappeared')
        return super().hideEvent(event)
    
    def closeEvent(self, event):
        if self._closeflag is False:
            self.signals.closeButtonSignal.emit()
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

        self.screen_btn = QPushButton('화면 감지')
        self.screen_btn.setFixedHeight(30)
        self.screen_btn.clicked.connect( lambda: self.onButtonCLicked(self.Button_SCREEN))

        self.state_btn = QPushButton('상태 체크')
        self.state_btn.setFixedHeight(30)
        self.state_btn.clicked.connect( lambda: self.onButtonCLicked(self.Button_STATE))
        self.state_btn.setEnabled(False)

        self.find_btn = QPushButton('루비 찾기')
        self.find_btn.setFixedHeight(30)
        self.find_btn.clicked.connect( lambda: self.onButtonCLicked( self.Button_FIND))
        self.find_btn.setEnabled(False)

        self.crack_btn = QPushButton('인증 풀기')
        self.crack_btn.setFixedHeight(30)
        self.crack_btn.clicked.connect( lambda: self.onButtonCLicked( self.Button_CRACK))
        self.crack_btn.setEnabled(False)

        hbox_test.addWidget(self.screen_btn)
        hbox_test.addWidget(self.state_btn)
        hbox_test.addWidget(self.find_btn)
        hbox_test.addWidget(self.crack_btn)

        layout.addLayout( hbox_test )

        self.centralWidget().setLayout(layout)

    def onButtonCLicked( self, which ):
        work = -1
        if which == self.Button_SCREEN:
            self.screen_btn.setEnabled(False)
            work = Worker.WORK_DETECT_SCREEN
        elif which == self.Button_STATE:
            self.state_btn.setEnabled(False)
            work = Worker.WORK_IDENTIFY_STATE
        elif which == self.Button_CRACK:
            self.crack_btn.setEnabled(False)
            work = Worker.WORK_CRACK
        elif which == self.Button_FIND:
            self.find_btn.setEnabled(False)
            work = Worker.WORK_RUBY
        
        if( work > -1 ):
          thread = self.makeWorkerThread(work)
          thread.finished.connect(lambda w=work:self.onWorkFinished(w))
          thread.start()

    def onWorkFinished( self, work ):
        if( work == Worker.WORK_DETECT_SCREEN):
            print('screen recognized')
            self.screen_btn.setEnabled(True)
        elif( work == Worker.WORK_CRACK ):
            print('crack work finished')
            self.setRatioVal(0)
            self.setRatioVal(0)
        elif( work == Worker.WORK_IDENTIFY_STATE ):
            print('state identified')
            self.state_btn.setEnabled(True)
        elif( work == Worker.WORK_RUBY ):
            print('find ruby work finished')

    def makeWorkerThread( self, work ):

        self.worker = Worker( self.sweeper, parent = None, work=work )
        thread = QThread(parent = self)
        self.worker.moveToThread(thread)

        self.worker.state.connect(lambda s:self.onStateChanged(s))
        self.worker.stateReport.connect(lambda report:self.setStateText(report))
        self.worker.changeScreen.connect( lambda mat:self.setScreenImage(mat) )
        self.worker.changeTemplate.connect( lambda mat:self.setTemplateImage(mat) )
        self.worker.tm_ratio.connect( lambda v:self.setRatioVal(v) )
        self.worker.tm_rotate.connect( lambda v:self.setAngleVal(v) )
        self.worker.changeLocation.connect( lambda s,x,y:self.signals.locationSign.emit(s,x,y))

        self.worker.finished.connect(thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)

        thread.started.connect(self.worker.run)
        thread.finished.connect(thread.deleteLater)

        return thread

    def onStateChanged(self, state):
        if( state == Sweeper.DET_STATE_SCREEN_RECOG ):
            self.state_btn.setEnabled(True)
            self.find_btn.setEnabled(False)
            self.crack_btn.setEnabled(False)
        elif( state == Sweeper.DET_STATE_NO_SCREEN ):
            self.state_btn.setEnabled(False)
            self.find_btn.setEnabled(False)
            self.crack_btn.setEnabled(False)
        elif( state == Sweeper.STATE_NORMAL ):
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
        
    def setStateText(self, text):
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
    coordinatesSign = pyqtSignal(int,int,int)

class RokAMU(QMainWindow):
      
    def __init__(self, systemResolution, sweeper, parent = None):
        QMainWindow.__init__(self, parent)
        self.tracker = None

        mainWidget = QWidget(self)
        self.setCentralWidget(mainWidget)

        self.sweeper = sweeper
        self.resolutionOption = self.initResolutionOption( systemResolution )
        
        self.signals = AmuSignals()
        self.createSubWindows()
        self.connectSubSignals()
        self.initUI()
        
    def initResolutionOption(self, resolution, marginRate = 0.7):
        detectionPartLimit = (2*resolution[0]//3, 2*resolution[1]//3)
        if bool( detectionPartLimit[0]*marginRate > 800 ) and bool( detectionPartLimit[1]*marginRate > 600):
            return (800,600,marginRate)
        elif bool( detectionPartLimit[0]*marginRate > 640 ) and bool( detectionPartLimit[1]*marginRate > 480):
            return (640,480,marginRate)
        else:
            return (480,360,marginRate)

    def closeEvent(self, e):
        self.signals.closeSign.emit( AmuSignals.SIGN_MINIMAP )
        self.signals.closeSign.emit( AmuSignals.SIGN_OVERLAY )
        self.signals.closeSign.emit( AmuSignals.SIGN_SWEEPER )
        print( str(self.__class__.__name__) + ' closed')
        return super().closeEvent(e)

    def createSubWindows( self ):
        self.sweeperView = SweeperView( self.signals, self.sweeper, parent = self)
        self.overlay = Overlay( self.signals, parent = self)
        self.rokMiniMap = MiniMap( self.signals, parent = self )

    def connectSubSignals( self):
        overlaySignals = self.overlay.getSignals()
        sweeperSignals = self.sweeperView.getSignals()
        minimapSignals = self.rokMiniMap.getSignals()

        overlaySignals.resizeSign.connect( lambda a,b,c,d:self.sweeper.setDetectionPart(a,b,c,d) )
        sweeperSignals.locationSign.connect( lambda a,b,c:self.signals.coordinatesSign.emit(a,b,c))

        overlaySignals.closeButtonSignal.connect( lambda:self.onSubWindowClosed(AmuSignals.SIGN_OVERLAY))
        sweeperSignals.closeButtonSignal.connect( lambda:self.onSubWindowClosed(AmuSignals.SIGN_SWEEPER))
        minimapSignals.closeButtonSignal.connect( lambda:self.onSubWindowClosed(AmuSignals.SIGN_MINIMAP))

    def initUI(self):

        initWidth = self.resolutionOption[0]/self.resolutionOption[2]
        initHeight = self.resolutionOption[1]/self.resolutionOption[2]

        self.sweeperView.setGeometry( initWidth, 0,380, initHeight)
        self.sweeperView.show()

        self.overlay.setGeometry(0, 0, initWidth, initHeight )
        self.overlay.show()
    
        self.sweeper.setDetectionPart( 0, 0, initWidth, initHeight) 
        

        self.rokMiniMap.setGeometry(initWidth, initHeight, 300, 300 )
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

        self.move(0, initHeight)

    

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
    
    


      
