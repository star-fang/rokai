import json
from PyQt5.QtWidgets import QAction, QMainWindow, QWidget
from PyQt5.QtCore import QPointF, pyqtSignal, QObject, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from pathlib import Path

class TranslucentWidgetSignals(QObject):
    # SIGNALS
    CLOSE = pyqtSignal()

class TranslucentWidget(QWidget):
    def __init__(self, parent=None):
        super(TranslucentWidget, self).__init__(parent)

        # make the window frameless
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.fillColor = QColor(30, 30, 30, 30)
        self.penColor = QColor("#FF000000")

        self.SIGNALS = TranslucentWidgetSignals()

    def paintEvent(self, event):
        s = self.size()
        qp = QPainter()
        qp.begin(self)
        qp.setRenderHint(QPainter.Antialiasing, True)
        qp.setPen(self.penColor)
        qp.setBrush(self.fillColor)
        qp.drawRect(0, 0, s.width(), s.height())
        qp.end()

    def _onclose(self):
        print("Close")
        self.SIGNALS.CLOSE.emit()

class MapPalette(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._paintcallCnt = 0
        self.lands = None
        self.mapSize = [1200, 1200]
        self.fillColor = QColor(0, 0, 0, 255)
        self.penColor = QColor(0, 0, 0, 255)
    
    def setMapData( self, lands, mapSize):
        self.lands = lands
        self.mapSize = mapSize
    
    def paint(self):
        self.repaint()

    def paintEvent(self, event):
        
        if self.lands is not None:
            self._paintcallCnt += 1
            print( 'paint count: ' + str(self._paintcallCnt))
            s = self.size()
            lW = s.width()
            lH = s.height()

            screenRatio = lW / lH
            mapRatio = self.mapSize[0] / self.mapSize[1]

            if( screenRatio < mapRatio ): # rescale map to width
                rescaleRatio = lW / self.mapSize[0]
            else:
                rescaleRatio = lH / self.mapSize[1]
            
            qp = QPainter()
            qp.begin(self)
            qp.setRenderHint(QPainter.Antialiasing, True)
            qp.setPen(QPen(self.penColor,5))
            qp.setBrush(self.fillColor)
            for i in range( 0, len(self.lands) ):
                land, color = self.lands[i]
                qp.setBrush(color)
                trans = QTransform()
                rescaled = trans.scale(rescaleRatio, rescaleRatio).map(land)
                path = QPainterPath()
                path.addPolygon(rescaled)
                qp.fillPath(path, qp.brush())
                qp.drawPolygon(rescaled)
            qp.end()

class MiniMap(QMainWindow):
    def __init__(self, signId, amuSignals, threadPool, parent=None):
        QMainWindow.__init__(self, parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        widget = MapPalette(self)
        self.setCentralWidget(widget)

        self._popframe = None
        self._popflag = False

        self.createActions()
        self.createToolBar()

        self.amuSign = signId
        self.amuSignals = amuSignals
        amuSignals.hideSign.connect(self.toggleWindow)
        amuSignals.closeSign.connect(self.requestClose)
        amuSignals.coordinatesSign.connect(lambda t:print(t))

        self._closeflag = False

    def requestClose( self ):
        self._closeflag = True
        self.close()
    
    def toggleWindow( self, sign, hide):
        if sign == self.amuSign:
            if hide:
                self.hide()
            else:
                self.show()

    def createActions(self):
        self.loadAction = QAction(self)
        self.loadAction.setText('&load')

        self.loadAction.triggered.connect(self.readData)


    def createToolBar(self):
        toolBar = self.addToolBar("minimap")
        self.addToolBar(toolBar)

        toolBar.addAction(self.loadAction)


    '''
    from json to python
    object -> dict
    array -> list (not tuple!! in opposite cate, it's possible)
    string -> str
    number(int) -> int
    number(real) -> float
    true -> True
    false -> False
    null -> None
    '''
    
    def readData(self):
        source_path = Path(__file__).resolve()
        source_dir = source_path.parent

        
        file_dir = str(source_dir) + '/assets/vertex1947.json'
        print( file_dir )
        with open(file_dir,'r', encoding='utf-8') as src_json:
            src_python = json.load(src_json)
        
        if isinstance( src_python, list ):
            for i in range( 0, len(src_python) ):
                elmt = src_python[i]
                if isinstance(elmt, dict):
                    try:
                        name = str( elmt['name'] )
                        data = elmt['data']

                        if 'server' in elmt:
                            server = int( elmt['server'] )
                        else:
                            server = 0

                        if name == 'land' and isinstance(data, list):
                            print( 'server: ' + str(server))
                            if 'size' in elmt:
                                mapSize = elmt['size']
                            else:
                                print( 'size no exist')
                                mapSize = [1200, 1200]

                            lands = [] # list of 'j' polygons ( contains 'k' points) 
                            for j in range(0, len(data)):
                                land = data[j]

                                try:
                                    color = str(land['color'])
                                except KeyError:
                                    color = '#FFFFFF'
                                if isinstance(land, dict) and 'boundary' in land:
                                    boundaries = land['boundary']
                                    if isinstance(boundaries, list):
                                        points = tuple() # tuple of QPointF(s)
                                        for k in range(0, len(boundaries)):
                                            point = boundaries[k]
                                            if isinstance( point, dict): # {'x':100, 'y':200}
                                                p = list(point.values()) # [100, 200]
                                                if len(p) == 2:
                                                    points += (QPointF( p[0], p[1] ),)
                                        lands.append( (QPolygonF(points), QColor(color)) )
                            self.lands = lands
                            self.centralWidget().setMapData(lands,mapSize)
                            self.centralWidget().paint()
                        
                    except KeyError:
                        name = ''
                        data = None
                
    

    def resizeEvent(self, event):
        if self._popflag:
            self._popframe.move(0, 0)
            self._popframe.resize(self.width(), self.height())

    def _onpopup(self):
        self._popframe = TranslucentWidget(self.centralWidget())
        self._popframe.move(0, 0)
        self._popframe.resize(self.width(), self.height())
        self._popframe.SIGNALS.CLOSE.connect(self._closepopup)
        self._popflag = True
        self._popframe.show()

    def _closepopup(self):
        self._popframe.close()
        self._popflag = False

    def hideEvent(self, event):
        print( str(self.__class__.__name__) + ' disappeared')
        return super().hideEvent(event)
    
    def closeEvent(self, event):
        if self._closeflag is False:
            self.amuSignals.closedSign.emit( self.amuSign )
            self.hide()
            event.ignore()
        else:
            print( str(self.__class__.__name__) + ' closed')
            event.accept()