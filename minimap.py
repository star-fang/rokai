import json
from PyQt5.QtWidgets import  QWidget
from PyQt5.QtCore import QObject, QPointF, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from pathlib import Path
from sweeper import Sweeper

def rayCastingCheck( land:QPolygonF, lat:float, lng:float):
    count  = 0
    
    bLen = land.count()
    for i in range(0, bLen):
        vertex1:QPointF = land.at(i)
        vertex2:QPointF = land.at( (i+1) % bLen )
        if vertex1.x() == vertex2.x and vertex2.x() == lng:
            if max( vertex1.y(), vertex2.y() ) > lat and min( vertex1.y(), vertex2.y() ) < lat: return True
        elif vertex1.y() == vertex2.y and vertex2.y == lat:
            if max( vertex1.x(), vertex2.x() ) > lng and min( vertex1.x(), vertex2.x() ) > lng: return True
        if west( vertex1, vertex2, lng, lat):
            count += 1
    return bool( count % 2 == 1 )

def west( v1:QPointF, v2:QPointF, x:float, y:float ):
    if v1.y() <= v2.y():
        if y <= v1.y() or y > v2.y() or x >= v1.x() and x >= v2.x():
            return False
        elif x < v1.x() and x < v2.x():
            return True
        else:
            return bool( ( y - v1.y() ) / ( x - v1.x() ) > ( v2.y() - v1.y() ) / ( v2.x() - v1.x() ) )
    else:
        return west( v2, v1, x, y)

class MiniMapSignals(QObject):
    readData = pyqtSignal()

class MiniMap(QWidget):
    def __init__(self, sweeper: Sweeper, parent=None):
        super(MiniMap, self).__init__(parent)
        #self.setAttribute(Qt.WA_TranslucentBackground)
        self.sweeper = sweeper
        self.sweeper.changeLocation.connect( self.drawHudLocRect )
        self.signals = MiniMapSignals()
        self.signals.readData.connect(self.readData)

        self._paintcallCnt = 0
        self._drawflag = False
        self.lands = None
        self.mapSize = [1200, 1200]
        self.server = 1947
        self.viewRect = None
        self._rectflag = False

        self.initColor()

        self.setMinimumHeight(300)
        self.show()    

    def drawHudLocRect( self, t ):
        server, x, y = t
        if hasattr(self, 'lands') and self.lands is not None and server == self.server:
            for land in self.lands:
                try:
                    if rayCastingCheck( land['boundary'], float(y), float(x)):
                        name_kr = str(land['name']['kor'])
                        print( f'aa{name_kr}' )
                        break
                except KeyError:
                    pass
            self.viewRect = (x-15,y-10,30,20)
            self._rectflag = True
            self.repaint()
  
    def initColor(self):
        self.penColor = QColor(0, 0, 0, 255)
        self.rectFillColor = QColor(255, 255, 0, 255)
        self.rectPenColor = QColor(255, 255, 255, 255)
  
    def clearMap(self):
        self._rectflag = False
        self.viewRect = None
        self.repaint()

    def setMapData( self, lands, mapSize):
        self.lands = lands
        self.mapSize = mapSize
        self._drawflag = True
        self.repaint()
    
    def paintEvent(self, event):

        if self._drawflag and self.lands is not None:
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
            qp.translate(self.rect().bottomLeft())
            qp.scale(1.0,-1.0)
            qp.setRenderHint(QPainter.Antialiasing, True)
            qp.setPen(QPen(self.penColor,5))
            for i in range( 0, len(self.lands) ):
                land = self.lands[i]['boundary']
                color = self.lands[i]['color']
                qp.setBrush(color)
                trans = QTransform()
                rescaled = trans.scale(rescaleRatio, rescaleRatio).map(land)
                path = QPainterPath()
                path.addPolygon(rescaled)
                qp.fillPath(path, qp.brush())
                qp.drawPolygon(rescaled)

            if self._rectflag and self.viewRect is not None:
                qp.setPen(self.rectPenColor)
                qp.setBrush(self.rectFillColor)
                x, y, w, h = self.viewRect
                rx = int( x*rescaleRatio)
                ry = int( y*rescaleRatio)
                rw = int( w*rescaleRatio)
                rh = int( h*rescaleRatio)
                qp.drawRect(rx,ry,rw,rh)
            qp.end()
             
    def readData(self):
        source_path = Path(__file__).resolve()
        source_dir = source_path.parent

        name_dir = str(source_dir) + '/assets/name.json'

        name_dict = dict()
        with open(name_dir,'r', encoding='utf-8') as name_json:
            name_python = json.load(name_json)
            if isinstance( name_python, list):
                for elmt in name_python:
                    if isinstance( elmt, dict):
                        try:
                            id = elmt['id']
                            name_eng = elmt['eng'] if 'eng' in elmt else ''
                            name_kor = elmt['kor'] if 'kor' in elmt else ''
                            name_dict[id] = {'eng':name_eng, 'kor':name_kor}
                        except KeyError:
                            pass
        file_dir = str(source_dir) + '/assets/vertex1947.json'
        print( f'{file_dir} loaded' )
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
                                server = 1947

                            if name == 'land' and isinstance(data, list):
                                print( 'server: ' + str(server))
                                self.server = server
                                if 'size' in elmt:
                                    mapSize = elmt['size']
                                else:
                                    print( 'size no exist')
                                    mapSize = [1200, 1200]

                                lands = [] # list of 'j' polygons ( contains 'k' points) 
                                for j in range(0, len(data)):
                                    land = data[j]

                                    if isinstance(land, dict) and 'boundary' in land:
                                        color = str(land['color']) if 'color' in land else '#FFFFFF'
                                        landName = dict()
                                        if 'nameId' in land:
                                            nameId = int(land['nameId'])
                                            if nameId in name_dict:
                                                landName = name_dict[ nameId ]
                                        boundaries = land['boundary']
                                        if isinstance(boundaries, list):
                                            points = tuple() # tuple of QPointF(s)
                                            for k in range(0, len(boundaries)):
                                                point = boundaries[k]
                                                if isinstance( point, dict): # {'x':100, 'y':200}
                                                    p = list(point.values()) # [100, 200]
                                                    if len(p) == 2:
                                                        points += (QPointF( p[0], p[1] ),)
                                            lands.append( {'boundary':QPolygonF(points), 
                                                            'color':QColor(color), 
                                                            'name': landName} )
                                self.lands = lands
                                self.setMapData( lands, mapSize )
                        
                        except KeyError:
                            pass
    '''from json to python
    object -> dict
    array -> list (not tuple!! in opposite cate, it's possible)
    string -> str
    number(int) -> int
    number(real) -> float
    true -> True
    false -> False
    null -> None'''