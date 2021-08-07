import json
from re import sub as regexreplace
from math import cos, sin, radians, pi
from PyQt5.QtWidgets import  QWidget
from PyQt5.QtCore import QLineF, QObject, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from pathlib import Path
from sweeper import Sweeper
from log import makeLogger
def intersctionPoint( boundary:QPolygonF, line: QLineF):
    bLen = boundary.count()
    for i in range(bLen):
        edge = QLineF( boundary.at(i),boundary.at((i+1)% bLen) )
        itype, point = edge.intersects(line)
        if itype == QLineF.IntersectType.BoundedIntersection:
            return point
    return None

def rayCastingCheck( boundary:QPolygonF, lat:float, lng:float):
    if boundary is None:
        return False
    count  = 0
    bLen = boundary.count()
    for i in range(0, bLen):
        vertex1:QPointF = boundary.at(i)
        vertex2:QPointF = boundary.at( (i+1) % bLen )
        if vertex1.x() == vertex2.x() and vertex2.x() == lng:
            if max( vertex1.y(), vertex2.y() ) > lat and min( vertex1.y(), vertex2.y() ) < lat: return True
        elif vertex1.y() == vertex2.y() and vertex2.y() == lat:
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
    #amu -> minimap
    readData = pyqtSignal()
    landChecked = pyqtSignal(int, bool)

    #minimap -> amu
    landLoaded = pyqtSignal(int, dict)

class MiniMap(QWidget):
    def __init__(self, logSignal, sweeper: Sweeper, parent=None):
        super(MiniMap, self).__init__(parent)
        #self.setAttribute(Qt.WA_TranslucentBackground)
        self.sweeper = sweeper
        self.sweeper.changeLocation.connect( self.evalLocation )
        self.signals = MiniMapSignals()
        self.signals.readData.connect(self.readData)
        self.signals.landChecked.connect(self.checkLand)
        self.logger = makeLogger(logSignal.logInfo, 'mini')

        self._paintcallCnt = 0
        self._drawflag = False
        self.lands = dict()
        self.mapSize = list()
        self.server:str = ''
        self.viewRect = list()
        self.arrow = list() 
        self._rectflag = False
        self._arrowflag = None
        self.targetPoint:QPointF = None

        self.initColor()

        self.setMinimumHeight(300)
        self.show()

    def checkLand(self, id:int, checked:bool ):
        if id in self.lands.keys():
            land = self.lands[id]
            if land is not None and isinstance(land, dict):
                land['checked'] = checked

    def evalLocation( self, loc:tuple, deg:float ):
        self.clearRect()
        server, x, y = loc
        if regexreplace('\D','',self.server) in str(server):
            checkedLandsList = list(filter( lambda land: isinstance(land,dict) and land.get('checked', False),self.lands.values()))
            for land in checkedLandsList:

                try:
                    if isinstance( land, dict ):
                        landName = land.get('name')
                        if isinstance( landName, dict ):
                            name = landName.get('kor')
                            self.logger.debug( f'check:{str(name)}')
                            boundary:QPolygonF = land.get('boundary')

                        if rayCastingCheck( boundary, float(y), float(x)):
                            self.logger.debug( f'x{x}, y{y} is valid position')
                            rad = radians(deg)
                            self.logger.debug( f'deg={deg}, rad={rad}')
                            boundingRect = boundary.boundingRect()
                            nextX = x + (boundingRect.width()+30) * cos(rad)
                            nextY = y + (boundingRect.height()+30 ) * sin(rad)

                            self.targetPoint = intersctionPoint(boundary, QLineF(x,y,nextX,nextY))


                            arrowXfactor = 50 * cos(rad)
                            arrowYfactor = 50 * sin(rad)
                            lwingXfactor = 30 * cos(radians(225 - deg))
                            lwingYfactor = 30 * sin(radians(45-deg))
                            rwingXfactor = 30 * cos(radians(495 - deg))
                            rwingYfactor = 30 * sin(radians(315 - deg))
                            self.logger.debug(f'next: x{nextX}, y{nextY}')
                            

                            lWingX = x + arrowXfactor + lwingXfactor
                            lWingY = y + arrowYfactor + lwingYfactor

                            rWingX = x + arrowXfactor + rwingXfactor
                            rWingY = y + arrowYfactor + rwingYfactor

                            self.arrow.append(x)
                            self.arrow.append(y)
                            self.arrow.append(arrowXfactor)
                            self.arrow.append(arrowYfactor)
                            self.arrow.append(lWingX)
                            self.arrow.append(lWingY)
                            self.arrow.append(rWingX)
                            self.arrow.append(rWingY)


                            
                            self.sweeper.evalLocation.emit(-1.0)
                            #self.viewRect.append( x - 15 )
                            #self.viewRect.append( y - 10 )
                            #self.viewRect.append( 30 )
                            #self.viewRect.append( 20 )
                            break
                except KeyError:
                    pass
            
        self._arrowflag = True
        self.repaint()
  
    def initColor(self):
        self.penColor = QColor(0, 0, 0, 255)
        self.rectFillColor = QColor(255, 255, 0, 255)
        self.rectPenColor = QColor(255, 255, 255, 255)
        self.arrowColor = QColor(255, 0, 0, 255)
  
    def clearRect(self):
        self._arrowflag = False
        self.viewRect.clear()
        self.arrow.clear()
        self.repaint()
        
    def paintEvent(self, event):

        if self._drawflag and self.lands is not None and len(self.lands) > 0:
            self._paintcallCnt += 1
            self.logger.debug( f'paint count:{self._paintcallCnt}')
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
            transScale = QTransform().scale(rescaleRatio, rescaleRatio)
            for id, land in self.lands.items():
                if isinstance(land, dict):
                    boundary = land.get('boundary', QPointF())
                    color = land.get('color',QColor('#FFFFFF'))
                    qp.setBrush(color)
                    
                    rescaled = transScale.map(boundary)
                    path = QPainterPath()
                    path.addPolygon(rescaled)
                    qp.fillPath(path, qp.brush())
                    qp.drawPolygon(rescaled)

            


            if self._arrowflag and len(self.arrow) == 8:
                qp.setPen(QPen(self.arrowColor,3))
                try:
                    #rationalArrow = [e * 2 for e in ]
                    x, y, xf, yf, lx, ly, rx, ry = self.arrow
                    startPointF = QPointF( x - xf, y - yf)
                    endPointF = QPointF( x + xf, y + yf)
                    leftPointF = QPointF( lx, ly)
                    rightPointF = QPointF( rx, ry)
                    middleRect = QPolygonF(transScale.map(QPolygonF( QRectF(x-15.0, y-15.0,30.0,30.0) ))).boundingRect()

                    qp.setPen(QPen(QColor(255,255,255,200),4))
                    qp.drawLine( transScale.map(QLineF(startPointF, endPointF)))
                    qp.drawLine( transScale.map(QLineF( endPointF, leftPointF)))
                    qp.drawLine( transScale.map(QLineF( endPointF, rightPointF)))
                    qp.setPen(QPen(QColor(255,0,0,255),3))
                    qp.drawArc(middleRect, 0, 360*16)

                    
                except TypeError as e:
                    self.logger.debug( f'exception while drawing: {e}')
            
            if self.targetPoint is not None:
                qp.setPen(QPen(QColor(0,0,255,255),4))
                targetRect = QPolygonF(transScale.map(QPolygonF( \
                    QRectF(self.targetPoint.x()-20.0, \
                        self.targetPoint.y()-20.0,40.0,40.0) ))).boundingRect()
                
                qp.drawArc(targetRect, 0, 360*16)
            qp.end()
    
    def clearData(self):
        self._drawflag = False
        self.lands.clear()
        self.mapSize.clear()

    def readData(self):
        self.clearData()
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
        self.logger.info( f'{file_dir} loaded' )
        with open(file_dir,'r', encoding='utf-8') as src_json:
            src_python = json.load(src_json)  
            if isinstance( src_python, list ):
              for i in range( 0, len(src_python) ):
                    elmt = src_python[i]
                    if isinstance(elmt, dict):
                        try:
                            name = str( elmt.get('name','') )
                            if name == 'land':
                                self.server = str( elmt.get('server') )
                                data:list = elmt.get('data',list())
                                self.mapSize = elmt.get('size',[1200,1200])
                                #= [] # list of 'j' polygons ( contains 'k' points)
                                for j in range(0, len(data)):
                                    land = data[j]
                                    if isinstance(land, dict) and 'boundary' in land:
                                        color = land.get('color', '#FFFFFF')
                                        landId = land.get('id', 129000+j)
                                        landName:dict = name_dict.get(land.get('nameId',-1),dict())
                                        boundaries = land['boundary']
                                        if isinstance(boundaries, list):
                                            points = tuple() # tuple of QPointF(s)
                                            for k in range(0, len(boundaries)):
                                                point = boundaries[k]
                                                if isinstance( point, dict): # {'x':100, 'y':200}
                                                    p = list(point.values()) # [100, 200]
                                                    if len(p) == 2:
                                                        points += (QPointF( p[0], p[1] ),)
                                            self.lands[landId] = {'boundary':QPolygonF(points), \
                                                                  'color':QColor(color),\
                                                                  'name': landName}
                                            self.signals.landLoaded.emit(landId, landName)
                                self._drawflag = True
                                self.repaint()
                            break
                        except Exception:
                            self.logger.debug('exception while read data',stack_info=True)
    '''from json to python
    object -> dict
    array -> list (not tuple!! in opposite cate, it's possible)
    string -> str
    number(int) -> int
    number(real) -> float
    true -> True
    false -> False
    null -> None'''