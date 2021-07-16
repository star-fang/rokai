from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
import cv2
from PIL import ImageGrab
import numpy as np
import imutils
import os
import re
from pathlib import Path
from shape import ShapeDetector
from threading import Lock

'''
state flow
1.상태체크
 a.팝업 확인 -> normar or dialog
 normal: field or home // 낮밤 : multithreading and join
 field: field or home // 좌표and좌표평가 // 루비 // 부대수 : multithreading and join
 home: to field -> field or home

 field or home : 좌표 -> 좌표확인 -> 중간클릭 -> 팝업 -> 팝업좌표확인 -> 일치 -> 내성 위치저장 and 팝업종료클릭 -> field
                                                                    일치x -> 
                                                    -> 좌표x ->
                                           -> 팝업x -> 다시클릭(팝업까지)
                      -> 좌표x -> 중간클릭 -> 팝업
                                         -> 팝업x
 field 버튼 ox 
 좌표 

'''

TH_BUTTON = 160

TH_RECT_APP = 70

TH_RECT_DIALOG1 = 70
TH_RECT_DIALOG2 = 127
TH_RECT_DIALOG3 = 160

TH_RUBY_DAY = 90
TH_RUBY_NIGHT = 60
TH_NIGHT_AND_DAY = 127
TH_DIALOG = 127
TH_CRACK = 127
RATIO_HEAD_IN_DIALOG = 0.12
TH_CONTRAST_RATIO_WB_ND = 0.3 # lower -> night, upper -> daytime

def globalThresholding(image, tVal=127, isGray=False):
    if isGray:
        img_gray = image
    else:
        img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    return cv2.threshold(img_gray, tVal, 255, cv2.THRESH_BINARY)[1]

def findContourList(img, *args):
    if len(args) < 1:
        print( 'findContourList : no args')
        return None
    print( 'detecting screen using contours (cv2 version: ' + str(cv2.__version__) + ')')
    if (int(cv2.__version__[0]) > 3):
        contours, hierarchy = cv2.findContours(img, mode=args[0], method=args[1])
    else:
        im2, contours, hierarchy = cv2.findContours(img, mode=args[0], method=args[1])

    return contours

def match(template, resized, method, mThreshold):
        th, tw = template.shape[:2]
        match_result = cv2.matchTemplate(resized, template, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match_result)
        targetExist = False
        #in case of TM_SQDIFF, matching value is min value
        #in other case, the opposite is true

        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                top_left = min_loc
                match_val = min_val
                targetExist = bool(match_val < mThreshold)
        else:
                top_left = max_loc
                match_val = max_val
                targetExist = bool(match_val > mThreshold)
                
        #print(str(match_val) + str(targetExist))
            
        if( targetExist ):
                bottom_right = (top_left[0] + tw, top_left[1] + th)
                return (match_val, top_left, bottom_right)
        else:
            return None

def rotateImage( image, angle ):
    center = tuple(np.array(image.shape[1::-1]) / 2)
    rotationMatrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, rotationMatrix, image.shape[1::-1], flags=cv2.INTER_LINEAR )
    return rotated

class SweeperWorkerSignals(QObject):
    changeLocation = pyqtSignal(tuple)
    changeState = pyqtSignal(int)
    reportState = pyqtSignal(str, bool)
    changeScreen = pyqtSignal(object) # image matrix, rect
    changeTemplate = pyqtSignal(object) # image matrix
    changeTmRatio = pyqtSignal(int)
    changeTmRotate = pyqtSignal(int)
    changeBbox = pyqtSignal(tuple)
    finished = pyqtSignal()

class SweeperWorkFlowSignals(QObject):
    finished = pyqtSignal()

class SweeperWorkFlow(QRunnable):
    FLOW_IDF_STATE = 0
    
    def run(self):
        if( self.flow == self.FLOW_IDF_STATE):
          if self.sweeper.captureScreen():
              self.workerSignals.reportState.emit('', False)
              dialogDetected = self.sweeper.detectDialog(self.workerSignals)
              if not dialogDetected:
                mutex = Lock()
                whenWorker = SweeperWorker(self.sweeper, work=SweeperWorker.WORK_WHEN, mutex=mutex, signals= self.workerSignals)
                coordsWorker = SweeperWorker(self.sweeper, work=SweeperWorker.WORK_COORDINATES, mutex=mutex, signals= self.workerSignals)
                whereWorker = SweeperWorker(self.sweeper, work=SweeperWorker.WORK_WHERE, mutex=mutex, signals= self.workerSignals)
                countTrpsWorker = SweeperWorker(self.sweeper, work=SweeperWorker.WORK_CNT_TROOPS, mutex=mutex, signals= self.workerSignals)
                checkRobotWorker = SweeperWorker(self.sweeper, work=SweeperWorker.WORK_CHECK_ROBOT, mutex=mutex, signals= self.workerSignals)

                pool = QThreadPool()
                pool.start(whenWorker)
                pool.start(coordsWorker)
                pool.start(whereWorker)
                pool.start(countTrpsWorker)
                pool.start(checkRobotWorker)

                r = pool.waitForDone()
                print(f'pool result:{r}')
        self.signals.finished.emit()

    def __init__(self, sweeper, *args, flow:int = 0):
        QRunnable.__init__(self)
        self.flow = flow
        self.sweeper = sweeper
        self.workerSignals = SweeperWorkerSignals()
        self.signals = SweeperWorkFlowSignals()
        self.args = args
        if args is not None and len(args)> 0:
            print( f'args of work flow: {args}')

    def getWorkerSignals(self):
        return self.workerSignals
    
    def getSignals(self):
        return self.signals

class SweeperWorker(QRunnable):
    WORK_DETECT_SCREEN = 0

    WORK_DIALOG_DET = 1 # find rect contours -> dialog / normal
    #WORK_DIALOG_IDF = 2 # 

    WORK_WHEN = 3 # night and day
    WORK_COORDINATES = 4 # x,y
    WORK_WHERE = 5 # home or field
    WORK_CHECK_ROBOT = 6 # check robot button appeared
    WORK_CNT_TROOPS = 7 # current troops count a / b

    WORK_CRACK = 8
    WORK_RUBY = 9

    #normal state -> night and day
    #             -> coordinates ( left upper )
    #             -> field or home ( left lower )
    #             -> check robot button ( right upper )
    #             -> check troops count ( right middle )
    # => join and report

    #dialog state -> check robot -> crack
    #             -> troop
    #             -> ruby dialog
    #             -> rss dialog
    #             -> unkown dialog

    def run(self):
        if( self.work == self.WORK_DIALOG_DET):
            bbox = self.sweeper.detectDialog(self.signals)
            self.sweeper.identifyDialog(bbox, self.signals)
        #elif( self.work == self.WORK_DIALOG_IDF):
            
        elif( self.work == self.WORK_COORDINATES):
            self.sweeper.detectCoordinates(self.signals, self.mutex)
        elif( self.work == self.WORK_WHERE):
            self.sweeper.checkFieldOrHome(self.signals, self.mutex)
        elif( self.work == self.WORK_WHEN):
            self.sweeper.detectNightAndDay(self.signals, self.mutex)
        elif( self.work == self.WORK_CHECK_ROBOT):
            print('check robot')
        elif( self.work == self.WORK_CNT_TROOPS):
            print('count troops')
        elif( self.work == self.WORK_RUBY):
            self.sweeper.findRuby(self.signals)
        elif( self.work == self.WORK_CRACK):
            self.sweeper.crackRobotCheck( self.signals )
        elif( self.work == self.WORK_DETECT_SCREEN):
            self.sweeper.detectScreen(self.signals, self.args)
        self.signals.finished.emit()

    def __init__(self, sweeper, *args, work:int = 0, mutex: Lock = None, signals = None):
        QRunnable.__init__(self)
        self.work = work
        self.sweeper = sweeper
        if signals is None:
            self.signals = SweeperWorkerSignals()
        else:
            self.signals = signals
        self.args = args
        self.mutex = mutex
        if args is not None and len(args)> 0:
            print( f'args of worker: {args}')

    def getSignals(self):
        return self.signals

#A ruby finder in rok
class Sweeper():

    TIME_NIGHT = 0
    TIME_DAY = 1
    
    NO_DIALOG = 0
    DIALOG_ROBOT1 = 1
    DIALOG_ROBOT2 = 2
    DIALOG_UNKNOWN = 3



    def __init__(self, ocr, methodName='cv2.TM_CCOEFF_NORMED'):
        
        
        if methodName is not None:
            self.setMethodName(methodName)
        self.ocr = ocr
        self.bbox = (0,0,100,100)
        self.img_src:np.ndarray = None
        self.loadTmImages()
        self.shapeDetector = ShapeDetector()

    def loadTmImages(self):
        source_path = Path(__file__).resolve()
        assets_dir = str(source_path.parent) + '/assets'

        self.template_ruby_day = globalThresholding(cv2.imread(f'{assets_dir}/ruby_day.png'), tVal=TH_RUBY_DAY)
        self.template_ruby_night = globalThresholding(cv2.imread(f'{assets_dir}/ruby_night.png'), tVal=TH_RUBY_NIGHT)

        self.template_to_field = globalThresholding(cv2.imread(f'{assets_dir}/btn_to_field.png'), tVal=TH_BUTTON)
        self.template_to_home = globalThresholding(cv2.imread(f'{assets_dir}/btn_to_home.png'), tVal=TH_BUTTON)

        self.template_robot_check = globalThresholding(cv2.imread(f'{assets_dir}/btn_robot.png'), tVal=TH_BUTTON)
        self.template_expand_troops = globalThresholding(cv2.imread(f'{assets_dir}/btn_expand_troops.png'), tVal=TH_BUTTON)

        #cv2.imshow('tm_field', self.template_to_field)
        #cv2.imshow('tm_home', self.template_to_home)
        #cv2.imshow('tm_robot', self.template_robot_check)
        #cv2.imshow('tm_expand', self.template_expand_troops)
    
    def setMethodName(self, name):
        self.methodName = name
        self.method = eval(name)

    def checkFieldOrHome(self, signals: SweeperWorkerSignals, mutex:Lock):
        if self.img_src is None or not isinstance(self.img_src,np.ndarray):
            print('no image source')
            return
        imgHeight, imgWidth = self.img_src.shape[:2]
        img_left_lower = self.img_src[int( imgHeight*0.7 ): imgHeight, 0: int( imgWidth * 0.3)]
        try:
            img_th = globalThresholding(img_left_lower, TH_BUTTON)
            
            match_result = self.multiScaleMatch( self.template_to_home, img_th, signals = signals )

            if match_result is not None:
                matched = cv2.cvtColor(img_th, cv2.COLOR_GRAY2RGB)
                matchVal,top_left,bottom_right,r = match_result
                restoredTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
                restoredBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))

                signals.reportState.emit('where: field',True)
            else:
                match_result = self.multiScaleMatch( self.template_to_field, img_th, signals = signals )
                if match_result is not None:
                    signals.reportState.emit('where: home',True)

            if match_result is None:
               signals.reportState.emit('where: ??',True) 

        except Exception as e:
            signals.reportState.emit(f'where: {e}',True)

    def detectCoordinates(self, signals:SweeperWorkerSignals, mutex:Lock):
        if self.img_src is None or not isinstance(self.img_src,np.ndarray):
            print('no image source')
            return
        imgHeight, imgWidth = self.img_src.shape[:2]

        img_topLeft = self.img_src[0:int(imgHeight*0.1),0:int(imgWidth*0.5)]

        rectExist,bbox, detected  = self.selectBigRectContour(img_topLeft,150, minRate=0.1, maxRate=0.6)
       
        if rectExist:
            try:
                x,y,x2,y2 = bbox
                w = x2-x
                h = y2-y
                coords_part = img_topLeft[y+int(0.1*h):y+int(0.8*h),x+w:x+int(2.1*w)]

                #coords_yuv = cv2.cvtColor(coords_part, cv2.COLOR_BGR2YUV)
                #oords_yuv[:, :, 0] = cv2.equalizeHist(coords_yuv[:, :, 0])
                #coords_rgb = cv2.cvtColor(coords_yuv, cv2.COLOR_YUV2RGB)
    
                coords_txt = self.ocr.read(coords_part,config='-l eng --oem 1 --psm 7')
                coords_txt = coords_txt.replace('\n',' ')
                
                txt = re.sub('\D',' ', coords_txt)
                
                split = re.split('\s+', txt)
                split = [e for e in split if e != '']
                if( len(split) != 3 ):
                    coords_gray = 255-cv2.cvtColor(coords_part, cv2.COLOR_BGR2GRAY)
                    ret,coord_removed_bg = self.ocr.removeBackground(coords_gray, kernel1=1, kernel2=5)

                    coords_txt = self.ocr.read(coord_removed_bg,config='-l eng --oem 1 --psm 7')
                    coords_txt = coords_txt.replace('\n',' ')
                    txt = re.sub('\D',' ', coords_txt)
                    
                    split = re.split('\s+', txt)
                    split = [e for e in split if e != '']

                signals.reportState.emit( f'location(ocr): {coords_txt}', True )
                if( len(split) == 3):
                    digits = tuple()
                    for i in range(0,3):
                        digits += ( int(split[i]), )
                    signals.changeLocation.emit(digits)
                    signals.reportState.emit( f'location: #{digits[0]} x{digits[1]} y{digits[2]}', True )
                return
            except Exception as e:
                signals.reportState.emit(f'ocr error:{e}', True)
            signals.reportState.emit('no coordinates info', True)

    def captureScreen( self ):
        try:
            # delete overlay componenets, move mouse to right lower part
            img_pil = ImageGrab.grab(bbox=self.bbox)
            self.img_src = np.array(img_pil)
        except:
            return False
        return True

    def identifyDialog(self, bbox, signals: SweeperWorkerSignals):
        if self.img_src is None or not isinstance(self.img_src,np.ndarray):
            print('no image source')
            return
            
        x, y, x2, y2 = bbox
        w = x2 - x
        h = y2 - y
        part_to_ocr = self.img_src[y:y+int(h*RATIO_HEAD_IN_DIALOG),x:x+w]
        part_gray, part_thresh = self.ocr.preprocessing( part_to_ocr )

        ocr_txt = str(self.ocr.read(part_thresh,config='-l kor --oem 1 --psm 7'))
        orc_txt_no_lines = os.linesep.join([s for s in ocr_txt.splitlines() if s])
        ocr_txt_no_blank = orc_txt_no_lines.replace(' ','')
        print('ocr_in_block(thresh):' + ocr_txt_no_blank)

        if( ocr_txt_no_blank == ''):
            ocr_txt = str(self.ocr.read(part_gray,config='-l kor --oem 1 --psm 7'))
            orc_txt_no_lines = os.linesep.join([s for s in ocr_txt.splitlines() if s])
            ocr_txt_no_blank = orc_txt_no_lines.replace(' ','')
            print('ocr_in_block(gray):' + ocr_txt_no_blank)
      
        if '사용' in ocr_txt_no_blank:
            signals.changeState.emit(self.DIALOG_ROBOT2)
            signals.reportState.emit('state: check robot2', True)
        elif '보상' in ocr_txt_no_blank:
            signals.changeState.emit(self.DIALOG_ROBOT1)
            signals.reportState.emit('state: check robot1', True)
        else:
            signals.changeState.emit(self.DIALOG_UNKNOWN)
            signals.reportState.emit('state: unknown', True)

    
    def detectDialog(self, signals: SweeperWorkerSignals):
        if self.img_src is None or not isinstance(self.img_src,np.ndarray):
            print('no image source')
            return True

        for th in [TH_RECT_DIALOG2, TH_RECT_DIALOG3]:
            contourExist, bbox, detected = self.selectBigRectContour(self.img_src, th, minRate=0.05, maxRate=0.6, max = True)
            if contourExist:
                break
        if contourExist:
            self.identifyDialog( bbox, signals )
            return True
        else:
            img_rgb = cv2.cvtColor( self.img_src, cv2.COLOR_BGR2RGB )
            signals.changeScreen.emit( img_rgb )
            signals.changeState.emit(self.NO_DIALOG)
            signals.reportState.emit('state: normal', True)
            return False

    def selectBigRectContour( self, img_src: np.ndarray, tVal, minRate=0.7, maxRate = 1.0, max = False ):
        resized = imutils.resize(img_src, width = 300)
        ratio = img_src.shape[0] / float(resized.shape[0])

        gray = cv2.cvtColor( resized, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray,(3,3), 0 )
        img_thresh = globalThresholding(blurred, tVal, isGray= True)

        contours = findContourList(img_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        detected = cv2.cvtColor(img_thresh,cv2.COLOR_GRAY2RGB)
        contoursCount = len(contours)
        if contoursCount > 0:
            #cv2.imshow('aa', detected)
            #cv2.waitKey()
            ih,iw = resized.shape[:2]
            contours.sort(key = cv2.contourArea, reverse=True)
            fitContour = None
            for i in range( 0, contoursCount):
                contour = contours[i]
                shape = self.shapeDetector.detect(contour)
                cw,ch = cv2.boundingRect(contour)[2:]
                areaCont = cw * ch
                areaImg = iw * ih
                if areaCont >= minRate * areaImg and areaCont <= maxRate * areaImg:
                    if  shape == ShapeDetector.SHAPE_RECTANGLE or shape == ShapeDetector.SHAPE_SQUARE:
                        fitContour = contour
                        if max:
                            break
                else:
                    print( f'bigContourFinder: stopped in {str(i)}try(s)')
                    break
            if fitContour is not None:
                a, b, c, d = cv2.boundingRect(fitContour)
                brect = [a, b, c, d]
                for i in range(0, len(brect)):
                    brect[i] = int( brect[i] * ratio )
                x, y, w, h = brect
                cv2.rectangle(detected, (a,b),(a+c,b+d), (0,255,0),3)
                return (True, (x,y,x+w,y+h), detected)
        return (False,None,detected)
            
    def detectNightAndDay( self, signals: SweeperWorkerSignals, mutex:Lock ):
        if self.img_src is None or not isinstance(self.img_src,np.ndarray):
            print('no image source')
            return
        img_thresh = globalThresholding( self.img_src, tVal = TH_NIGHT_AND_DAY )

        number_of_white = np.sum(img_thresh == 255)
        number_of_black = np.sum(img_thresh == 0)

        wbRatio = round(number_of_white/number_of_black, 2)
        print( 'white/balck : ' + str(wbRatio) )
        
        daytime = bool(TH_CONTRAST_RATIO_WB_ND < wbRatio)
        
        if daytime is True:
            self.time = self.TIME_DAY
            signals.reportState.emit(f'contrast ratio: {str(wbRatio)}\ntime: daytime', True)
        else:
            self.time = self.TIME_NIGHT
            signals.reportState.emit(f'contrast ratio: {str(wbRatio)}\ntime: night', True)
            

    def detectScreen(self, signals: SweeperWorkerSignals, args=None):
        if args is None or len(args)==0:
            print( 'no args')
            return
        rect = args[0]
        if rect is None or not isinstance(rect, tuple) or len(rect) != 4 or not all(isinstance(n,int) for n in rect):
            print( f'no rect: {str(rect)}')
            return

        img_pil = ImageGrab.grab(bbox=[rect[0],rect[1],rect[0]+rect[2],rect[1]+rect[3]] )
        img_src = np.array(img_pil)

        contourExist, bbox, detected = self.selectBigRectContour(img_src, TH_RECT_APP, minRate=0.6)
        
        if contourExist is True:
            x1, y1 = rect[:2]
            x3, y3, x4, y4 = bbox
            self.bbox = (x1 + x3, y1 + y3, x1 + x4, y1 + y4)
            signals.changeBbox.emit( bbox )
        signals.changeScreen.emit( detected )

    def findRuby(self, signals: SweeperWorkerSignals):
        if self.img_src is None or not isinstance(self.img_src,np.ndarray):
            print('no image source')
            return
        
        img_th = None
        match_result = None

        try:
            if( self.time == self.TIME_DAY ):
                signals.changeTemplate.emit( self.template_ruby_day )
                img_th = globalThresholding(self.img_src, TH_RUBY_DAY)
                match_result = self.multiScaleMatch( self.template_ruby_day, img_th, signals = signals )
            elif( self.time == self.TIME_NIGHT ):
                signals.changeTemplate.emit( self.template_ruby_night )
                img_th = globalThresholding(self.img_src, TH_RUBY_NIGHT)
                match_result = self.multiScaleMatch( self.template_ruby_night, img_th, signals = signals )
        except AttributeError:
            print('attribute error')
            
        
        if img_th is not None:
            signals.changeScreen.emit( img_th )
        if match_result is not None:
            matched = cv2.cvtColor(img_th, cv2.COLOR_GRAY2RGB)
            matchVal,top_left,bottom_right,r = match_result
            
            restoredTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
            restoredBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))

            cv2.rectangle(matched, restoredTopLeft,restoredBottomRight, (0,0,255),5)
            signals.changeScreen.emit(matched)
            #self.setViewText('보석 발견 (매칭값: '+str(matchVal)+')')
            return ( 
                (restoredTopLeft[0]+restoredBottomRight[0]) // 2 + self.bbox[0],
                (restoredTopLeft[1]+restoredBottomRight[1]) // 2 + self.bbox[1] )
        else:
            #self.setViewText('보석 없심더...')

            return None

    def onChange_th1(self, k):
        if k > 0:
            self.th1 = k
            self.c_dst = cv2.Canny(cv2.GaussianBlur(self.c_src,(self.gb,self.gb),0) , self.th1, self.th2)
            cv2.imshow(self.windowName, self.c_dst)
    
    def onChange_th2(self, k):
        if k > 0:
            self.th2 = k
            self.c_dst = cv2.Canny(cv2.GaussianBlur(self.c_src,(self.gb,self.gb),0) , self.th1, self.th2)
            cv2.imshow(self.windowName, self.c_dst)
            
    def onChange_gb(self, k):
        self.gb = k * 2 + 1
        self.c_dst = cv2.Canny(cv2.GaussianBlur(self.c_src,(self.gb,self.gb),0) , self.th1, self.th2)
        cv2.imshow(self.windowName, self.c_dst) 

    def crackRobotCheck( self, signals: SweeperWorkerSignals, adjustMode=False ):
        if self.img_src is None or not isinstance(self.img_src,np.ndarray):
            print('no image source')
            return
        #thresholding -> (multiscale <> ratate matching) -> click
        
        img_thresh = globalThresholding(self.img_src, TH_CRACK)

        contours = findContourList(img_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) > 0:
            if len(contours) > 1:
                contours.sort(key = cv2.contourArea, reverse=True)
                c = contours[0]
            else:
                c = contours[0]
            
            x,y,w,h = cv2.boundingRect(c)

            #img_dialog_head = cv2.cvtColor(np.array(img_pil)[y+2:y+2+int(0.2*h),x:x+w],cv2.COLOR_BGR2GRAY)
            
            #img_src_head = img_src[y:y+int(0.12*h),x:x+w]
            img_dialog_head_thresh = img_thresh[y:y+int(RATIO_HEAD_IN_DIALOG*h),x:x+w]
            img_dialog_head_blur = cv2.GaussianBlur(img_dialog_head_thresh,(3,3),0)  #advanced config # blur value
            img_dialog_head_canny = cv2.Canny(img_dialog_head_blur, 50, 100)  #advanced config # canny value

            #img_dialog = img_src[y:y+h,x:x+w]
            img_dialog_content= self.img_src[y+int(RATIO_HEAD_IN_DIALOG*h):y+h,x:x+w]
            img_dialog_head = self.img_src[y:y+int(RATIO_HEAD_IN_DIALOG*h),x:x+w]
            
            
            signals.changeScreen.emit( img_dialog_head_thresh )
            #ocr_txt = self.ocr.read(img_dialog_head_thresh,config='-l kor --oem 1 --psm 3')
            #print(ocr_txt)
            #if '사용' not in str(ocr_txt).replace(' ',''):
                #self.stateReport.emit('인증 화면 인식 실패')
                #print(ocr_txt)
                #return False

           
            contours_in_dialog = findContourList(img_dialog_head_canny, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            if (contours_in_dialog is not None) and (len(contours_in_dialog) > 0):
                
                headHeight, headWidth = img_dialog_head_canny.shape[:2]
                head_area = headHeight * headWidth
                
                template_rects = []
                for c in contours_in_dialog:
                    cx,cy,cw,ch = cv2.boundingRect(c)
                    area = cw * ch
                    
                    if (area * 65 > head_area) and (cw * 10 < headWidth) and (cx > headWidth // 2):
                        template_rects.append((cx,cy,cw,ch))

                rects_sorted = sorted( template_rects, key=lambda t: t[0], reverse=False)

                rects_no_duplicates = []
                for i in range(0,len(rects_sorted)):
                    if (i > 0) and abs(rects_sorted[i-1][0] - rects_sorted[i][0]) < rects_sorted[i-1][2]:
                        continue
                    rects_no_duplicates.append(rects_sorted[i])

                head_color = cv2.cvtColor(img_dialog_head_thresh, cv2.COLOR_GRAY2RGB)
                cI = 0
                for (rx,ry,rw,rh) in rects_no_duplicates:
                    c += 1
                    cv2.rectangle(head_color,(rx,ry),(rx+rw,ry+rh),(0,0,255), 1)
                    cv2.putText(head_color, str(cI), (rx,ry), cv2.FONT_HERSHEY_SIMPLEX, 1,(255,255,255))
                signals.changeScreen.emit( head_color )

                cI = 0
                self.c_src = img_dialog_content
                self.th1 = 300
                self.th2 = 300
                self.gb = 7
                self.c_dst = cv2.Canny(cv2.GaussianBlur(self.c_src,(self.gb,self.gb),0) , self.th1, self.th2)
                if bool(adjustMode):
                    cv2.imshow('Canny',self.c_dst)
                    self.windowName = 'Canny'
                    cv2.createTrackbar('th1', 'Canny', 0, 300, self.onChange_th1)
                    cv2.createTrackbar('th2', 'Canny', 0, 300, self.onChange_th2)
                    cv2.createTrackbar('gb', 'Canny', 0, 10, self.onChange_gb)
                    cv2.waitKey()

                content_canny = self.c_dst
                signals.changeScreen.emit( content_canny )

                '''
                a = cv2.GaussianBlur(img_dialog_content,(9,9),0)  #advanced config # blur value
                b = cv2.Canny(a, 300, 300)  #advanced config # canny value
                cv2.imshow('canny', b)
                cv2.waitKey()
                '''

                self.c_src = img_dialog_head
                self.c_dst = self.c_src.copy()
                
                
                self.th1 = 2
                self.th2 = 0
                self.gb = 1
                self.c_dst = cv2.Canny(cv2.GaussianBlur(self.c_src,(self.gb,self.gb),0) , self.th1, self.th2)
                if bool(adjustMode):
                    cv2.imshow('Template',self.c_dst)
                    self.windowName = 'Template'
                    cv2.namedWindow('Template',cv2.WINDOW_NORMAL)
                    cv2.resizeWindow('Template', 300,300)
                    cv2.createTrackbar('th1', 'Template', 0, 300, self.onChange_th1)
                    cv2.createTrackbar('th2', 'Template', 0, 300, self.onChange_th2)
                    cv2.createTrackbar('gb', 'Template', 0, 10, self.onChange_gb)
                    cv2.waitKey()

                templates_canny = self.c_dst
                detected = cv2.cvtColor(content_canny, cv2.COLOR_GRAY2RGB)

                for (rx,ry,rw,rh) in rects_no_duplicates:
                        cI += 1

                        template_canny = templates_canny[ry:ry+rh, rx:rx+rw]
                        signals.changeTemplate.emit( template_canny )
                        print( '----- template matching #'+ str(cI)+' ----')

                        match_result = None
                        for matchVal in [0.5,0.4,0.3]:
                            print( ' -> threshold: ' + str(matchVal))
                            for angle in np.linspace(360, 0, 180)[::-1]:
                                signals.changeTmRotate.emit( int( angle ))
                                #print( 'angle:' + str(angle))
                                rotated = rotateImage( template_canny, angle)
                                signals.changeTmRotate.emit( rotated )
                                #self.setViewText(str(cI)+"번째 매칭 진행중 (angle:"+ str(angle)+")")
                                match_result = self.multiScaleMatch( rotated, content_canny,0.2, 0.6, 40, matchVal, signals )

                                if match_result is not None:
                                    matchScore,tl,br,r = match_result
                                    top_left = (int(tl[0]*r), int(tl[1]*r))
                                    bottom_right = (int(br[0]*r), int(br[1]*r))
                                    cv2.rectangle(detected, top_left,bottom_right, (0,0,255),5)
                                    cv2.putText(detected, str(cI), top_left, cv2.FONT_HERSHEY_SIMPLEX, 1,(255,255,255))
                                
                                    print( 'match score:' + str(matchScore) )
                                    signals.changeScreen.emit( detected )
                                    break
                            
                            if match_result is not None:
                                break
                            else:
                                print( ' ---')
                        
             
    def multiScaleMatch( self, template, img, min=0.1, max=2.5, counts=20, matchVal=0.7, signals = None ):
        th, tw = template.shape[:2]
        
        i = 0
        for scale in np.linspace(min, max, counts)[::-1]:
            resized = imutils.resize(img, width = int(img.shape[1] * scale))
            r = img.shape[1] / float(resized.shape[1])
            if signals is not None:
                ratioProgress = int ( 100 / (max-min) * ( 1 / r - min ) )
                signals.changeTmRatio.emit( ratioProgress )
            if resized.shape[0] < th or resized.shape[1] < tw:
                break
            match_result = match(template,resized,self.method, matchVal)
            if match_result is not None:
                print('template found in ' + str(i+1) + 'try(s) ratio: ' +  str(1/r) )
                return match_result + (r,)
            i+=1
            
        return None
            




