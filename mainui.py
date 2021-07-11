from PyQt5.QtWidgets import QGridLayout, QMainWindow, QProgressBar, QStackedLayout, QTextEdit, QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QListWidget
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from tracker import Tracker
import pygetwindow
import re
from sweeper import Sweeper, Worker

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
       
class SweeperView(QWidget):
    def __init__(self,parent=None):
        QWidget.__init__(self, parent)

        self.initUi()

    def initUi(self):
        palette = self.palette()
        palette.setColor(palette.Background,Qt.white)
        self.setPalette(palette)

        self.screenView = QLabel()
        self.templateView = QLabel()
        self.stateText = QTextEdit('aaa')
        self.resolutionText = QLabel('640 X 480')

        self.tm_ratioBar = QProgressBar()
        self.tm_ratioBar.setMinimum(0)
        self.tm_ratioBar.setMaximum(100)
        self.tm_angleBar = QProgressBar()
        self.tm_angleBar.setMinimum(0)
        self.tm_angleBar.setMaximum(360)
        #self.screenView.setFixedSize( self.width, self.height)
        #self.conditionLabel.setFixedHeight(30)

        layout = QGridLayout(self)

        self.setFixedSize(480,360)

        self.w, self.h = self.geometry().getRect()[2:]
        self.screenView.setFixedSize( self.w * 2 // 3, self.h * 2 // 3)

        layout.addWidget(self.screenView,0, 0, 3, 4)
        layout.addWidget(self.resolutionText, 3, 0, 1, 4)
        layout.addWidget(QLabel('화면 인식'), 0, 4, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stateText,1, 4, 3, 2)
        layout.addWidget(self.templateView, 5, 0, 2, 2)
        layout.addWidget(QLabel('ratio:'), 5, 2, 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.tm_ratioBar, 5, 4, 2, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(QLabel('rotation:'), 6, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.tm_angleBar, 6, 4, 2, 1, alignment=Qt.AlignmentFlag.AlignLeft)

    

    def setScreenImage(self, mat):
        pixmap = mat2QPixmap( mat )
        sWidth,sHeight = self.screenView.geometry().getRect()[2:]
        
        if bool( sWidth > pixmap.width() ) and bool( sHeight > pixmap.height() ):
            self.screenView.setPixmap( pixmap )
        elif pixmap.width() * 2 > pixmap.height() * 3:
            self.screenView.setPixmap( pixmap.scaledToWidth( self.w * 2 // 3) )
        else:
            self.screenView.setPixmap( pixmap.scaledToHeight( self.h * 3 // 7 ) )

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

class RokAMU(QMainWindow):

    Button_DETECT = 0
    Button_CRACK = 1
    Button_FIND = 2
    def __init__(self, systemResolution, ocr, parent = None):
        QMainWindow.__init__(self, parent)

        
        self.tracker = None
        self.ocr = ocr

        mainWidget = QWidget(self)
        self.setCentralWidget(mainWidget)
        
        
        #x1, y1, x2, y2
        #() tuple : immutable , [] list : mutable
        self.resolutionOption = self.initResolutionOption( systemResolution )
        self.sweeper = Sweeper( ocr ) # default TM_option
        self.sweeper.setDetectionPart([2,2,self.resolutionOption[0]//self.resolutionOption[2], self.resolutionOption[1]// self.resolutionOption[2]])

        self.initUI()
        
    def initResolutionOption(self, resolution, marginRate = 0.7):
        detectionPartLimit = (2*resolution[0]//3, 2*resolution[1]//3)
        if bool( detectionPartLimit[0]*marginRate > 800 ) and bool( detectionPartLimit[1]*marginRate > 600):
            return (800,600,marginRate)
        elif bool( detectionPartLimit[0]*marginRate > 640 ) and bool( detectionPartLimit[1]*marginRate > 480):
            return (640,480,marginRate)
        else:
            return (480,360,marginRate)

    def initUI(self):

        centralWidget = self.centralWidget()
        vbox = QVBoxLayout(centralWidget)
  
        # Horizontal box layout
        hbox_head = QHBoxLayout()

        desc_label = QLabel()
        desc_label.setFixedHeight(30)
        hbox_head.addWidget(desc_label)
        self.label = desc_label
        
        refresh_btn = QPushButton('재탐색', centralWidget)
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self.refresh)
        hbox_head.addWidget(refresh_btn)

        vbox.addLayout(hbox_head)

        # Create QlistWidget Object
        self.listWidget = QListWidget(centralWidget)
        self.listWidget.setFixedHeight(100)
        vbox.addWidget(self.listWidget)  
  
        # Set position & size
        #self.setWindowFlags(Qt.FramelessWindowHint)
        self.move(self.resolutionOption[0]//self.resolutionOption[2], 0)
        #self.setFixedWidth(self.screenSize[0]//3)
  
        # On item selected
        self.listWidget.itemClicked.connect(self.onItemSelected)
        # Display QlistWidget
        #self.setWindowTitle('')

        self.sweeperView = SweeperView(centralWidget)
        vbox.addWidget(self.sweeperView)

        self.state_btn = QPushButton('상태 감지',centralWidget)
        self.state_btn.setFixedHeight(30)
        self.state_btn.clicked.connect( lambda: self.onButtonCLicked(self.Button_DETECT))

        self.find_btn = QPushButton('루비 찾기 테스트',centralWidget)
        self.find_btn.setFixedHeight(30)
        self.find_btn.clicked.connect( lambda: self.onButtonCLicked( self.Button_FIND))
        self.find_btn.setEnabled(False)

        self.crack_btn = QPushButton('인증 풀기 테스트',centralWidget)
        self.crack_btn.setFixedHeight(30)
        self.crack_btn.clicked.connect( lambda: self.onButtonCLicked( self.Button_CRACK))
        self.crack_btn.setEnabled(False)

        vbox.addWidget(self.state_btn)
        vbox.addWidget(self.find_btn)
        vbox.addWidget(self.crack_btn)

        hbox_foot = QHBoxLayout()
        stop_btn = QPushButton('정지',centralWidget)
        stop_btn.clicked.connect(self.onStopButtonClicked)
        hbox_foot.addWidget(stop_btn)

        pause_btn = QPushButton('일시 정지',centralWidget)
        #pause_btn.setShortcut('Alt+F8')
        pause_btn.clicked.connect(self.onPauseButtonClicked)
        hbox_foot.addWidget(pause_btn)

        start_btn = QPushButton('시작',centralWidget)
        start_btn.clicked.connect(self.onStartButtonClicked)
        hbox_foot.addWidget(start_btn)
        vbox.addStretch(1)
        vbox.addLayout(hbox_foot)
        self.refresh()

    def onWorkFinished( self, work ):
        if( work == Worker.WORK_CRACK ):
            print('crack work finished')
            self.sweeperView.setRatioVal(0)
            self.sweeperView.setRatioVal(0)
        elif( work == Worker.WORK_DETECT_STATE ):
            print('screen recognized')
            self.state_btn.setEnabled(True)
        elif( work == Worker.WORK_RUBY ):
            print('find ruby work finished')

    def onButtonCLicked( self, which ):
        work = -1
        if which == self.Button_DETECT:
            self.state_btn.setEnabled(False)
            work = Worker.WORK_DETECT_STATE
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

    def onItemSelected(self, item):
        title = item.text()
        players = pygetwindow.getWindowsWithTitle(title)
        if( len(players) > 0 ):
            player = players[0]
            #print(str((self.resolutionOption[0]//self.resolutionOption[2],self.resolutionOption[1]//self.resolutionOption[2])))
            player.resizeTo(int(self.resolutionOption[0]/self.resolutionOption[2]),int(self.resolutionOption[1]/self.resolutionOption[2]))
            player.moveTo(0,0)
            player.activate()
            self.label.setText('선택된 프로그램:' + title)
        else:
            self.refresh()

    def makeWorkerThread( self, work ):

        self.worker = Worker( self.sweeper, parent = None, work=work )

        thread = QThread(self.centralWidget())
        self.worker.moveToThread(thread)

        self.worker.state.connect(self.onStateChanged)
        self.worker.stateReport.connect(self.onStateReport)
        self.worker.changeScreen.connect( lambda mat:self.sweeperView.setScreenImage(mat) )
        self.worker.changeTemplate.connect( lambda mat:self.sweeperView.setTemplateImage(mat) )
        self.worker.tm_ratio.connect( lambda v:self.sweeperView.setRatioVal(v) )
        self.worker.tm_rotate.connect( lambda v:self.sweeperView.setAngleVal(v) )

        self.worker.finished.connect(thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)

        thread.started.connect(self.worker.run)
        thread.finished.connect(thread.deleteLater)

        return thread

    def onStateReport(self, stateReport):
        self.sweeperView.setStateText(stateReport)

    def onStateChanged(self, state):
        if( state == Sweeper.STATE_NORMAL ):
            self.crack_btn.setEnabled(False)
            self.find_btn.setEnabled(True)
        elif( state == Sweeper.STATE_CHECK_ROBOT2 ):
            self.find_btn.setEnabled(False)
            self.crack_btn.setEnabled(True)
        else:
            self.find_btn.setEnabled(False)
            self.crack_btn.setEnabled(False)

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
    
    def onPauseButtonClicked( self ):
        if self.tracker is not None:
            self.tracker.pause()

    def onStopButtonClicked( self ):
        if self.tracker is not None:
            self.tracker.stop()
    
    def refresh(self):
        self.listWidget.clear()
        print('operating program list refreshed')
        titles = pygetwindow.getAllTitles()
        regex = re.compile('^(?!python.*$)^(?!Program.*$)^(?!Microsoft.*$)(?=\S).*')
        titles = list(filter(regex.match, titles))
        self.listWidget.addItems(titles)
        self.label.setText('실행중인 프로그램 목록: 앱플레이어를 선택하세요')
        #self.listWidget.show()


      
