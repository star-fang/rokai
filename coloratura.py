import cv2
import numpy as np
import pyautogui
from imutils import resize as imResize
from math import cos, sin, radians
from re import sub as regexSub, split as regexSplit
from PIL import ImageGrab
from concurrent import futures
from PyQt5.QtCore import QMutex, QRunnable, QThread, QWaitCondition, QObject, pyqtSignal, pyqtBoundSignal
from pathlib import Path
from recognizing import OcrEngine, ocr_preprocessing, hsvMasking, template_match, detectShape, findContourList, rotateImage
from unpredictable import MT19937Generator
from multiprocessing import Process, Queue, Pipe, connection
from threading import Event
from pynput import keyboard
from time import sleep
from log import MultiProcessLogging

LV_CHECK_STATUS = 1
LV_MOUSING = 2
LV_FIND_RUBY = 3
LV_CRACK = 4
LV_AUTO = 5

TH_BUTTON0 = 100
TH_BUTTON1= 180
TH_HEADLINE = 170
TH_RUBY_IN_DIALOG = 150
TH_RUBY_DAY = 90
TH_RUBY_NIGHT = 60
TH_NIGHT_AND_DAY = 127
RATIO_HEAD_IN_DIALOG = 0.12
TH_CONTRAST_RATIO_WB_ND = 0.3 # lower -> night, upper -> daytime

class ColoraturaSignalKey:
    changeLocation = 0
    evalLocation = 1
    changeState = 2
    changeTemplate = 3
    changeTmRatio = 4
    changeTmRotate = 5
    plotPlt = 6
    changeBbox = 7
    addRect = 8
    statusMessage = 9


    captureScreen = 99 # special signature

class Coloratura( QObject ):
    # minimap
    changeLocation = pyqtSignal(tuple, float) # location, dreiction to minimap
    evalLocation = pyqtSignal( float ) # direction from minimap

    # to coloratura view
    changeState = pyqtSignal(int)
    changeTemplate = pyqtSignal( np.ndarray ) # image matrix
    changeTmRatio = pyqtSignal(int)
    changeTmRotate = pyqtSignal(int)
    plotPlt = pyqtSignal( np.ndarray ) # draw plt in main thread
    
    # to overlay
    changeBbox = pyqtSignal(tuple) # draw overlay boundary
    addRect = pyqtSignal(tuple, int, int ,int ,int, int) # draw ovetlay rects, rgba, thickness
    clearRects = pyqtSignal(QWaitCondition)

    # to main window
    statusMessage = pyqtSignal( str )

    def signalMap(self, key:int):
        if key == ColoraturaSignalKey.changeLocation: # 0
            return self.changeLocation 
        elif key == ColoraturaSignalKey.evalLocation: # 1
            return self.evalLocation
        elif key == ColoraturaSignalKey.changeState: # 2
            return self.changeState
        elif key == ColoraturaSignalKey.changeTemplate: # 3
            return self.changeTemplate
        elif key == ColoraturaSignalKey.changeTmRatio: # 4
            return self.changeTmRatio
        elif key == ColoraturaSignalKey.changeTmRotate: # 5
            return self.changeTmRotate
        elif key == ColoraturaSignalKey.plotPlt: # 6
            return self.plotPlt
        elif key == ColoraturaSignalKey.changeBbox: # 7
            return self.changeBbox
        elif key == ColoraturaSignalKey.addRect: # 8
            return self.addRect
        elif key == ColoraturaSignalKey.statusMessage: #9
            return  self.statusMessage

    def __init__(self, loggingQueue:Queue):
        super().__init__()
        self.logger = MultiProcessLogging().make_q_handled_logger(loggingQueue, 'coloratura')
        self.bbox:tuple = None
            
    def grabScreen( self ):
        try:
            waitCondition = QWaitCondition()
            self.logger.debug('Coloratura wait for overlay clear')
            mutex = QMutex()
            if mutex.tryLock( 2000 ):
                try:        
                    self.clearRects.emit(waitCondition)
                    waitCondition.wait(mutex, 2000)
                finally:
                    mutex.unlock()
                    img_pil = ImageGrab.grab(bbox=self.bbox)
                    img_src = np.array(img_pil)
                    img_gray = cv2.cvtColor(img_src, cv2.COLOR_BGR2GRAY)
                    self.logger.debug('capture: succ')
                    return (img_src, img_gray)
            else:
                self.logger.debug('capture failure: deadlock')
        except Exception as e:
            self.logger.debug('exception while caputre', stack_info=True)
        self.logger.info('capture: none')
        return None

class DetectScreenWorker(QRunnable):

    def run(self):
        if self.args is None or len(self.args)==0:
            self.coloratura.logger.warning( 'detect screen: no args')
            return
        rect = self.args[0]
        if rect is None or not isinstance(rect, tuple) or len(rect) != 4 or not all(isinstance(n,int) for n in rect):
            self.coloratura.logger.warning( 'detect screen: no rect')
            return

        self.coloratura.bbox = (rect[0],rect[1],rect[0]+rect[2],rect[1]+rect[3])
        captured = self.coloratura.grabScreen()
        
        if captured is None:
            return
        img_gray = captured[1]
        resized = imResize(img_gray, width = 320)
        ratio = img_gray.shape[0] / float(resized.shape[0])
        blurred = cv2.GaussianBlur(resized,(3,3), 0 )
        img_thresh = cv2.threshold(blurred, 70, 255, cv2.THRESH_BINARY)[1]
        contours = findContourList(img_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if isinstance(contours,list) and len(contours) > 0:
            ih,iw = img_thresh.shape[:2]
            contours.sort(key = cv2.contourArea, reverse=True)
            fitContour = None
            for i in range( 0, len(contours) ):
                
                contour = contours[i]
                verticesCnt = detectShape(contour=contour)[0]
                cw,ch = cv2.boundingRect(contour)[2:]
                areaCont = cw * ch
                areaImg = iw * ih
                if areaCont >= 0.6 * areaImg and areaCont <= 1.0 * areaImg:
                    if  verticesCnt == 4:
                        fitContour = contour
                else:
                    self.coloratura.logger.debug( f'bigContourFinder: stopped in {(i+1)}try(s)' )
                    break
            if fitContour is not None:
                brect = [e*ratio for e in cv2.boundingRect(fitContour)]
                x, y, w, h = brect
                bbox = (x,y,x+w,y+h)
                x1, y1 = rect[:2]
                x3, y3, x4, y4 = bbox
                self.coloratura.changeBbox.emit( bbox )
                self.coloratura.bbox = (x1 + x3, y1 + y3, x1 + x4, y1 + y4)
            else:
                self.coloratura.changeBbox.emit( (0,0,rect[2],rect[3]) )

    def __init__(self, coloratura:Coloratura, *args):
        super().__init__()
        self.coloratura = coloratura
        self.args = args

class ColoraturaConnector(QThread):
    def __init__(self, coloratura:Coloratura, pipe_main:connection.Connection):
        super().__init__()
        self.__coloratura = coloratura
        self.__pipe = pipe_main

    def _emit(self, key:int, args=None):
        if key == ColoraturaSignalKey.captureScreen:
            data = ( ('captured'), )
            captured = self.__coloratura.grabScreen()
            data += ( captured, )
            try:
                self.__pipe.send( data )
            except Exception:
                pass
        else:
            signal = self.__coloratura.signalMap(key)
            if isinstance( signal, pyqtBoundSignal ):
                try:
                    if args is not None:
                        signal.emit(*args)
                    else:
                        signal.emit()
                except TypeError:
                    pass

    def run(self):
        while True:
            #self.__coloratura.logger.debug('connector: looping...')
            try:
                recvData = self.__pipe.recv()
            except EOFError:
                break
            else:
                if recvData is None:
                    break
                #self.__coloratura.logger.debug(f'recvd: {recvData}')
                self._emit(*recvData) # (signature) + (args)
        #self.__coloratura.logger.debug('connector: end loop')
        print('connector end')

class ColoraturaProcessRunner(QRunnable):
    def run(self):
        def on_release(key):
            if key == keyboard.Key.esc:
                self.__process.end_process()
        
        self.__connector.start()
        self.__process.start()
        #self.__coloratura.logger.debug(f'---Process level {self.__level} started---')
        keyboard_listener = keyboard.Listener(on_release = on_release )
        keyboard_listener.start()
        while True:
            try:
                data = self.__queue.get()
            except EOFError:
                break
            else:
                if data is None:
                    break
        keyboard_listener.stop()
        keyboard_listener.join()
        self.__connector.wait()
        self.__process.join()
        #self.__coloratura.logger.debug(f'---Process level {self.__level} finished---')         
        try:
            self.finSignal.finished.emit()
        except AttributeError:
            pass
        print('runner end')

    def __init__(self, loggingQueue:Queue, coloratura:Coloratura, level:int=1):
        super().__init__()
        self.finSignal = type('FinSignal', (QObject,), {'finished': pyqtSignal()})()
        self.__coloratura = coloratura
        self.__level = level
        self.__queue = Queue()
        conn_main, conn_proc = Pipe(True)
        self.__connector = ColoraturaConnector(coloratura, conn_main)
        self.__process = ColoraturaProcess( loggingQueue, self.__queue, conn_proc, tuple(e for e in coloratura.bbox), level)

class ColoraturaProcess(Process):
    WHERE_NONE = 0
    WHERE_FIELD = 1
    WHERE_HOME = 2
    
    WHEN_NONE = 0
    WHEN_NIGHT = 1
    WHEN_DAY = 2
    
    NO_DIALOG = 0
    DIALOG_ROBOT = 1
    DIALOG_RUBY = 2
    DIALOG_UNKNOWN = 3
    INIT_STATE = 9
    
    def __init__(self, loggingQueue:Queue, queue:Queue, pipe:connection.Connection, bbox:tuple, level:int = 1):
        super().__init__()
        self.__queue = queue
        self.__level = level
        self.__pipe = pipe
        self.__loggingQ = loggingQueue
        
        self.ocr = OcrEngine()
        self.loadTmImages()
        self.bbox = bbox
        self.tmMethod = cv2.TM_CCOEFF_NORMED
        self.rboxList = list()
        self.crack_tm_box_list = list()
        self.initStateFlags()
        self.initWorkFlowData()
        self.randomGenerator = MT19937Generator()
        self.direction: float = self.randomGenerator.generateRandomFloat(max=360.0) # 0.0 ~ 360.0
        #self.evalLocation.connect(lambda a: self.changeDirection( a ))
        self.logger = MultiProcessLogging().make_q_handled_logger(self.__loggingQ, 'proc')
        
        
    def loadTmImages(self):
        source_path = Path(__file__).resolve()
        assets_dir = str(source_path.parent) + '/assets'

        self.template_ruby_in_dialog = cv2.threshold(cv2.imread(f'{assets_dir}/ruby_in_dialog.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_RUBY_IN_DIALOG, 255, cv2.THRESH_BINARY)[1]
        self.template_ruby_day = cv2.threshold(cv2.imread(f'{assets_dir}/ruby_day.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_RUBY_DAY, 255, cv2.THRESH_BINARY)[1]
        self.template_ruby_night = cv2.threshold(cv2.imread(f'{assets_dir}/ruby_night.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_RUBY_NIGHT, 255, cv2.THRESH_BINARY)[1]
        self.template_to_field = cv2.threshold(cv2.imread(f'{assets_dir}/btn_to_field.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_BUTTON1, 255, cv2.THRESH_BINARY)[1]
        self.template_to_home = cv2.threshold(cv2.imread(f'{assets_dir}/btn_to_home.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_BUTTON1, 255, cv2.THRESH_BINARY)[1]
        self.template_robot_check = cv2.threshold(cv2.imread(f'{assets_dir}/btn_robot.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_BUTTON0, 255, cv2.THRESH_BINARY)[1]
        self.template_head_robot = cv2.threshold(cv2.imread(f'{assets_dir}/head_robot.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_HEADLINE, 255, cv2.THRESH_BINARY)[1]

    def _emit( self, key:int, args=None):
        data = (key,)
        if args is not None:
            if isinstance( args, tuple):
                data += (args,)
            else:
                data += ((args,),)
        try:
            self.__pipe.send(data)
        except Exception:
            pass
        
    def end_process(self):
        try:
            print('process end')
            self.__pipe.send(None) # stop signal connector
            self.__queue.put(None) # stop runner
            self.terminate()
        except AttributeError:
            pass
        
    def run(self):
        self.logger.debug('start process')
        while( True ):
            self.initWorkFlowData()
            self.initStateFlags()
            captureSucc:bool = False
            self._emit(ColoraturaSignalKey.captureScreen)
            while True:
                try:
                    recvd = self.__pipe.recv()
                    key, args = recvd
                    if key == 'captured':
                        captured = args
                        captureSucc = isinstance(captured,tuple) and len(captured) == 2
                        break
                except ValueError:
                    pass

            if captureSucc:
                img_src, img_gray = captured
                dialogTuple = self.detectDialog(img_src)
                if isinstance(dialogTuple, tuple):
                    self.identifyDialog( dialogTuple, img_src, img_gray, self.__level )
                else:
                    with futures.ThreadPoolExecutor() as executor:
                        whenFuture = executor.submit( self.detectNightAndDay, img_gray )
                        coordsFuture = executor.submit( self.detectCoordinates, img_src, img_gray )
                        whereFuture =  executor.submit( self.checkFieldOrHome, img_gray, self.__level )
                        robotFuture = executor.submit( self.checkRobotBtnAppear, img_gray, self.__level )

                        whenResult:bool = whenFuture.result()
                        coordsResult:bool = coordsFuture.result()
                        whereResult:bool = whereFuture.result()
                        robotResult:bool = robotFuture.result()

                        if whenResult and whereResult and not robotResult:
                            self.determineFieldWork(coordsResult, img_gray, self.__level)
            if self.__level >= LV_AUTO:
                sleep(0.5)
            else: 
                break   
        self.end_process()

    def changeDirection( self, angle:float):
        self.direction = angle
        #self.waitForEvalLoc.wakeAll()
    
    def initStateFlags(self):
        self.state_when:int = self.WHEN_NONE
        self.state_where:int = self.WHERE_NONE
        self.state_dialog:int = self.NO_DIALOG

    def initWorkFlowData(self):
        self.crack_tm_box_list.clear()
        self.crack_image_box:tuple = None
        self.crack_button_box:tuple = None
        self.field_button_box:tuple = None
    
    def identifyDialog(self, dialogInfo:tuple, img_src:np.ndarray, img_gray:np.ndarray, wf_level:int = 1):
        bbox = dialogInfo[1]
        isWhiteDialog:bool = dialogInfo[0] == 'white'

        x, y, x2, y2 = bbox
        w = x2 - x
        h = y2 - y

        def robotMatch( x,y,w,h,img_gray, useless:bool=False):
            if useless:
                return None
            dialog_head = img_gray[y:y+int(h*RATIO_HEAD_IN_DIALOG),x:x+w]
            
            match_result = self.multiScaleMatch(self.template_head_robot, dialog_head, min=0.01, max=4.0, counts = 40, matchVal=0.6 )
            
            if match_result is not None:
                matchVal,top_left,bottom_right,r = match_result
                rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
                rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
                localHeadlineBox = rTopLeft + rBottomRight
                x1,y1,x2,y2 = localHeadlineBox
                globalHeadlineBox = (x+x1, y+y1, x+x2, y+y2)
                self._emit(ColoraturaSignalKey.addRect, ( globalHeadlineBox,255,0,255,255, 2 ))
                return globalHeadlineBox
            return None

        def rubyTemplateMatch( x, y, w, h, img_gray, useless:bool=False ):
            if useless:
                return False
            img_dialog_left = img_gray[y:y+h,x:x+w//2]
            img_dialog_th = cv2.threshold(img_dialog_left, TH_RUBY_IN_DIALOG, 255, cv2.THRESH_BINARY)[1]
            
            match_result = self.multiScaleMatch(self.template_ruby_in_dialog, img_dialog_th)
            if match_result is not None:
                matchVal,top_left,bottom_right,r = match_result
                rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
                rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
                rubyImgBox = rTopLeft + rBottomRight
                x1,y1,x2,y2 = rubyImgBox
                self._emit(ColoraturaSignalKey.addRect, ( (x+x1, y+y1, x+x2, y+y2),255,255,0,255, 2 ) )
                return True
            return False

        def findButtons( x, y, w, h, img_src):
            px = x
            py = y + int(h*0.5)
            fitContours = list()

            try:
                dialog_lower = img_src[py:y + h,px:x+w]
                hsv = cv2.cvtColor(dialog_lower, cv2.COLOR_BGR2HSV)

                for mask_idf, mask in {'blue': hsvMasking( hsv, [0,150,0], [40,255,255] ), \
                                       'red': hsvMasking( hsv, [110,150,0], [130,255,255] ),
                                       'yellow': hsvMasking( hsv, [90,150,0], [120,255,255]) }.items():
                    contours = findContourList(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

                    if contours is not None and len( contours ) > 0:
                        for contour in contours:
                            cw,ch = cv2.boundingRect(contour)[2:]
                            if cw < w and cw * 5 > w and ch * 20 > h and ch < h:
                                verticesCnt = detectShape(contour=contour, epsilon=0.02)[0]
                                self.logger.debug( f'button shape:{verticesCnt}' )
                                if verticesCnt == 4:
                                    fitContours += ( (mask_idf,contour),)
            except Exception as e:
                self.logger.debug('exception while find buttons', stack_info=True)
                            
            return (fitContours, px, py)
                    
        with futures.ThreadPoolExecutor() as executor:
            
            buttonFuture = executor.submit( findButtons, x,y, w, h, img_src)
            rubyFuture = executor.submit( rubyTemplateMatch, x,y, w, h, img_gray, useless = not isWhiteDialog)
            robotFuture = executor.submit(robotMatch, x,y,w,h, img_gray, useless =  not isWhiteDialog)

            rubyResult = rubyFuture.result()
            buttonResult = buttonFuture.result()
            robotResult = robotFuture.result()

            buttons, buttonPx, buttonPy = buttonResult
            btnCount = len(buttons) # (idf,btn), ...

            buttonBoxes = dict()
            if btnCount > 0:
                btnCount = 0
                btns_sorted = sorted( buttons, key=lambda b: cv2.boundingRect(b[1])[1], reverse=True)
                lowest_rect =  cv2.boundingRect(btns_sorted[0][1])
                for idf, button in buttons:
                    bx, by, bw, bh = cv2.boundingRect(button)
                    if by + bh > lowest_rect[1]:
                        btnBox = ( buttonPx + bx, buttonPy + by, buttonPx + bx + bw,  buttonPy +by + bh)
                        self._emit(ColoraturaSignalKey.addRect, ( btnBox, 255,0,0,200, 5)  )
                        if idf not in buttonBoxes:
                            buttonBoxes[idf] = list()
                        buttonBoxes[idf] += (btnBox,)
                        btnCount += 1

            
            if robotResult is not None and btnCount == 1 and 'blue' in buttonBoxes:
                if self.analyzeRobot2Dialog( img_gray, bbox, buttonBoxes['blue'][0], robotResult):
                    self._emit(ColoraturaSignalKey.changeState, self.DIALOG_ROBOT)
                    if wf_level >= LV_CRACK:
                        self.crackRobotCheck(img_src, False)
                    return
            if rubyResult:
                self._emit(ColoraturaSignalKey.changeState, self.DIALOG_RUBY)
                self.logger.info( f'dialog: ruby with {btnCount} button(s)' )
            else:
                self._emit(ColoraturaSignalKey.changeState, self.DIALOG_UNKNOWN)
                self.logger.info( f'dialog: unknown with {btnCount} button(s)' )
            
            if wf_level >= LV_MOUSING:
                if btnCount == 1 and 'blue' in buttonBoxes:
                    bx1, by1, bx2, by2 = buttonBoxes['blue'][0]
                    pyautogui.moveTo( self.bbox[0] + (bx1+bx2)//2, self.bbox[1]+ (by1+by2)//2, 1 )
                    pyautogui.click()
                elif not isWhiteDialog and  btnCount == 2 and 'blue' in buttonBoxes and 'yellow' in buttonBoxes:
                    bx1, by1, bx2, by2 = buttonBoxes['yellow'][0]
                    pyautogui.moveTo( self.bbox[0] + (bx1+bx2)//2, self.bbox[1]+ (by1+by2)//2, 1 )
                    pyautogui.click()
                else:
                    pyautogui.moveTo( self.bbox[0] + bbox[0] - 10, self.bbox[1]+ bbox[3] - 10, 1 )
                    pyautogui.click()

    def detectDialog(self, img_src:np.ndarray = None):
        hsv = cv2.cvtColor( img_src, cv2.COLOR_BGR2HSV )
        ih,iw = img_src.shape[:2]
        whiteDialogMask = hsvMasking( hsv, [0,0,190], [120,90,255], adjMode=False )
        contours = findContourList(whiteDialogMask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if contours is not None and len( contours ) > 0:
            contour = max( contours, key = cv2.contourArea)
            cx, cy, cw,ch = cv2.boundingRect(contour)
            if cw < iw and cw * 10 > iw and ch * 5 > ih and ch < ih:
                verticesCnt, ar = detectShape(contour=contour)
                if verticesCnt == 4:
                    bbox = (cx, cy, cx+cw, cy+ch)
                    self._emit(ColoraturaSignalKey.addRect, ( bbox, 0,0,255,255, 5 ))
                    return ('white',bbox)

        navyDialogMask = cv2.bitwise_or(hsvMasking( hsv, [0,70,60], [25,255,180], adjMode=False ),\
            hsvMasking( hsv, [150,70,60], [180,255,180], adjMode=False ) )
        contours = findContourList(navyDialogMask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if contours is not None and len( contours ) > 0:
            contour = max( contours, key = cv2.contourArea)
            cx, cy, cw,ch = cv2.boundingRect(contour)
            if cw < iw and cw > iw * 0.6 and ch > ih * 0.7 and ch < ih:
                verticesCnt, ar = detectShape(contour=contour)
                self.logger.debug( f'dialog shape:{verticesCnt}, ar:{ar}' )
                if verticesCnt == 4:
                    bbox = (cx, cy, cx+cw, cy+ch)
                    self._emit(ColoraturaSignalKey.addRect, ( bbox, 0,0,255,255, 5 ))
                    return ('navy',bbox)
        self.state_dialog = self.NO_DIALOG
        self._emit(ColoraturaSignalKey.changeState, self.NO_DIALOG )
        self.logger.info( 'dialog: none' )
        return None

    def detectNightAndDay( self, img_gray:np.ndarray ):
        img_thresh = cv2.threshold(img_gray, TH_NIGHT_AND_DAY, 255, cv2.THRESH_BINARY)[1]

        try:
            number_of_white = np.sum(img_thresh == 255)
            number_of_black = np.sum(img_thresh == 0)

            wbRatio = round(number_of_white/number_of_black, 2)
        
            daytime = bool(TH_CONTRAST_RATIO_WB_ND < wbRatio)
        
            if daytime is True:
                self.state_when = self.WHEN_DAY
                self.logger.info( f'when: daytime (cr: {str(wbRatio)})' )
            else:
                self.state_when = self.WHEN_NIGHT
                self.logger.info( f'when: night (cr: {str(wbRatio)})' )
            return True
        except Exception:
            self.logger.debug('when error', stack_info=True)
        self.state_when = self.WHEN_NONE
        self.logger.info( f'when: none' )
        return False

    def checkRobotBtnAppear(self, img_gray:np.ndarray, wf_level:int = 1):
        imgHeight, imgWidth = img_gray.shape[:2]
        pY = 0
        pX = int( imgWidth * 0.5)
        try:
            img_right_upper = img_gray[pY: int( imgHeight * 0.3 ), pX: imgWidth ]
            img_th = cv2.threshold(img_right_upper, TH_BUTTON0, 255, cv2.THRESH_BINARY)[1]
            match_result = self.multiScaleMatch( self.template_robot_check, img_th )
            if match_result is not None:
                matchVal,top_left,bottom_right,r = match_result
                rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
                rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
                buttonBox = rTopLeft + rBottomRight
                robot_button_box = (pX+buttonBox[0], pY+buttonBox[1], pX+buttonBox[2], pY+buttonBox[3])
                self._emit(ColoraturaSignalKey.addRect, ( robot_button_box,255,0,0,100, 4 ))
                if wf_level >= LV_MOUSING:
                    x1, y1, x2, y2 = robot_button_box
                    pyautogui.moveTo( self.bbox[0] + (x1+x2)//2, self.bbox[1]+ (y1+y2)//2, 1 )
                    pyautogui.click()
                return True
        except Exception:
            self.logger.debug('checkRobotBtnAppear', stack_info= True)
        return False

    def checkFieldOrHome(self, img_gray:np.ndarray, wf_level:int = 1):

        imgHeight, imgWidth = img_gray.shape[:2]
        pY = int( imgHeight*0.7 )
        pX = 0
        try:
            img_left_lower = img_gray[pY: imgHeight, pX: int( imgWidth * 0.3)]
            img_th = cv2.threshold(img_left_lower, TH_BUTTON1, 255, cv2.THRESH_BINARY)[1]
            self._emit(ColoraturaSignalKey.changeTemplate, self.template_to_home)    
            match_result = self.multiScaleMatch( self.template_to_home, img_th )

            if match_result is not None:
                self.logger.info( 'where: field' )
                self.state_where = self.WHERE_FIELD
                
            else:
                self._emit(ColoraturaSignalKey.changeTemplate,self.template_to_field)
                match_result = self.multiScaleMatch( self.template_to_field, img_th)
                if match_result is not None:
                    self.logger.info( 'where: home' )
                    self.state_where = self.WHERE_HOME

            if match_result is not None:
                matchVal,top_left,bottom_right,r = match_result
                rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
                rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
                buttonBox = rTopLeft + rBottomRight
                self.field_button_box = (pX+buttonBox[0], pY+buttonBox[1], pX+buttonBox[2], pY+buttonBox[3])
                self._emit( ColoraturaSignalKey.addRect,( self.field_button_box,255,0,0,100,4 ) )
                if self.state_where == self.WHERE_HOME:
                    if wf_level >= LV_MOUSING:
                        x1, y1, x2, y2 = self.field_button_box
                        pyautogui.moveTo( self.bbox[0] + (x1+x2)//2, self.bbox[1]+ (y1+y2)//2, 1 )
                        pyautogui.click()
                    return False
                return True

        except Exception as e:
            self.logger.debug( 'where', stack_info=True)
        self.logger.info( 'where: none' )
        self.state_where = self.WHERE_NONE
        return False
            
    def detectCoordinates(self, img_src:np.ndarray, img_gray:np.ndarray):
        imgHeight, imgWidth = img_gray.shape[:2]

        #img_topLeft = img_src[0:int(imgHeight*0.1),0:int(imgWidth*0.5)]
        img_topLeft = img_src[0:int(imgHeight*0.1),0:int(imgWidth*0.5)]
        itlH, itlW = img_topLeft.shape[:2]
        hsv = cv2.cvtColor(img_topLeft, cv2.COLOR_BGR2HSV)
        grayMask = hsvMasking( hsv, [90,0,120], [120,30,255], adjMode=False )
        contours = findContourList(grayMask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if contours is not None and len( contours ) > 0:
            contour = max( contours, key = cv2.contourArea)
            cx, cy, cw,ch = cv2.boundingRect(contour)
            if cw * 2 < itlW and cw * 5 > itlW and ch * 3 > itlH and ch < itlH:
                verticesCnt, ar = detectShape(contour=contour)
                if verticesCnt == 4:
                    bbox = (cx, cy, cx+cw, cy+ch)
                    try:
                        bx,by,x2,y2 = bbox
                        self._emit( ColoraturaSignalKey.addRect,( bbox,255,0,0,255,2 ) )
                        bw = x2-bx
                        bh = y2-by
                        cbox = (bx + bw , by + int(0.1*bh), bx+int(2.2*bw), by + int(0.9*bh) )
                        coords_part_gray = img_gray[cbox[1]:cbox[3], cbox[0]:cbox[2]]
                        self._emit( ColoraturaSignalKey.addRect,( cbox,255,0,255, 200,2 ) )
            
                        dst, r = ocr_preprocessing(src_gray=coords_part_gray, height=64, adjMode=False)

                        if dst is not None:
                            coords_txt = self.ocr.read(dst,config='-l eng --oem 1 --psm 13').strip()

                            txt = regexSub('\D',' ', coords_txt)
                            split = [e for e in regexSplit('\s+', txt) if e != '']
                            self.logger.info( f'location(ocr): {coords_txt}' )
                            if( len(split) == 3):
                                digits = tuple()
                                for i in range(0,3):
                                    digits += ( int(split[i]), )
                                mutex = QMutex()
                                if mutex.tryLock(2000):
                                    try:
                                        self.logger.debug(f'degree before:{self.direction}')
                                        self._emit( ColoraturaSignalKey.changeLocation,( digits, self.direction ) )
                                        #self.waitForEvalLoc.wait(mutex, 2000)
                                        self.logger.debug(f'degree after:{self.direction}')
                                    finally:
                                        mutex.unlock()
                                    return True
                    except Exception as e:
                        self.logger.debug(f'location error {e}', stack_info=True)
        self.logger.info( f'location: none' )
        return False

    def findRuby(self, img_gray:np.ndarray ):
        img_th = None
        match_result = None

        def rubyMatch( img:np.ndarray, template:np.ndarray, th:int ):
            self._emit(ColoraturaSignalKey.changeTemplate, template)
            img_th = cv2.threshold(img, th, 255, cv2.THRESH_BINARY)[1]
            return (self.multiScaleMatch( template, img_th), img_th)

        try:
            if( self.state_when == self.WHEN_DAY ):
                match_result, img_th = rubyMatch( img_gray, self.template_ruby_day , TH_RUBY_DAY )
            elif( self.state_when == self.WHEN_NIGHT ):
                match_result, img_th = rubyMatch( img_gray, self.template_ruby_night, TH_RUBY_NIGHT )
            else:
                match_result, img_th = rubyMatch( img_gray, self.template_ruby_day , TH_RUBY_DAY )
                if match_result is None:
                    match_result, img_th = rubyMatch( img_gray, self.template_ruby_night, TH_RUBY_NIGHT )
        except AttributeError:
            self.logger.debug( 'find ruby', stack_info = True)
            
        if match_result is not None and img_th is not None:
            matched = cv2.cvtColor(img_th, cv2.COLOR_GRAY2RGB)
            matchVal,top_left,bottom_right,r = match_result
            
            rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
            rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))

            #cv2.rectangle(matched, rTopLeft,rBottomRight, (0,0,255),5)
            rBox = rTopLeft + rBottomRight
            self.logger.info(  f'ruby match value: {matchVal}' )
            self.rboxList.append(rBox)
            self._emit(ColoraturaSignalKey.addRect, ( rBox, 255,0,0,255, 5 ))
            rx1, ry1, rx2, ry2 = rBox
            pyautogui.moveTo( self.bbox[0] + (rx1+rx2)//2, self.bbox[1] + (ry1+ry2)//2, 1.5 )
            pyautogui.click()
            return True
    
        return False

    def analyzeRobot2Dialog( self, img_gray:np.ndarray, dialogBox:tuple, blueButtonBox:tuple, headlineBox:tuple):

      try:
          dx1, dy1, dx2, dy2 = dialogBox
          dw = dx2 - dx1
          dh = dy2 - dy1
        
          bx1, by1, bx2,by2 = blueButtonBox
          hx2 = headlineBox[2]

          if bx2 + 5 < dx2:
              dx2 = bx2 + 5
              dw = dx2 - dx1
          if by2 + 10 < dy2:
              dy2 = by2 + 10
              dh = dy2 - dy1

          #img_dialog_gray = img_gray[ dy1:dy2, dx1:dx2 ]
          img_dialog_head_gray = img_gray[ dy1 + 5:dy1+int(RATIO_HEAD_IN_DIALOG*dh), hx2:dx2 ]
          img_dialog_head_thresh = cv2.threshold(img_dialog_head_gray, 127, 255, cv2.THRESH_BINARY)[1]
          img_dialog_head_blur = cv2.GaussianBlur(img_dialog_head_thresh,(5,5),0)  #advanced config # blur value
          img_dialog_head_canny = cv2.Canny(img_dialog_head_blur, 50, 100)  #advanced config # canny value

          templateContours = findContourList(img_dialog_head_canny, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

          if templateContours is not None and len(templateContours) > 0:
                
            hHeight, hWidth = img_dialog_head_canny.shape[:2]
                
            template_rects = []
            #aa = cv2.cvtColor(img_dialog_head_thresh,cv2.COLOR_GRAY2RGB)
            for c in templateContours:
                cx,cy,cw,ch = cv2.boundingRect(c)
                if cw * 3 < hWidth and cw * 15 > hWidth and ch * 4 > hHeight and ch < hHeight:
                    template_rects.append((cx,cy,cw,ch))
                    #cv2.drawContours(aa, [c], 0, (255,0,0), 5)

            rects_sorted = sorted( template_rects, key=lambda t: t[0], reverse=False)

            rects_no_duplicates = []
            for i in range(0,len(rects_sorted)):
                if (i > 0) and abs(rects_sorted[i-1][0] - rects_sorted[i][0]) < rects_sorted[i-1][2]:
                    continue
                rects_no_duplicates.append(rects_sorted[i])

            for (rx,ry,rw,rh) in rects_no_duplicates:
                tm_box = (hx2 + rx, dy1 + ry + 5, hx2+ rx + rw, dy1 + ry + rh + 5 )
                self._emit(ColoraturaSignalKey.addRect, (tm_box,0,0,255,255, 1))
                self.crack_tm_box_list += (tm_box,)
        
          if len( self.crack_tm_box_list) > 0:
              self.crack_image_box = ( dx1, dy1+int(RATIO_HEAD_IN_DIALOG*dh), dx2, by1 - 5)
              self._emit(ColoraturaSignalKey.addRect, ( self.crack_image_box, 255,255,0,255, 2))
              self.crack_button_box = blueButtonBox
              self.logger.info( f'dialog: check robot with {len(self.crack_tm_box_list)} template(s)')
          return True
      except Exception as e:
          self.logger.debug( f'analyzing failure {e}', stack_info=True)
      return False

    def crackRobotCheck( self, img_src:np.ndarray, adjustMode:bool = False ):
        if self.crack_image_box is None or self.crack_button_box is None or len(self.crack_tm_box_list)<1:
            self.logger.warning( 'crack data unsatisfied' )
            return

        cx1, cy1, cx2, cy2 = self.crack_image_box
        img_to_crack = img_src[cy1:cy2, cx1:cx2]

        def changeCo(k, i, adj = False):
            if i == 0:
                changeCo.th1 = k
            elif i == 1:
                changeCo.th2 = k
            else:
                changeCo.gbf = k
            gb = changeCo.gbf * 2 + 1
            changeCo.c_dst = cv2.Canny(cv2.GaussianBlur(changeCo.c_src, 
                 (gb,gb),0), 
                 changeCo.th1, changeCo.th2)
            if adj:
                cv2.imshow(changeCo.windowName, changeCo.c_dst)
        
        changeCo.c_src = img_to_crack
        changeCo.th1 = 300
        changeCo.th2 = 300
        changeCo.gbf = 3
        changeCo.windowName = 'Canny'
        changeCo.c_dst = None

        changeCo(300, 0, adj = adjustMode)
    
        if bool(adjustMode):
            cv2.createTrackbar('th1', changeCo.windowName, changeCo.th1, 300, lambda k: changeCo(k, 0, True))
            cv2.createTrackbar('th2', changeCo.windowName, changeCo.th2, 300, lambda k: changeCo(k, 1, True))
            cv2.createTrackbar('gb', changeCo.windowName, changeCo.gbf, 10, lambda k: changeCo(k, 2, True))
            cv2.waitKey(0)
        
        content_canny = changeCo.c_dst

        if content_canny is None:
            return
        content_canny_rgb = cv2.cvtColor(content_canny, cv2.COLOR_GRAY2RGB)

        def matchCrackTemplate( number:int, img_template:np.ndarray, content_canny:np.ndarray):
            template_canny = cv2.Canny(cv2.GaussianBlur(img_template,(1,1),0) , 2, 0)
            self.logger.debug( f'template matching thread#{number} launched' )
            match_result = None
            for thVal in [0.5,0.4,0.3]:
                for angle in np.linspace(360, 0, 180)[::-1]:
                    #self.changeTmRotate.emit( int( angle ))
                    rotated = rotateImage( template_canny, angle)
                    #self.changeTmRotate.emit( rotated )
                    match_result = self.multiScaleMatch( rotated, content_canny,0.2, 0.6, 40, thVal )

                    if match_result is not None:
                        matchScore,tl,br,r = match_result
                        top_left = (int(tl[0]*r), int(tl[1]*r))
                        bottom_right = (int(br[0]*r), int(br[1]*r))
                        cv2.rectangle(content_canny_rgb, top_left,bottom_right, (0,0,255),5)
                        cv2.putText(content_canny_rgb, str(number), top_left, cv2.FONT_HERSHEY_SIMPLEX, 1,(255,255,255))
                        localMatchBox = top_left + bottom_right
                        x1,y1,x2,y2 = localMatchBox
                        globalMatchBox = (cx1+x1, cy1+y1, cx1+x2, cy1+y2)
                        self._emit(ColoraturaSignalKey.addRect, ( globalMatchBox, 255,0,0,255, 2 ))
                        self.logger.debug( f'template matching thread#{number} end')
                        return (number, globalMatchBox)
            return (number, None)

        tmBoxCount = len(self.crack_tm_box_list)
        
        with futures.ThreadPoolExecutor(max_workers=tmBoxCount) as executor:
            matchBoxes = dict()
            futuresGroup = {executor.submit( matchCrackTemplate, int(i+1), img_src[
                self.crack_tm_box_list[i][1]:self.crack_tm_box_list[i][3], 
                self.crack_tm_box_list[i][0]:self.crack_tm_box_list[i][2]], content_canny ):
            i for i in range(0,tmBoxCount)}

            for future in futures.as_completed(futuresGroup):
                num, box = future.result()
                matchBoxes[num] = box
            
            for n in range( 1, len(matchBoxes) + 1):
                box = matchBoxes[n]
                if box is not None:
                    mx1, my1, mx2, my2 = box
                    pyautogui.moveTo( self.bbox[0] + (mx1+mx2)//2, self.bbox[1]+ (my1+my2)//2, 0.5 )
                    pyautogui.click()
            self.logger.debug('all templates clicked')

            bx1, by1, bx2, by2 = self.crack_button_box
            pyautogui.moveTo( self.bbox[0] + (bx1+bx2)//2, self.bbox[1]+ (by1+by2)//2, 1 )
            pyautogui.click()
                               
    def multiScaleMatch( self, template:np.ndarray, img:np.ndarray, min:float=0.01, max:float=4.0, counts:int=40, matchVal:float=0.65 ):
        th, tw = template.shape[:2]
        
        tryCount = 1
        scales = np.linspace(min, max, counts)[::-1]
        index = round(counts / 2) - 1
        for i in range(0, counts):
            index += pow(-1,(i+1)) * i
            if index >= 0 and index < counts:
                try:
                    scale = scales[index]
                except IndexError:
                    self.logger.debug('array out of bounds', stack_info=True)
                    continue
                resized = imResize(img, width = int(img.shape[1] * scale))
                r = img.shape[1] / float(resized.shape[1])
                ratioProgress = int ( 100 / (max-min) * ( 1 / r - min ) )
                #self.changeTmRatio.emit( ratioProgress )
                if resized.shape[0] < th or resized.shape[1] < tw:
                    break
                match_result = template_match(template,resized,self.tmMethod, matchVal)
                if match_result is not None:
                    self.logger.debug(f'template found in {tryCount}try(s) ratio:{str(1/r)}')
                    return match_result + (r,)
            tryCount+=1
            
        return None

    def determineFieldWork(self, coordResult:bool, img_gray:np.ndarray, wf_level:int = 1):
        if self.state_where == self.WHERE_FIELD and coordResult:
            if self.direction < 0:
                self.direction = self.randomGenerator.generateRandomFloat(max=360.0)
                self.logger.debug('random direction generated')
                if wf_level >= LV_MOUSING:
                    try:
                        x1, y1, x2, y2 = self.field_button_box
                        pyautogui.moveTo( self.bbox[0] + (x1+x2)//2, self.bbox[1]+ (y1+y2)//2, 1 )
                        pyautogui.click()
                    except TypeError:
                        self.logger.debug('mousing fail: field_button_box is None')
            else:
                for rbox in self.rboxList:
                    cv2.rectangle( img_gray, (rbox[0],rbox[1]),(rbox[2],rbox[3]),(0,0,0),-1)
                rubyfound = self.findRuby( img_gray ) if wf_level >= LV_FIND_RUBY else False
                if not rubyfound:
                    self.rboxList.clear()
                    if wf_level >= LV_MOUSING:
                        rad = radians(self.direction)
                        mX = (self.bbox[0] + self.bbox[2]) / 2
                        mY = (self.bbox[1] + self.bbox[3]) / 2
                        dragL = min( (self.bbox[3] - self.bbox[1]) * 0.8, (self.bbox[2] - self.bbox[0]) * 0.8)
                        pyautogui.moveTo( int(mX + dragL / 2 * cos(rad)), int(mY - dragL / 2 * sin(rad)), 1 )
                        pyautogui.dragTo( int(mX - dragL / 2 * cos(rad)), int(mY + dragL / 2 * sin(rad)), 1 )
                        pyautogui.moveTo( int(mX + dragL / 2 * cos(rad)), int(mY - dragL / 2 * sin(rad)), 1 )
                        pyautogui.dragTo( int(mX - dragL / 2 * cos(rad)), int(mY + dragL / 2 * sin(rad)), 1 )