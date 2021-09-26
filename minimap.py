from json import load as json_load
from logging import getLogger
from re import sub as regexreplace
from math import cos, sin, radians, atan2, degrees
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QLineF, QObject, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPainterPath, QPen, QPolygonF, QTransform, QWheelEvent
from coloratura import Coloratura
from log import resource_path

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
    pointing = pyqtSignal(str)

class MiniMap(QWidget):

    def __init__(self, coloratura: Coloratura=None, parent=None):
        super(MiniMap, self).__init__(parent)
        #self.setAttribute(Qt.WA_TranslucentBackground)

        self.setMouseTracking(True)
        if coloratura is not None:
            self.coloratura = coloratura
            self.coloratura.changeLocation.connect( self.evalLocation )
        self.signals = MiniMapSignals()
        self.signals.readData.connect(self.readData)
        self.signals.landChecked.connect(self.checkLand)
        self.logger = getLogger()

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
        self.setMinimumWidth(300)
        self.show()

    def checkLand(self, id:int, checked:bool ) -> None:
        if id in self.lands.keys():
            land = self.lands[id]
            if land is not None and isinstance(land, dict):
                land['checked'] = checked

    def evalLocation( self, loc:tuple, deg:float ) -> None:
        self.clearRect()
        server, x, y = loc
        if regexreplace('\D','',self.server) in str(server):
            checkedLandsList = list(filter( lambda land: isinstance(land,dict) and land.get('checked', False),self.lands.values()))
            for land in checkedLandsList:

                try:
                    if isinstance( land, dict ):
                        landName = land.get('name')
                        nameKor = landName.get('kor') if isinstance( landName, dict ) else None
                        boundary:QPolygonF = land.get('boundary')
                        if rayCastingCheck( boundary, float(y), float(x)):
                            self.logger.debug( f'x{x}, y{y} is in {nameKor}')

                            if self.targetPoint is not None:
                                targetX = self.targetPoint.x()
                                targetY = self.targetPoint.y()
                                rad = atan2((targetY - y),(targetX - x))
                                deg = degrees(rad) % 360
                                if deg < 0:
                                    deg += 360
                            else:
                                rad = radians(deg)
                                boundingRect = boundary.boundingRect()
                                beyondX = x + (boundingRect.width()+30) * cos(rad)
                                beyondY = y + (boundingRect.height()+30 ) * sin(rad)
                                self.targetPoint = intersctionPoint(boundary, QLineF(x,y,beyondX,beyondY))

                            arrowXfactor = 25 * cos(rad)
                            arrowYfactor = 25 * sin(rad)
                            lwingXfactor = 50 * cos(radians(210 - deg))
                            lwingYfactor = 50 * sin(radians(30 - deg))
                            rwingXfactor = 50 * cos(radians(510 - deg))
                            rwingYfactor = 50 * sin(radians(330 - deg))

                            if rayCastingCheck( boundary, y + arrowYfactor, x + arrowXfactor ):
                                self.logger.debug(f'next xy : bounded')
                                self.arrow.append(x)
                                self.arrow.append(y)
                                self.arrow.append(arrowXfactor)
                                self.arrow.append(arrowYfactor)
                                self.arrow.append(lwingXfactor)
                                self.arrow.append(lwingYfactor)
                                self.arrow.append(rwingXfactor)
                                self.arrow.append(rwingYfactor)
                                self._arrowflag = True
                                self.repaint()
                                self.coloratura.evalLocation.emit(deg)
                                return
                            else:
                                self.targetPoint = None
                                self.logger.debug(f'next xy : unbounded')
                            break
                except KeyError:
                    pass
            
        self.targetPoint = None
        self.repaint()
        self.coloratura.evalLocation.emit(-1.0)
  
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

    def wheelEvent(self, evt: QWheelEvent) -> None:
        numPx = evt.pixelDelta()
        if not numPx.isNull():
            print( f'num pixels: {numPx}')
        else:
            numAngle = evt.angleDelta()
            if not numAngle.isNull():
                numDeg = numAngle / 8
                numSteps = numDeg / 15
                print( f'num steps: {numSteps}')
        evt.accept()
        return super().wheelEvent(evt)

    def mouseMoveEvent(self, evt: QMouseEvent) -> None:
        if self._drawflag:
            self.signals.pointing.emit(f'x:{evt.x()}, y:{evt.y()}')
            evt.accept()
        return super().mouseMoveEvent(evt)
        
    def paintEvent(self, evt:QPaintEvent) -> None:

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
                    x, y, xf, yf, lxf, lyf, rxf, ryf = self.arrow
                    middleF = QPointF( x, y)
                    headF = QPointF( x + xf, y + yf)
                    leftF = QPointF( x + xf + lxf, y + yf + lyf )
                    rightF = QPointF( x + xf + rxf, y + yf + ryf )
                    arrowF:QPolygonF = transScale.map(QPolygonF((middleF, leftF, headF, rightF)))
                    arrowPath = QPainterPath()
                    arrowPath.addPolygon(arrowF)

                    qp.fillPath(arrowPath, QColor(255,0,0,255))

                    
                except TypeError as e:
                    self.logger.debug( f'exception while drawing: {e}')
            
            if self.targetPoint is not None:
                qp.setPen(QPen(QColor(0,0,255,255),4))
                targetRect = QPolygonF(transScale.map(QPolygonF( \
                    QRectF(self.targetPoint.x()-20.0, \
                        self.targetPoint.y()-20.0,40.0,40.0) ))).boundingRect()
                
                qp.drawArc(targetRect, 0, 360*16)
            qp.end()
    
    def clearData(self) -> None:
        self._drawflag = False
        self.lands.clear()
        self.mapSize.clear()

    def readData(self) -> None:
        self.clearData()
        
        name_dict = dict()
        with open( resource_path( 'name.json' ),'r', encoding='utf-8') as name_json:
            name_python = json_load(name_json)
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
        file_dir = resource_path( 'vertex1947.json' )
        self.logger.info( f'{file_dir} loaded' )
        with open(file_dir,'r', encoding='utf-8') as src_json:
            src_python = json_load(src_json)  
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