from PyQt5.QtWidgets import QAction, QCheckBox, QDialog, QLabel, QMainWindow, QMenu, QMenuBar, QPlainTextEdit, QVBoxLayout, QWidget, QPushButton, QWidgetAction
from PyQt5.QtCore import QMutex, QObject, QThreadPool, Qt, pyqtSignal
from sweeper import Sweeper
from minimap import MiniMap
from overlay import Overlay
from sweeperview import SweeperView
from log import makeLogger

LogSignal = type("LogSignal", (QObject,), {'logInfo': pyqtSignal(str)})

class LoggingDialog( QDialog ):
    def __init__(self, painTextEdit:QPlainTextEdit, parent=None):
        super().__init__(parent)
        self.initUI(painTextEdit)
    
    def initUI( self, pte ):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Log'))
        layout.addWidget(pte)
        self.setLayout(layout)

class RokAMU(QMainWindow):
    def __init__(self, systemResolution: list, parent = None):
        QMainWindow.__init__(self, parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.threadPool = QThreadPool( parent = self )
        self.threadPool.setMaxThreadCount(10)
        self.resolutionOption = self.initResolutionOption( systemResolution )

        self.logSignal = LogSignal()
        self.logger = makeLogger(signal=self.logSignal.logInfo, name='amu')
        self.sweeper = Sweeper(self.logSignal)
        self.createSubWidgets()
        self.connectSubSignals()
        self.initUI(systemResolution)
        self.createActions()
        self.createMenus()
        self.createMenuBar()
        self.createLandToolBar()

        self.logger.info('program launched')
        

    def loggingPlainText(self, msg):
        mutex = QMutex()
        if mutex.tryLock(5000):
            self.plainTextLogger.appendPlainText(msg)
            mutex.unlock()
        else:
            self.logger.debug('plain text logging failure: deadlock')
    
    def showLoggingDialog(self):
        dialog = LoggingDialog(self.plainTextLogger, parent=self)
        dialog.show()
        dialog.raise_()
        
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
        self.overlay.signals.systemEndSign.emit()
        self.logger.debug('amu closed')
        return super().closeEvent(e)

    def createSubWidgets( self ):
        self.plainTextLogger = QPlainTextEdit()
        self.sweeperView:SweeperView = SweeperView( self.logSignal, self.sweeper, parent = self) # sub widget
        self.rokMiniMap:MiniMap = MiniMap( self.logSignal, self.sweeper, parent = self ) # sub widget
        self.overlay:Overlay = Overlay( self.logSignal, self.sweeper , parent = self) # sub window

    def connectSubSignals( self):
        try:
            self.logSignal.logInfo.connect( lambda msg: self.loggingPlainText(msg))
        except AttributeError:
            pass
        self.sweeper.queuing.connect( lambda r: self.threadPool.start(r))
        self.rokMiniMap.signals.landLoaded.connect( lambda id, name: self.createLandAction(id, name))

    def initUI(self, systemResolution):
        mainWidget = QWidget(self)
        self.setCentralWidget(mainWidget)

        initWidth = self.resolutionOption[0]/self.resolutionOption[2]
        initHeight = self.resolutionOption[1]/self.resolutionOption[2]

        self.overlay.setGeometry( 50, 50, initWidth - 50 , initHeight - 50 )
        self.overlay.hide()
        self.overlay.requestDetectScreenWork()

        vbox = QVBoxLayout(self.centralWidget())
        vbox.addWidget(self.rokMiniMap)
        vbox.addWidget(self.sweeperView)
        
        def toggleButton( button: QPushButton, clicked:bool):
            button.setChecked(clicked )
            self.overlay_btn.setStyleSheet('background-color: lightblue' if clicked \
                                            else 'background-color: gray')
        self.overlay_btn = QPushButton('오버레이')
        self.overlay_btn.setCheckable(True)
        self.overlay_btn.clicked.connect(lambda: self.overlay.signals.toggleSign.emit())
        self.overlay.signals.hideSign.connect( lambda hide: toggleButton(self.overlay_btn, not hide))
        vbox.addWidget(self.overlay_btn)

        
        self.move( systemResolution[0] - self.size().width(), 0)
        self.show()

        self.overlay_btn.click()

    def createActions(self):
        def loadData():
            self.landToolBar.clear()
            self.rokMiniMap.signals.readData.emit()
        self.loadAction = QAction(self)
        self.loadAction.setText('&LOAD')
        self.loadAction.triggered.connect(lambda: loadData())

        self.showLoggerAction = QAction(self)
        self.showLoggerAction.setText('&LOGGER')
        self.showLoggerAction.triggered.connect(self.showLoggingDialog)
    

    def createMenus(self):
        self.fileMenu = QMenu()
        self.fileMenu.setTitle('&File')
        self.fileMenu.setStyleSheet(    'QMenu::item{\
                                            color: rgb(0,0,255);\
                                        }')
        self.fileMenu.addAction(self.loadAction)

        self.widgetMenu = QMenu()
        self.widgetMenu.setTitle('&Widget')
        self.widgetMenu.addAction(self.showLoggerAction)    
    
    def createMenuBar(self):
        menubar = QMenuBar()
        menubar.setStyleSheet(    'QMenuBar::item{\
                                            color: rgb(0,0,255);\
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

    
    


      
