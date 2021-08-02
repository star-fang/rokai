from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QPushButton
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from tracker import Tracker
from sweeper import Sweeper
from minimap import MiniMap
from overlay import Overlay
from threading import Lock
from sweeperview import SweeperView

class AmuSignals(QObject):
    SIGN_MINIMAP = 1
    SIGN_OVERLAY = 2
    SIGN_SWEEPER = 3
    SIGN_STOP = 4
    SIGN_PAUSE = 5
    SIGN_START = 6
    hideSign = pyqtSignal(int, bool)
    closeSign = pyqtSignal(int)
    closedSign = pyqtSignal(int)
    queuing = pyqtSignal(QRunnable)

class RokAMU(QMainWindow):
      
    def __init__(self, systemResolution: list, parent = None):
        QMainWindow.__init__(self, parent)
        self.tracker = None

        mainWidget = QWidget(self)
        self.setCentralWidget(mainWidget)

        self.threadPool = QThreadPool( parent = self )
        self.threadPool.setMaxThreadCount(10)

        self.sweeper = Sweeper()
        self.resolutionOption = self.initResolutionOption( systemResolution )

        self.mutex = Lock()

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
        self.sweeper.deleteLater()
        self.threadPool.releaseThread()
        self.signals.closeSign.emit( AmuSignals.SIGN_MINIMAP )
        self.signals.closeSign.emit( AmuSignals.SIGN_OVERLAY )
        self.signals.closeSign.emit( AmuSignals.SIGN_SWEEPER )
        print( str(self.__class__.__name__) + ' closed')
        return super().closeEvent(e)

    def createSubWindows( self ):
        self.sweeperView:SweeperView = SweeperView( AmuSignals.SIGN_SWEEPER, self.signals, self.sweeper, self.mutex, parent = self)
        self.rokMiniMap = MiniMap( AmuSignals.SIGN_MINIMAP, self.signals, self.sweeper, self.mutex, parent = self )
        self.overlay = Overlay( self.tracker, AmuSignals.SIGN_OVERLAY, self.signals, self.sweeper, self.mutex , parent = self)

    def connectSubSignals( self):
        self.signals.closedSign.connect(lambda s:self.onSubWindowClosed(s))
        self.signals.queuing.connect( lambda r: self.threadPool.start( r ))

    def initUI(self):

        initWidth = self.resolutionOption[0]/self.resolutionOption[2]
        initHeight = self.resolutionOption[1]/self.resolutionOption[2]

        self.sweeperView.setGeometry( initWidth+100, 0, 400, initHeight)
        self.sweeperView.show()

        self.overlay.setGeometry( 50, 50, initWidth - 50 , initHeight - 50 )
        self.overlay.show()
        self.overlay.requestDetectScreenWork()
    
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
        self.show()


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
    
    


      
