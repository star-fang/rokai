from logging import getLogger
from PyQt5.QtWidgets import QMainWindow, QWidget
from PyQt5.QtCore import QPointF, QRectF, QRunnable, QObject, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QPaintEvent, QPainter, QPainterPath, QPen, QPolygonF, QMouseEvent
from coloratura import Coloratura, DetectScreenWorker

TranslucentSignal = type("TranslucentSignal", (QObject,), {'addRect': pyqtSignal(tuple)})
class TranslucentRects(QWidget):
    def __init__(self, parent=None):
        super(TranslucentRects, self).__init__(parent)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.signals = TranslucentSignal()
        self.signals.addRect.connect(self.addRect)
        self.rects = list()
    
    def addRect( self, rectInfo:tuple):
        self.rects.append( rectInfo )
        self.repaint()

    def paintEvent(self, event):
        
        if  len(self.rects) > 0:
            qp = QPainter()
            qp.begin(self)
            for rect, pen in self.rects:
                rectPath = QPainterPath()
                rectPath.addRect( rect )
                qp.strokePath( rectPath, pen )
            qp.end()

class OverlaySignals(QObject):
    #amu->overlay
    systemEndSign = pyqtSignal() 
    toggleSign = pyqtSignal()

    #overlay-> amu
    closeSign = pyqtSignal()
    hideSign = pyqtSignal(bool)
    addRunner = pyqtSignal(QRunnable)

class Overlay(QMainWindow):
    BORDER_THICKNESS = 12

    def __init__(self, coloratura: Coloratura, parent=None):
        QMainWindow.__init__(self, parent, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        widget = QWidget(self)
        self.setCentralWidget(widget)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.bboxColor = QColor(0, 255, 0, 200)
        self.boundaryColor = QColor(0, 0, 0, 255)
        self.movingBoundaryColor = QColor(255, 0, 0, 255)
        self.penColor = QColor(200, 200, 200, 10)


        self.pvPoint:list = None # pivot points form resizng << type is list for [mutable] parameter passing
        self._setGeoMode:int = 0

        self.logger = getLogger()

        self.signals = OverlaySignals()
        self.signals.toggleSign.connect(self.toggleWindow)
        self.signals.systemEndSign.connect(self.requestClose)

        self._closeflag:bool = False

        self.coloratura:Coloratura = coloratura
        self.bbox:list = list()
        self._bboxFlag:bool = False

        self.coloratura.changeBbox.connect( self.setBbox )
        self.coloratura.addRect.connect( self.showRects )
        self.coloratura.clearRects.connect( self.clearRects )

        self.signals.hideSign.emit(False)

        self._rectsflag = False
        self.show()

    @pyqtSlot(tuple, int, int, int, int, int)
    def showRects(self, box:tuple, r:int, g:int, b:int, alpha:int, thickness:int):
        try:
            x1, y1, x2, y2 = box
            w = x2 - x1
            h = y2 - y1
            if self._bboxFlag:
                if not self._rectsflag:
                    self.rects = TranslucentRects(self.centralWidget())
                    self.rects.move(0, 0)
                    self.rects.resize(self.width(), self.height())
                    self.rects.show()
                    self._rectsflag = True
                rect = QRectF(float(x1+ self.bbox[0]), float(y1+ self.bbox[1]), float(w), float(h))
                self.rects.signals.addRect.emit( (rect, QPen(QColor(r,g,b,alpha), thickness ) ) )
                
        except Exception:
            self.logger.debug('exception while draw rect', stack_info=True)
    
    @pyqtSlot()
    def clearRects(self):
        if self._rectsflag:
            self.rects.close()
            self._rectsflag = False

    @pyqtSlot( tuple )
    def setBbox( self, bbox:tuple):
        if len(bbox) == 4:
            self.bbox = [e+self.BORDER_THICKNESS for e in bbox]
            self._bboxFlag = True
            self.repaint()

    def requestDetectScreenWork( self ):
        runner = DetectScreenWorker(self.coloratura, self.getInnerRect())
        self.signals.addRunner.emit(runner)

    def getInnerRect(self):
        rect = self.geometry().getRect()
        x = rect[0] + self.BORDER_THICKNESS
        y = rect[1] + self.BORDER_THICKNESS
        w = rect[2] - 2 * self.BORDER_THICKNESS
        h = rect[3] - 2 * self.BORDER_THICKNESS
        return (x,y,w,h)

    

    def requestClose( self ):
        self._closeflag = True
        self.close()
    
    def toggleWindow( self ):
        if self.isHidden():
            self.show()
            self.signals.hideSign.emit(False)
        else:
            self.hide()
            self.signals.hideSign.emit(True)

    def mousePressEvent(self, event: QMouseEvent):
        
        s = self.size()
        lW = s.width()
        lH = s.height()
        evtX = event.x()
        evtY = event.y()
        egX = event.globalX()
        egY = event.globalY()

        self.pvPoint = [evtX, evtY, egX, egY]
        
        left = evtX <= self.BORDER_THICKNESS and evtX >= 0
        upper = evtY <= self.BORDER_THICKNESS and evtY >= 0
        right = evtX <= lW and evtX >= lW - self.BORDER_THICKNESS
        lower = evtY <= lH and evtY >= lH - self.BORDER_THICKNESS

        mode = 0
        '''
        1 2 3
        8   4
        7 6 5  -> 9 : moveing mode
        '''
        if left:
            if upper:
                mode = 1
            elif lower:
                mode = 7
            else:
                mode = 8
        elif right:
            if upper:
                mode = 3
            elif lower:
                mode = 5
            else:
                if evtY >= lH - 4*self.BORDER_THICKNESS and evtY <= lH - 2*self.BORDER_THICKNESS:
                    mode = 9
                else:
                    mode = 4
        else:
            if upper:
                mode = 2
            elif lower:
                mode = 6

        self._setGeoMode = mode

        self._bboxFlag = False
        self.bbox.clear()
        self.repaint()
        self.clearRects()
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._setGeoMode = 0 
        self.pvPoint = None

        self.requestDetectScreenWork()
        

        return super().mouseReleaseEvent(event)


        '''
        433, 137 -> 300, 230
        -133, +93
        '''

    def mouseMoveEvent(self, event: QMouseEvent):

        '''
        1 2 3
        8   4
        7 6 5  -> 9 : moveing mode
        '''

        if self._setGeoMode > 0 and self.pvPoint is not None:
            mode = self._setGeoMode
            s = self.size()
            lW = s.width()
            lH = s.height()
            evtX = event.x()
            evtY = event.y()
            egX = event.globalX()
            egY = event.globalY()

            evtPvX, evtPvY, egPvX, egPvY = self.pvPoint

            diffX = egX - egPvX
            diffY = egY - egPvY

            move = True
            if mode == 1:
                nextW = lW - diffX   # -1, -1, (0,1), (0,1)
                nextH = lH - diffY
                nextX = egX - evtPvX
                nextY = egY - evtPvY
            elif mode == 2:
                nextW = lW
                nextH = lH - diffY
                nextX = egX - evtX
                nextY = egY - evtPvY
            elif mode == 3:
                nextW = lW + diffX
                nextH = lH - diffY
                nextX = egX - evtX
                nextY = egY - evtPvY
            elif mode == 4:
                nextW = lW + diffX
                nextH = lH
                nextX = egX - evtX
                nextY = egY - evtY
            elif mode == 5:
                nextW = lW + diffX
                nextH = lH + diffY
                nextX = egX - evtX
                nextY = egY - evtY
            elif mode == 6:
                nextW = lW
                nextH = lH + diffY
                nextX = egX - evtX
                nextY = egY - evtY
            elif mode == 7:
                nextW = lW - diffX
                nextH = lH + diffY
                nextX = egX - evtPvX
                nextY = egY - evtY
            elif mode == 8:
                nextW = lW - diffX
                nextH = lH
                nextX = egX - evtPvX
                nextY = egY - evtY
            elif mode == 9:
                nextW = lW
                nextH = lH
                nextX = egX - evtPvX
                nextY = egY - evtPvY
            else:
                move = False
            try:
                if move and nextW > 8*self.BORDER_THICKNESS and nextH > 8*self.BORDER_THICKNESS:
                    self.setGeometry( nextX, nextY, nextW, nextH )
            except UnboundLocalError:
                self.logger.debug('exception while dragging')

            self.pvPoint[2] = egX
            self.pvPoint[3] = egY
            
            


        return super().mouseMoveEvent(event)

    def createBoundaryPolygons( self, bbox:list, thickness:int):
        #x1,y1,x2,y2
        outP = []
        inP = []
        #x1,y1 | x1+w , y1 | x1, y1+h | x1+w, y1+h
        #x1,y1 | x2, y1 | x1, y2 | x2, y2
        #0,1 | 2,1 | 0, 3 | 2,3 
        #0,0 | 1,0 | 0, 1 | 1,1
        for i in range(0,4): # 0: 0,0 | 1: lW,0 | 2: 0,lH | 3: lW,lH
            outter = [bbox[2*(i%2)], bbox[1+2*(i//2)]]
            inner = outter.copy()
            inner[0] += thickness*(1 if outter[0] == 0 else -1)
            inner[1] += thickness*(1 if outter[1] == 0 else -1)
            
            outP.append( outter )
            inP.append( inner )
        
        trapezoid_list = []
        indexList = [0,1,3,2]
        for i in range(0,4):
            # o: 0, 1 // l: 1, 0
            # o: 1, 3 // l: 3, 1
            # o: 3, 2 // l: 2, 3
            # o: 2, 0 // l: 0, 2
            currI = indexList[i]
            nextI = indexList[(i+1)%4]
            trapezoid  = QPolygonF( [
                QPointF( outP[currI][0],outP[currI][1] ),
                QPointF( outP[nextI][0],outP[nextI][1] ),
                QPointF( inP[nextI][0],inP[nextI][1] ),
                QPointF( inP[currI][0],inP[currI][1] )
                ] )
            trapezoid_list.append( trapezoid )
        return trapezoid_list  

    def paintEvent(self, event:QPaintEvent):
        s = self.size()
        lW = s.width()
        lH = s.height()
        
        qp = QPainter()
        qp.begin(self)
        qp.setRenderHint(QPainter.Antialiasing, True)
        qp.setPen(QPen(self.penColor,2))
        
        qp.setBrush(self.boundaryColor)
        outB = self.createBoundaryPolygons([0,0,lW,lH], self.BORDER_THICKNESS)
        for polygon in outB:
            outPath = QPainterPath()
            outPath.addPolygon(polygon)
            qp.fillPath(outPath, qp.brush())
            qp.drawPolygon(polygon)

        if self._bboxFlag:
            inB = self.createBoundaryPolygons(self.bbox, 5)
            qp.setBrush(self.bboxColor)
            for polygon in inB:
                inPath = QPainterPath()
                inPath.addPolygon(polygon)
                qp.fillPath(inPath, qp.brush())
  
        qp.setBrush(self.movingBoundaryColor)
        qp.fillRect(lW-self.BORDER_THICKNESS, lH-4*self.BORDER_THICKNESS, self.BORDER_THICKNESS, 2*self.BORDER_THICKNESS, qp.brush())
        qp.end()

    def hideEvent(self, event):
        self.logger.info('hide overlay')
        return super().hideEvent(event)
    
    def closeEvent(self, event):
        if self._closeflag is False:
            self.signals.closeSign.emit()
            self.hide()
            event.ignore()
        else:
            self.logger.debug('close overlay')
            event.accept()