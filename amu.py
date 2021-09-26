from logging import getLogger
from PyQt5.QtWidgets import QAction, QCheckBox, QDialog, QLabel, QMainWindow, \
    QMenu, QMenuBar, QPlainTextEdit, QVBoxLayout, QWidget, QWidgetAction
from PyQt5.QtCore import QMutex, QObject, QThreadPool, Qt, pyqtBoundSignal, pyqtSignal
from coloratura import Coloratura
from minimap import MiniMap
from overlay import Overlay
from coloratura_view import ColoraturaView
from pyautogui import size, press
from log import init_logger

class RokAMU(QMainWindow):
    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.prepareLogger()
        self.coloratura = Coloratura()
        self.coloratura.statusMessage.connect(lambda m: self.statusBar().showMessage(m))
        self.threadPool = QThreadPool( self )
        self.threadPool.setMaxThreadCount(1)
        
        self.createStatusBar()
        self.createActions()
        self.createMenus()
        self.createMenuBar()
        self.createLandToolBar()

        self.createSubWindows() # create sub ui and connect signals
        self.initUI()

    def prepareLogger(self) -> None:
        signalObj = type('Signal', (QObject,), {'logSign': pyqtSignal(str)})()
        if hasattr(signalObj,'logSign') and isinstance(signalObj.logSign, pyqtBoundSignal):
            def loggingPlainText(msg:str):
                mutex = QMutex()
                if mutex.tryLock(2000):
                    try:
                        self.plainTextLogger.appendPlainText(msg)
                    except AttributeError:
                        pass
                    finally:
                        mutex.unlock()
            signalObj.logSign.connect(loggingPlainText)
            self.logListener, self.logQueue = init_logger(signalObj)
        
        self.logger = getLogger()

    def createSubWindows( self ):
        self.plainTextLogger = QPlainTextEdit()
        self.coloraturaView = ColoraturaView( self.coloratura, self.logQueue, parent = self) # sub widget
        self.coloraturaView.signals.addRunner.connect( lambda r: self.threadPool.start(r) )
        self.coloraturaView.signals.changeSatatusMessage.connect(lambda m: self.statusBar().showMessage(m))

        self.rokMiniMap = MiniMap( self.coloratura, parent = self ) # sub widget
        self.rokMiniMap.signals.landLoaded.connect( lambda id, name: self.createLandAction(id, name))

        self.overlay = Overlay( self.coloratura , parent = self) # sub window
        self.overlay.signals.addRunner.connect( lambda r: self.threadPool.start(r) )
        self.overlay.signals.hideSign.connect( lambda hide: self.showOverlayAction.setChecked( not hide) )

    def initUI(self):
        def initResolutionOption(resolution, marginRate = 0.7):
            detectionPartLimit = (2*resolution[0]//3, 2*resolution[1]//3)
            if bool( detectionPartLimit[0]*marginRate > 800 ) and bool( detectionPartLimit[1]*marginRate > 600):
                return (800,600,marginRate)
            elif bool( detectionPartLimit[0]*marginRate > 640 ) and bool( detectionPartLimit[1]*marginRate > 480):
                return (640,480,marginRate)
            else:
                return (480,360,marginRate)
        systemResolution = size()
        resolutionOption = initResolutionOption( systemResolution )
        mainWidget = QWidget(self)
        self.setCentralWidget(mainWidget)

        initWidth = resolutionOption[0]/resolutionOption[2]
        initHeight = resolutionOption[1]/resolutionOption[2]

        self.overlay.setGeometry( 50, 50, initWidth - 50 , initHeight - 50 )
        self.overlay.requestDetectScreenWork()

        vbox = QVBoxLayout(self.centralWidget())
        vbox.addWidget(self.rokMiniMap)
        vbox.addWidget(self.coloraturaView)
        
        self.move( systemResolution[0] - self.size().width(), 0)
        self.show()

    def createStatusBar(self):
        self.statusBar().setStyleSheet('QStatusBar{padding-left:8px;background:rgba(20,20,20,30);color:white;font-weight:bold;}')
        self.statusBar().showMessage('hello')

    def createActions(self):
        def loadData():
            self.landToolBar.clear()
            self.rokMiniMap.signals.readData.emit()
        self.loadAction = QAction(self)
        self.loadAction.setText('&LOAD')
        self.loadAction.triggered.connect(lambda: loadData())

        self.showLoggerAction = QAction(self)
        self.showLoggerAction.setCheckable(True)
        self.showLoggerAction.setText('&LOGGER')
        def logginDialog( checked:bool ):
            if checked:
                logginDialog.dialog = LoggingDialog(self.plainTextLogger, parent=self)
                if isinstance( logginDialog.dialog.closeSignal.closed, pyqtBoundSignal ):
                    logginDialog.dialog.closeSignal.closed.connect( lambda: self.showLoggerAction.setChecked(False))
                    logginDialog.dialog.show()
                    logginDialog.dialog.raise_()
            else:
                if isinstance(logginDialog.dialog, LoggingDialog):
                    if isinstance( logginDialog.dialog.closeSignal.close, pyqtBoundSignal ):
                        logginDialog.dialog.closeSignal.close.emit()
        logginDialog.dialog = None
        self.showLoggerAction.triggered.connect(lambda checked: logginDialog(checked))
        self.showOverlayAction = QAction(self)
        self.showOverlayAction.setCheckable(True)
        self.showOverlayAction.setText('&OVERLAY')
        self.showOverlayAction.triggered.connect(lambda: self.overlay.signals.toggleSign.emit())
        self.showOverlayAction.setChecked( True )
    
    def createMenus(self):
        self.fileMenu = QMenu()
        self.fileMenu.setTitle('&File')
        self.fileMenu.setStyleSheet(    'QMenu::item{\
                                            color: rgb(0,0,0);\
                                        }')
        self.fileMenu.addAction(self.loadAction)

        self.widgetMenu = QMenu()
        self.widgetMenu.setTitle('&Widget')
        self.widgetMenu.addAction(self.showLoggerAction)
        self.widgetMenu.addAction(self.showOverlayAction)    
    
    def createMenuBar(self):
        menubar = QMenuBar()
        menubar.setStyleSheet(    'QMenuBar::item{\
                                            color: rgb(0,0,0);\
                                        }')
        menubar.addMenu(self.fileMenu)
        menubar.addMenu(self.widgetMenu)                     
        self.setMenuBar(menubar)

    def createLandAction( self, id, name:dict):
        checkBox = QCheckBox(name.get('kor','?'))
        checkBox.stateChanged.connect(lambda state: \
            self.rokMiniMap.signals.landChecked.emit(id, state==Qt.CheckState.Checked))
        landAction = QWidgetAction(self)
        landAction.setDefaultWidget(checkBox)
        self.landToolBar.addAction(landAction)

    def createLandToolBar(self):
        self.landToolBar = self.addToolBar("lands")
        self.addToolBar(self.landToolBar)
    
    def closeEvent(self, e):
        press('esc') # stop workflow
        self.threadPool.waitForDone() # wait workflow end
        self.overlay.signals.systemEndSign.emit()
        self.coloratura.deleteLater()
        self.logger.debug('amu closed')
        self.logListener.stop()
        return super().closeEvent(e)

class LoggingDialog( QDialog ):
    def __init__(self, painTextEdit:QPlainTextEdit, parent=None):
        super().__init__(parent)
        self.initUI(painTextEdit)
        self._closeflag= False
        self.closeSignal = type("CloseSignal", (QObject,), {'close': pyqtSignal(),'closed': pyqtSignal()})()
        if isinstance( self.closeSignal.close, pyqtBoundSignal ):
            self.closeSignal.close.connect(self.closeByMenuButton)
    
    def closeByMenuButton(self):
        self._closeflag = True
        self.close()
    
    def initUI( self, pte ):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Log'))
        layout.addWidget(pte)
        self.setLayout(layout)

    def closeEvent(self, evt):
        if not self._closeflag and isinstance( self.closeSignal.closed, pyqtBoundSignal ):
            self.closeSignal.closed.emit()
        return super().closeEvent(evt)

    
    


      
