from PyQt5.QtWidgets import QAction, QMainWindow, QMenu, QMenuBar, QVBoxLayout, QWidget, QPushButton
from PyQt5.QtCore import QThreadPool, Qt
from sweeper import Sweeper
from minimap import MiniMap
from overlay import Overlay
from sweeperview import SweeperView

class RokAMU(QMainWindow):
      
    def __init__(self, systemResolution: list, parent = None):
        QMainWindow.__init__(self, parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.threadPool = QThreadPool( parent = self )
        self.threadPool.setMaxThreadCount(10)
        self.sweeper = Sweeper()
        self.resolutionOption = self.initResolutionOption( systemResolution )

        self.createSubWidgets()
        self.connectSubSignals()
        self.initUI(systemResolution)
        self.createActions()
        self.createMenus()
        self.createMenuBar()
        
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
        print( str(self.__class__.__name__) + ' closed')
        return super().closeEvent(e)

    def createSubWidgets( self ):
        self.sweeperView:SweeperView = SweeperView( self.sweeper, parent = self) # sub widget
        self.rokMiniMap:MiniMap = MiniMap( self.sweeper, parent = self ) # sub widget
        self.overlay:Overlay = Overlay( self.sweeper , parent = self) # sub window

    def connectSubSignals( self):
        self.sweeper.queuing.connect( lambda r: self.threadPool.start(r))

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
        self.loadAction = QAction(self)
        self.loadAction.setText('&LOAD')
        #self.loadAction.setFont( QFont('Arial', 16))
        self.loadAction.triggered.connect(lambda: self.rokMiniMap.signals.readData.emit())

        self.showLoggerAction = QAction(self)
        self.showLoggerAction.setText('&LOGGER')
        self.showLoggerAction.triggered.connect(lambda: self.sweeperView.signals.showLogger.emit())
    

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

    def createToolBar(self):
        toolBar = self.addToolBar("toolbar")
        self.addToolBar(toolBar)
        toolBar.addAction(self.loadAction)

    
    


      
