from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QListWidget
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from tracker import Tracker
import pygetwindow
import time
import re

def image2pixmap(im):
    if hasattr(im, 'mode'):
        if im.mode == "RGB":
            r, g, b = im.split()
            im = Image.merge("RGB", (b, g, r))
        elif  im.mode == "RGBA":
            r, g, b, a = im.split()
            im = Image.merge("RGBA", (b, g, r, a))
        elif im.mode == "L":
            im = im.convert("RGBA")
    else: # for np array
        im = Image.fromarray(im)

    # Bild in RGBA konvertieren, falls nicht bereits passiert
    im2 = im.convert("RGBA")
    data = im2.tobytes("raw", "RGBA")
    qim = QImage(data, im.size[0], im.size[1], QImage.Format_ARGB32)
    pixmap = QPixmap.fromImage(qim)
    return pixmap


class SweeperView(QVBoxLayout):
    def __init__(self, width, height):
        super().__init__()
        self.width = width
        self.height = height

    def initUi(self):
        self.imageView = QLabel()
        self.conditionLabel = QLabel()
        self.imageView.setFixedSize( self.width, self.height)
        self.conditionLabel.setFixedHeight(30)
        self.addWidget(self.imageView)
        self.addWidget(self.conditionLabel)
        #self.imageView.setPixmap( QPixmap('C:/Users/clavi/Downloads/ruby/template.png') )

    def setImage(self, img):
        pixmap = image2pixmap(img)
        if pixmap.width() > pixmap.height():
            self.imageView.setPixmap( pixmap.scaledToWidth( int(self.width * 0.95) ) )
        else:
            self.imageView.setPixmap( pixmap.scaledToHeight( int(self.height * 0.95) ) )

    def setText(self, text):
        self.conditionLabel.setText(text)

class RokAU(QWidget):
    def __init__(self, screenSize, ocr, sweeper):
        super().__init__()
        self.tracker = None
        self.ocr = ocr
        self.sweeper = sweeper
        self.screenSize = screenSize
        self.pw = 2*self.screenSize[0]//3
        self.ph = 2*self.screenSize[1]//3
        self.bbox = [0, 0, self.pw,self.ph] 
        #x1, y1, x2, y2
        #() tuple : immutable , [] list : mutable
        self.initUI()

    def initUI(self):
        # Vertical box layout
        vbox = QVBoxLayout(self)
  
        # Horizontal box layout
        hbox_head = QHBoxLayout()

        desc_label = QLabel()
        desc_label.setFixedHeight(30)
        hbox_head.addWidget(desc_label)
        self.label = desc_label
        
        refresh_btn = QPushButton('재탐색', self)
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self.refresh)
        hbox_head.addWidget(refresh_btn)

        vbox.addLayout(hbox_head)

        # Create QlistWidget Object
        self.listWidget = QListWidget(self)
        self.listWidget.setFixedHeight(100)
        vbox.addWidget(self.listWidget)  

        self.setLayout(vbox)
  
        # Set position & size
        #self.setWindowFlags(Qt.FramelessWindowHint)
        self.move(2*self.screenSize[0]//3, 0)
        self.setFixedWidth(self.screenSize[0]//3)
  
        # On item selected
        self.listWidget.itemClicked.connect(self.onItemSelected)
        # Display QlistWidget
        #self.setWindowTitle('')

        sweeperView = SweeperView( self.screenSize[0]//3, self.screenSize[1]//3 )
        sweeperView.initUi()
        vbox.addLayout(sweeperView)
        self.sweeper.setView(sweeperView)

        screen_btn = QPushButton('화면 감지',self)
        screen_btn.setFixedHeight(30)
        screen_btn.clicked.connect(self.onScreenButtonClicked)

        find_btn = QPushButton('루비 찾기 테스트',self)
        find_btn.setFixedHeight(30)
        find_btn.clicked.connect(self.onFindButtonClicked)

        crack_btn = QPushButton('인증 풀기 테스트',self)
        crack_btn.setFixedHeight(30)
        crack_btn.clicked.connect(self.onCrackButtonClicked)

        vbox.addWidget(find_btn)
        vbox.addWidget(screen_btn)
        vbox.addWidget(crack_btn)

        hbox_foot = QHBoxLayout()
        stop_btn = QPushButton('정지',self)
        stop_btn.clicked.connect(self.onStopButtonClicked)
        hbox_foot.addWidget(stop_btn)

        pause_btn = QPushButton('일시 정지',self)
        #pause_btn.setShortcut('Alt+F8')
        pause_btn.clicked.connect(self.onPauseButtonClicked)
        hbox_foot.addWidget(pause_btn)

        start_btn = QPushButton('시작',self)
        start_btn.clicked.connect(self.onStartButtonClicked)
        hbox_foot.addWidget(start_btn)
        vbox.addStretch(1)
        vbox.addLayout(hbox_foot)

        self.show()
        time.sleep(0.5)
        self.refresh()
    
    def onItemSelected(self, item):
        title = item.text()
        players = pygetwindow.getWindowsWithTitle(title)
        if( len(players) > 0 ):
            #self.listWidget.hide()
            player = players[0]
            player.resizeTo(self.pw,self.ph)
            player.moveTo(0,0)
            time.sleep(0.2)
            player.activate()
            #if playerActive == False:
            #pywinauto.application.Application().connect(handle=player._hWnd).top_window().set_focus()
            self.label.setText('선택된 프로그램:' + title)
            self.sweeper.detectScreen( self.pw, self.ph, self.bbox)
        else:
            self.refresh()

    def onFindButtonClicked(self):
        #print('find button clicked')
        self.sweeper.findRuby(self.bbox)

    def onCrackButtonClicked(self):
        #print('find button clicked')
        self.sweeper.crackRobotCheck(self.bbox)
    
    def onScreenButtonClicked(self):
        self.sweeper.detectScreen( self.pw, self.ph, self.bbox)
        #print('check bbox:' + str(self.bbox))

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


      
