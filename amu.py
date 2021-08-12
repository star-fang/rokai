from PyQt5.QtWidgets import QAction, QCheckBox, QDialog, QLabel, QMainWindow, QMenu, QMenuBar, QPlainTextEdit, QVBoxLayout, QWidget, QWidgetAction
from PyQt5.QtCore import QMutex, QObject, Qt, pyqtBoundSignal, pyqtSignal
from coloratura import Coloratura
from minimap import MiniMap
from overlay import Overlay
from coloratura_view import ColoraturaView
from pyautogui import size
from multiprocessing import Queue
from log import MultiProcessLogging

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
        if not self._closeflag:
            self.closeSignal.closed.emit()
        return super().closeEvent(evt)

class RokAMU(QMainWindow):
    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        systemResolution = size()
        self.resolutionOption = self.initResolutionOption( systemResolution )
        self.signals = type("Signals", (QObject,), {'logInfo': pyqtSignal(str), 'showMessage':pyqtSignal(str)})()
        self.logger = self.prepareLogger()
        self.coloratura = Coloratura(self.loggingQueue)
        self.createSubWindows()
        self.initUI(systemResolution)
        self.createStatusBar()
        self.createActions()
        self.createMenus()
        self.createMenuBar()
        self.createLandToolBar()
    
    def createStatusBar(self):
        self.statusBar().setStyleSheet('QStatusBar{padding-left:8px;background:rgba(20,20,20,30);color:white;font-weight:bold;}')
        self.statusBar().showMessage('hello')
        if isinstance(self.signals.showMessage, pyqtBoundSignal ):
            self.signals.showMessage.connect(lambda m: self.statusBar().showMessage(m))

    def prepareLogger(self):
        self.loggingQueue = Queue(-1)
        self.logListener = MultiProcessLogging()
        if isinstance( self.signals.logInfo, pyqtBoundSignal ):
            self.signals.logInfo.connect( lambda msg: self.loggingPlainText(msg) )
            self.logListener.startGetter(self.loggingQueue, 'listener', self.signals.logInfo )
        else:
            self.logListener.startGetter(self.loggingQueue, 'listener' )
    
        logger = MultiProcessLogging().make_q_handled_logger(self.loggingQueue, 'amu')
        logger.info('test-info')
        logger.debug('test-debug')
        logger.warning('test-warning')
        logger.error('test-error')
        logger.critical('test-critical')
        return logger

    def loggingPlainText(self, msg):
        mutex = QMutex()
        if mutex.tryLock(2000):
            self.plainTextLogger.appendPlainText(msg)
            mutex.unlock()
        else:
            self.logger.debug('plain text logging failure: deadlock')
        
    def initResolutionOption(self, resolution, marginRate = 0.7):
        detectionPartLimit = (2*resolution[0]//3, 2*resolution[1]//3)
        if bool( detectionPartLimit[0]*marginRate > 800 ) and bool( detectionPartLimit[1]*marginRate > 600):
            return (800,600,marginRate)
        elif bool( detectionPartLimit[0]*marginRate > 640 ) and bool( detectionPartLimit[1]*marginRate > 480):
            return (640,480,marginRate)
        else:
            return (480,360,marginRate)

    def closeEvent(self, e):
        self.logger.debug('amu closed')
        self.logListener.stopGetter(self.loggingQueue)
        self.coloratura.deleteLater()
        self.overlay.signals.systemEndSign.emit()
        return super().closeEvent(e)

    def createSubWindows( self ):
        self.plainTextLogger = QPlainTextEdit()
        self.coloraturaView:ColoraturaView = ColoraturaView( self.loggingQueue, self.signals.showMessage, self.coloratura, parent = self) # sub widget
        self.rokMiniMap:MiniMap = MiniMap( self.loggingQueue, self.coloratura, parent = self ) # sub widget
        self.rokMiniMap.signals.landLoaded.connect( lambda id, name: self.createLandAction(id, name))
        self.overlay:Overlay = Overlay( self.loggingQueue, self.coloratura , parent = self) # sub window

    def initUI(self, systemResolution):
        mainWidget = QWidget(self)
        self.setCentralWidget(mainWidget)

        initWidth = self.resolutionOption[0]/self.resolutionOption[2]
        initHeight = self.resolutionOption[1]/self.resolutionOption[2]

        self.overlay.setGeometry( 50, 50, initWidth - 50 , initHeight - 50 )
        self.overlay.requestDetectScreenWork()

        vbox = QVBoxLayout(self.centralWidget())
        vbox.addWidget(self.rokMiniMap)
        vbox.addWidget(self.coloraturaView)
        
        self.move( systemResolution[0] - self.size().width(), 0)
        self.show()
    
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
        self.overlay.signals.hideSign.connect( lambda hide: self.showOverlayAction.setChecked( not hide) )
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

    
    


      
