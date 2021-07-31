import json
from PyQt5.QtWidgets import QAction, QMainWindow, QWidget
from PyQt5.QtCore import QPointF, pyqtSignal, QObject, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from pathlib import Path
from sweeper import Sweeper
from threading import Lock

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
'''
function contains(boundary, lat, lng) {
  //https://rosettacode.org/wiki/Ray-casting_algorithm
  var count = 0;
  for (var b = 0; b < bounds.length; b++) {
      var vertex1 = bounds[b];
      var vertex2 = bounds[(b + 1) % bounds.length];
      if( vertex1.x == vertex2.x && vertex2.x == lng) {
        if( Math.max( vertex1.y, vertex2.y) > lat && Math.min( vertex1.y, vertex2.y ) < lat) return true; 
      } else if( vertex1.y == vertex2.y && vertex2.y == lat) {
        if( Math.max( vertex1.x, vertex2.x) > lng && Math.min( vertex1.x, vertex2.x ) < lng) return true; 
      }
      if (west(vertex1, vertex2, lng, lat))
          ++count;
  }
  return (count % 2) == 1;
'''

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


'''
  /**
   * @return {boolean} true if (x,y) is west of the line segment connecting A and B
   */
  function west(A, B, x, y) {
      if (A.y <= B.y) {
          if (y <= A.y || y > B.y ||  x >= A.x && x >= B.x) {
              return false;
          } else if (x < A.x && x < B.x) {
              return true;
          } else {
              return (y - A.y) / (x - A.x) > (B.y - A.y) / (B.x - A.x);
          }
      } else {
          return west(B, A, x, y);
      }
  }
}
'''




class PaletteSignals(QObject):
    clear = pyqtSignal()
    setLand = pyqtSignal( list, list )
    drawLoc = pyqtSignal( tuple )

class MapPalette(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._paintcallCnt = 0

        self._drawflag = False
        self.lands = None
        self.mapSize = [1200, 1200]
        self.penColor = QColor(0, 0, 0, 255)

        self.rectFillColor = QColor(255, 255, 0, 255)
        self.rectPenColor = QColor(255, 255, 255, 255)

        self.viewRect = None
        self._rectflag = False

        self.signals = PaletteSignals()
        self.signals.clear.connect( self.clearMap )
        self.signals.setLand.connect( self.setMapData)
        self.signals.drawLoc.connect( self.drawCurrLoc )


    def drawCurrLoc( self, t ):
        self.viewRect = t
        self._rectflag = True
        self.repaint()
        

    def clearMap(self):
        self._rectflag = False
        self.viewRect = None
        self.repiant

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
                ry = int( (self.mapSize[1] -y)*rescaleRatio)
                rw = int( w*rescaleRatio)
                rh = int( h*rescaleRatio)
                qp.drawRect(rx,ry,rw,rh)
            qp.end()

class MiniMap(QMainWindow):
    def __init__(self, signId, amuSignals, sweeper: Sweeper, mutex:Lock, parent=None):
        QMainWindow.__init__(self, parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.palette = MapPalette(self)
        self.setCentralWidget(self.palette)

        self.createActions()
        self.createToolBar()

        self.amuSign = signId
        self.amuSignals = amuSignals
        amuSignals.hideSign.connect(self.toggleWindow)
        amuSignals.closeSign.connect(self.requestClose)

        self.sweeper = sweeper
        self.sweeper.changeLocation.connect( self.drawHudLocRect )

        self._closeflag = False

        self.server = 1947

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
            
            self.palette.signals.drawLoc.emit( (x-15,y-10,30,20) )
            
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
                                                        points += (QPointF( p[0], mapSize[1] - p[1] ),)
                                            lands.append( {'boundary':QPolygonF(points), 
                                                            'color':QColor(color), 
                                                            'name': landName} )
                                self.lands = lands
                                self.palette.signals.setLand.emit(lands, mapSize)
                        
                        except KeyError:
                            pass
                

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