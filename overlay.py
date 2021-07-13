from PyQt5.QtWidgets import QMainWindow, QWidget
from PyQt5.QtCore import QPointF, pyqtSignal, QObject, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

class TranslucentWidgetSignals(QObject):
    # SIGNALS
    CLOSE = pyqtSignal()

class TranslucentWidget(QWidget):
    def __init__(self, parent=None):
        super(TranslucentWidget, self).__init__(parent)

        # make the window frameless
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.fillColor = QColor(200, 200, 200, 50)
        self.penColor = QColor("#333333")

        self.popup_fillColor = QColor(240, 240, 240, 255)
        self.popup_penColor = QColor(200, 200, 200, 255)

        self.SIGNALS = TranslucentWidgetSignals()

    def paintEvent(self, event):
        # This method is, in practice, drawing the contents of
        # your window.

        # get current window size
        s = self.size()
        qp = QPainter()
        qp.begin(self)
        
        qp.setPen(self.penColor)
        qp.setBrush(self.fillColor)
        qp.drawRect(0, 0, s.width(), s.height())

        qp.end()

    def _onclose(self):
        print("Close")
        self.SIGNALS.CLOSE.emit()

class OverlaySignals(QObject):
    resizeSign = pyqtSignal(int,int,int,int)
    closeButtonSignal = pyqtSignal()



class Overlay(QMainWindow):
    BORDER_THICKNESS = 14

    def __init__(self, amuSignals, parent=None):
        QMainWindow.__init__(self, parent, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        widget = QWidget(self)
        self.setCentralWidget(widget)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.boundaryColor = QColor(0, 0, 0, 255)
        self.movingBoundaryColor = QColor(255, 0, 0, 255)
        self.penColor = QColor(200, 200, 200, 10)

        self._popframe = None
        self._popflag = False

        self.pvPoint = None
        self._setGeoMode = 0 

        self.signals = OverlaySignals()

        self.amuSign = amuSignals.SIGN_OVERLAY
        amuSignals.hideSign.connect(self.toggleWindow)
        amuSignals.closeSign.connect(self.requestClose)

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

    def getSignals( self ):
        return self.signals

    def mousePressEvent(self, event):
        
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


        self._onpopup()
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._setGeoMode = 0 
        self.pvPoint = None
        self._closepopup()
        return super().mouseReleaseEvent(event)


        '''
        433, 137 -> 300, 230
        -133, +93
        '''


    def mouseMoveEvent(self, event):

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
                print( 'local variable referenced before assignmen')

            
            self.pvPoint[2] = egX
            self.pvPoint[3] = egY
            
            


        return super().mouseMoveEvent(event)

    def paintEvent(self, event):
        s = self.size()
        lW = s.width()
        lH = s.height()
        #elWidth = lW//10
        #elHeight = lH//10

        outP = []
        inP = []
        for i in range(0,4): # 0: 0,0 | 1: lW,0 | 2: 0,lH | 3: lW,lH
            outter = [(i%2)*lW, (i//2)*lH]
            inner = outter.copy()
            inner[0] += self.BORDER_THICKNESS*(1 if outter[0] == 0 else -1)
            inner[1] += self.BORDER_THICKNESS*(1 if outter[1] == 0 else -1)
            
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
        
        
        qp = QPainter()
        qp.begin(self)
        qp.setRenderHint(QPainter.Antialiasing, True)
        qp.setPen(QPen(self.penColor,2))
        qp.setBrush(self.boundaryColor)
        
        for polygon in trapezoid_list:
            path = QPainterPath()
            path.addPolygon(polygon)
            qp.fillPath(path, qp.brush())
            qp.drawPolygon(polygon)


        qp.setBrush(self.movingBoundaryColor)
        qp.fillRect(lW-self.BORDER_THICKNESS, lH-4*self.BORDER_THICKNESS, self.BORDER_THICKNESS, 2*self.BORDER_THICKNESS, qp.brush())

        qp.end()

    def resizeEvent(self, event):
        geoRect = self.geometry().getRect()
        if self._popflag:
            self._popframe.move(0, 0)
            self._popframe.resize(geoRect[2], geoRect[3])
        self.signals.resizeSign.emit(geoRect[0],geoRect[1],geoRect[2],geoRect[3])

    def moveEvent(self, event):
        geoRect = self.geometry().getRect()
        self.signals.resizeSign.emit(geoRect[0],geoRect[1],geoRect[2],geoRect[3])
        return super().moveEvent(event)

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
            self.signals.closeButtonSignal.emit()
            self.hide()
            event.ignore()
        else:
            print( str(self.__class__.__name__) + ' closed')
            event.accept()