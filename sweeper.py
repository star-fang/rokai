from concurrent import futures
from PyQt5.QtCore import QMutex, QObject, QRunnable, QWaitCondition, pyqtSignal, pyqtSlot
import cv2
from PIL import ImageGrab
import numpy as np
import imutils
import os
import re
import pyautogui
from pathlib import Path
from shape import ShapeDetector
from concurrent.futures import ThreadPoolExecutor

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

TH_BUTTON0 = 160
TH_BUTTON1= 180
TH_BUTTON2 = 200
TH_BUTTON3 = 220

TH_RECT_APP = 70

TH_RECT_DIALOG1 = 60
TH_RECT_DIALOG2 = 127
TH_RECT_DIALOG3 = 160

TH_HEADLINE = 170

TH_RUBY_IN_DIALOG = 150
TH_RUBY_DAY = 90
TH_RUBY_NIGHT = 60
TH_NIGHT_AND_DAY = 127
TH_DIALOG = 127
TH_CRACK = 127
RATIO_HEAD_IN_DIALOG = 0.12
RATIO_LOWER_DIALOG = 0.7
TH_CONTRAST_RATIO_WB_ND = 0.3 # lower -> night, upper -> daytime

def findContourList(img, *args):
    if len(args) < 1:
        print( 'findContourList : no args')
        return None
    #print( 'detecting screen using contours (cv2 version: ' + str(cv2.__version__) + ')')
    if (int(cv2.__version__[0]) > 3):
        contours, hierarchy = cv2.findContours(img, mode=args[0], method=args[1])
    else:
        im2, contours, hierarchy = cv2.findContours(img, mode=args[0], method=args[1])

    return contours

def selectContours( img_gray: np.ndarray, tVal = 127):
        resized = imutils.resize(img_gray, width = 300)
        ratio = img_gray.shape[0] / float(resized.shape[0])
        blurred = cv2.GaussianBlur(resized,(3,3), 0 )
        img_thresh = cv2.threshold(blurred, tVal, 255, cv2.THRESH_BINARY)[1]
        contours = findContourList(img_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        return (contours, img_thresh, ratio)

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
    finished = pyqtSignal()

class SweeperWorkFlowSignals(QObject):
    finished = pyqtSignal()

class SweeperWorkFlow(QRunnable):
    FLOW_IDF_STATE = 0
    
    def run(self):
        if( self.flow == self.FLOW_IDF_STATE):
            self.sweeper.initWorkFlowData()
            captured = self.sweeper.captureScreen()
            if captured is not None:
                img_src, img_gray = captured
                dialogBox = self.sweeper.detectDialog()
                if dialogBox is None:
                    with ThreadPoolExecutor() as executor:
                        whenFuture = executor.submit( self.sweeper.detectNightAndDay, img_gray )
                        coordsFuture = executor.submit( self.sweeper.detectCoordinates, img_src, img_gray )
                        whereFuture =  executor.submit( self.sweeper.checkFieldOrHome, img_gray )
                        troopsFuture =  executor.submit( self.sweeper.checkCurrentTroops, img_src, img_gray )
                        
                        #countTrpsWorker = SweeperWorker(self.sweeper, work=SweeperWorker.WORK_CNT_TROOPS)
                        #checkRobotWorker = SweeperWorker(self.sweeper, work=SweeperWorker.WORK_CHECK_ROBOT)

                        whenResult = whenFuture.result()
                        coordsResult = coordsFuture.result()
                        whereResult = whereFuture.result()
                        troopsResult = troopsFuture.result()
                        print(f'when:{whenResult}, where:{whereResult}, coords:{coordsResult}')


                else:
                    self.sweeper.identifyDialog( dialogBox, img_src, img_gray )

        self.signals.finished.emit()

    def __init__(self, sweeper, *args, flow:int = 0):
        QRunnable.__init__(self)
        self.flow = flow
        self.sweeper = sweeper
        self.signals = SweeperWorkFlowSignals()
        self.args = args
        #if args is not None and len(args)> 0:
        #    print( f'args of work flow: {args}')

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
            self.sweeper.detectDialog()
        #elif( self.work == self.WORK_DIALOG_IDF):
            
        elif( self.work == self.WORK_COORDINATES):
            self.sweeper.detectCoordinates()
        elif( self.work == self.WORK_WHERE):
            self.sweeper.checkFieldOrHome()
        elif( self.work == self.WORK_WHEN):
            self.sweeper.detectNightAndDay()
        elif( self.work == self.WORK_CHECK_ROBOT):
            print('check robot')
        elif( self.work == self.WORK_CNT_TROOPS):
            print('count troops')
        elif( self.work == self.WORK_RUBY):
            self.sweeper.findRuby()
        elif( self.work == self.WORK_CRACK):
            self.sweeper.crackRobotCheck()
        elif( self.work == self.WORK_DETECT_SCREEN):
            self.sweeper.detectScreen(self.args)
        self.signals.finished.emit()

    def __init__(self, sweeper, *args, work:int = 0):
        QRunnable.__init__(self)
        self.work = work
        self.sweeper = sweeper
        self.signals = SweeperWorkerSignals()
        self.args = args
        #if args is not None and len(args)> 0:
        #    print( f'args of worker: {args}')

class Sweeper( QObject ):

    WHERE_NONE = 0
    WHERE_FIELD = 1
    WHERE_HOME = 2
    
    WHEN_NONE = 0
    WHEN_NIGHT = 1
    WHEN_DAY = 2
    
    NO_DIALOG = 0
    DIALOG_ROBOT1 = 1
    DIALOG_ROBOT2 = 2
    DIALOG_UNKNOWN = 3
    DIALOG_RUBY0 = 4
    DIALOG_RUBY1 = 5
    DIALOG_RUBY2 = 6


    changeLocation = pyqtSignal(tuple) # to minimap

    changeState = pyqtSignal(int)
    reportState = pyqtSignal(str, bool)
    changeScreen = pyqtSignal(object) # image matrix, rect
    changeTemplate = pyqtSignal(object) # image matrix
    changeTmRatio = pyqtSignal(int)
    changeTmRotate = pyqtSignal(int) 

    changeBbox = pyqtSignal(tuple) # draw overlay bbox
    addRect = pyqtSignal(tuple, int, int ,int ,int, int) # draw ovetlay rects, rgba, thickness
    clearRects = pyqtSignal(QWaitCondition)

    def __init__(self, ocr, methodName='cv2.TM_CCOEFF_NORMED', parent = None):
        QObject.__init__(self, parent)
        
        if methodName is not None:
            self.setMethodName(methodName)
        self.ocr = ocr
        self.bbox:tuple = None
        self.img_src:np.ndarray = np.ndarray((1,1,1))
        #print( self.img_src.shape )
        self.loadTmImages()
        self.shapeDetector = ShapeDetector()

        self.crack_tm_box_list = list()
        self.initStateFlags()
        self.initWorkFlowData()

    def initStateFlags(self):
        self.state_when:int = self.WHEN_NONE
        self.state_where:int = self.WHERE_NONE
        self.state_dialog:int = self.NO_DIALOG
    
    def initWorkFlowData(self):
        self.crack_tm_box_list.clear()
        self.crack_image_box:tuple = None
        self.crack_button_box:tuple = None

        self.field_home_button_box:tuple = None
        self.ruby_button_box:tuple = None


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
                                                     TH_BUTTON1, 255, cv2.THRESH_BINARY)[1]
        self.template_expand_troops = cv2.threshold(cv2.imread(f'{assets_dir}/btn_expand_troops.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_BUTTON0, 255, cv2.THRESH_BINARY)[1]
        self.template_head_robot1 = cv2.threshold(cv2.imread(f'{assets_dir}/head_robot1.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_HEADLINE, 255, cv2.THRESH_BINARY)[1]
        self.template_head_robot2 = cv2.threshold(cv2.imread(f'{assets_dir}/head_robot2.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_HEADLINE, 255, cv2.THRESH_BINARY)[1]

    def setMethodName(self, name):
        try:
            self.methodName = name
            self.method = eval(name)
        except Exception as e:
            print( f'Exception: {e}')

    def checkFieldOrHome(self, img_gray:np.ndarray = None):
        if img_gray is None:
            img_gray = cv2.cvtColor(self.img_src,cv2.COLOR_BGR2GRAY)

        imgHeight, imgWidth = img_gray.shape[:2]
        pY = int( imgHeight*0.7 )
        pX = 0
        img_left_lower = img_gray[pY: imgHeight, 0: int( imgWidth * 0.3)]
        try:
            img_th = cv2.threshold(img_left_lower, TH_BUTTON1, 255, cv2.THRESH_BINARY)[1]
            self.changeTemplate.emit( self.template_to_home)            
            match_result = self.multiScaleMatch( self.template_to_home, img_th )

            if match_result is not None:
                self.reportState.emit('where: field',True)
                self.state_where = self.WHERE_FIELD
                
            else:
                self.changeTemplate.emit( self.template_to_field) 
                match_result = self.multiScaleMatch( self.template_to_field, img_th)
                if match_result is not None:
                    self.reportState.emit('where: home',True)
                    self.state_where = self.WHERE_HOME

            if match_result is not None:
                matchVal,top_left,bottom_right,r = match_result
                rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
                rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
                buttonBox = rTopLeft + rBottomRight
                x1,y1,x2,y2 = buttonBox
                self.addRect.emit( (pX+x1, pY+y1, pX+x2, pY+y2),
                                    255,0,0,255, 4  )
                return True

            if match_result is None:
               self.reportState.emit('where: ??',True)

        except Exception as e:
            self.reportState.emit(f'where: {e}',True)
        self.state_where = self.WHERE_NONE
        return False

    def checkCurrentTroops( self, img_src:np.ndarray=None, img_gray:np.ndarray=None):
        if img_src is None:
            img_src = self.img_src.copy()
        if img_gray is None:
            img_gray = cv2.cvtColor(img_src,cv2.COLOR_BGR2GRAY)
        h, w = img_gray.shape[:2]
        ix = int(0.9*w)
        iy = int(0.1*h)
        img_right_bar = img_gray[ iy:h-iy, ix: w ]
        img_right_bar_thresh = cv2.threshold(img_right_bar, TH_BUTTON1, 255, cv2.THRESH_BINARY)[1]

        match_result = self.multiScaleMatch(self.template_expand_troops, img_right_bar_thresh)
        if match_result is not None:
            matchVal,top_left,bottom_right,r = match_result
            rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
            rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
            localExpandButtonBox = rTopLeft + rBottomRight
            x1,y1,x2,y2 = localExpandButtonBox
            buttonWidth = x2 - x1
            tmpBox = (ix+x2, iy+y1, w, iy+y2)
            tx1, ty1, tx2, ty2 = tmpBox
            tw = tx2 - tx1
            th = ty2 - ty1
            if tw > 3*buttonWidth:
                try:
                    tx1 += buttonWidth // 2
                    tx2 -= buttonWidth
                    ty2 = int( ty2 - 0.15*th )
                    globalTroopsCountBox = (tx1, ty1, tx2 , ty2)
                    self.addRect.emit( globalTroopsCountBox,255,0,255,255, 2 )
                    cnt_gray = 255-img_gray[ty1:ty2,tx1:tx2]
                    resized = imutils.resize(cnt_gray, width = 300)
                    troops_txt = self.ocr.read(resized,config='--oem 1 --psm 13')
                    cv2.imshow('sffssf',resized)
                    cv2.waitKey()
                    print( f't count: {troops_txt}')
                except Exception as e:
                    print( f'exception while count troops:{e}')
            

    def detectCoordinates(self, img_src:np.ndarray=None, img_gray:np.ndarray = None):
        if img_src is None:
            img_src = self.img_src.copy()
        if img_gray is None:
            img_gray = cv2.cvtColor(img_src,cv2.COLOR_BGR2GRAY)
        imgHeight, imgWidth = img_gray.shape[:2]

        img_topLeft = img_src[0:int(imgHeight*0.1),0:int(imgWidth*0.5)]
        img_topLeft_gray = img_gray[0:int(imgHeight*0.1),0:int(imgWidth*0.5)]

        rectExist,bbox, detected  = self.selectBigRectContour(img_topLeft_gray,150, minRate=0.1, maxRate=0.6)
       
        if rectExist:
            try:
                x,y,x2,y2 = bbox
                w = x2-x
                h = y2-y
                coords_part = img_topLeft[y+int(0.1*h):y+int(0.8*h),x+w:x+int(2.1*w)]

                #coords_yuv = cv2.cvtColor(coords_part, cv2.COLOR_BGR2YUV)
                #oords_yuv[:, :, 0] = cv2.equalizeHist(coords_yuv[:, :, 0])
                #coords_rgb = cv2.cvtColor(coords_yuv, cv2.COLOR_YUV2RGB)
    
                coords_txt = self.ocr.read(coords_part,config='-l eng --oem 1 --psm 13')
                coords_txt = coords_txt.replace('\n',' ')
                
                txt = re.sub('\D',' ', coords_txt)
                
                split = re.split('\s+', txt)
                split = [e for e in split if e != '']
                if( len(split) != 3 ):
                    coords_part_gray = img_topLeft_gray[y+int(0.1*h):y+int(0.8*h),x+w:x+int(2.1*w)]
                    coords_gray = 255-coords_part_gray
                    ret,coord_removed_bg = self.ocr.removeBackground(coords_gray, kernel1=1, kernel2=5)

                    coords_txt = self.ocr.read(coord_removed_bg,config='-l eng --oem 1 --psm 13')
                    coords_txt = coords_txt.replace('\n',' ')
                    txt = re.sub('\D',' ', coords_txt)
                    
                    split = re.split('\s+', txt)
                    split = [e for e in split if e != '']

                self.reportState.emit( f'location(ocr): {coords_txt}', True )
                if( len(split) == 3):
                    digits = tuple()
                    for i in range(0,3):
                        digits += ( int(split[i]), )
                    self.changeLocation.emit(digits)
                    self.reportState.emit( f'location: #{digits[0]} x{digits[1]} y{digits[2]}', True )
                return
            except Exception as e:
                self.reportState.emit(f'ocr error:{e}', True)
            self.reportState.emit('no coordinates info', True)

    def captureScreen( self ):
        waitCondition = QWaitCondition()
        mutex = QMutex()

        self.initStateFlags()
        self.reportState.emit('', False)
        self.clearRects.emit(waitCondition)
        try:
            mutex.lock()
            waitCondition.wait(mutex)
            mutex.unlock()
            print('overaly clear')
            # delete overlay componenets, move mouse to right lower part
            img_pil = ImageGrab.grab(bbox=self.bbox)
            img_src = np.array(img_pil)
            img_gray = cv2.cvtColor(img_src, cv2.COLOR_BGR2GRAY)
            self.img_src = img_src.copy()
            #print(self.img_src.shape)
            return (img_src, img_gray)
        except Exception as e:
            print( f'exception while capture: {e}')
        return None

    def identifyDialog(self, bbox, img_src:np.ndarray=None, img_gray:np.ndarray=None):
        if img_src is None:
            img_src = self.img_src.copy()
        if img_gray is None:
            img_gray = cv2.cvtColor(img_src,cv2.COLOR_BGR2GRAY)
        x, y, x2, y2 = bbox
        w = x2 - x
        h = y2 - y

        def ocrDialog( x, y, w, h, img_src):
            dialog_head = img_src[y:y+int(h*RATIO_HEAD_IN_DIALOG),x:x+w]
            head_gray, part_thresh = self.ocr.preprocessing( dialog_head )

            ocr_txt = str(self.ocr.read(part_thresh,config='-l kor --oem 1 --psm 7'))
            orc_txt_no_lines = os.linesep.join([s for s in ocr_txt.splitlines() if s])
            ocr_txt_no_blank = orc_txt_no_lines.replace(' ','')
            print('ocr_in_block(thresh):' + ocr_txt_no_blank)

            if( ocr_txt_no_blank == ''):
                ocr_txt = str(self.ocr.read(head_gray,config='-l kor --oem 1 --psm 7'))
                orc_txt_no_lines = os.linesep.join([s for s in ocr_txt.splitlines() if s])
                ocr_txt_no_blank = orc_txt_no_lines.replace(' ','')
                print('ocr_in_block(gray):' + ocr_txt_no_blank)
        
            head_line = ocr_txt_no_blank.replace('\n','')
            self.reportState.emit(f'headline(ocr): {head_line}', True)
            return head_line

        def headlineMatch( x,y,w,h,img_gray):
            dialog_head = img_gray[y:y+int(h*RATIO_HEAD_IN_DIALOG),x:x+w]
            match_result = self.multiScaleMatch(self.template_head_robot1, dialog_head, min=0.01, max=4.0, counts = 40, matchVal=0.6 )
            if match_result is not None:
                state = self.DIALOG_ROBOT1
            else:
                match_result = self.multiScaleMatch(self.template_head_robot2, dialog_head, min=0.01, max=4.0, counts = 40, matchVal=0.6 )
                if match_result is not None:
                    state = self.DIALOG_ROBOT2
            if match_result is not None:
                matchVal,top_left,bottom_right,r = match_result
                rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
                rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
                localHeadlineBox = rTopLeft + rBottomRight
                x1,y1,x2,y2 = localHeadlineBox
                globalHeadlineBox = (x+x1, y+y1, x+x2, y+y2)
                self.addRect.emit( globalHeadlineBox,255,0,255,255, 2  )
                return (state, globalHeadlineBox)
            return None

        def rubyTemplateMatch( x, y, w, h, img_gray ):
            img_dialog_left = img_gray[y:y+h,x:x+w//2]
            img_dialog_th = cv2.threshold(img_dialog_left, TH_RUBY_IN_DIALOG, 255, cv2.THRESH_BINARY)[1]
            
            self.changeTemplate.emit(self.template_ruby_in_dialog)
            match_result = self.multiScaleMatch(self.template_ruby_in_dialog, img_dialog_th)
            if match_result is not None:
                matchVal,top_left,bottom_right,r = match_result
                rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
                rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
                rubyImgBox = rTopLeft + rBottomRight
                x1,y1,x2,y2 = rubyImgBox
                self.addRect.emit( (x+x1, y+y1, x+x2, y+y2),255,255,0,255, 2  )
                return True
            return False

        def findButtons( x, y, w, h, img_gray):
            px = x
            py = y + int(h*RATIO_LOWER_DIALOG)
            dialog_lower = img_gray[py:y+h,px:x+w]
            fitContours = list()
            try:
                contours, img_thresh, ratio = selectContours( dialog_lower, TH_BUTTON2 )
            
                if len( contours ) > 0:
                    img_rgb = cv2.cvtColor(img_thresh,cv2.COLOR_GRAY2RGB)
                    for i in  range( 0, len( contours )):
                        contour = contours[i]
                        cw,ch = cv2.boundingRect(contour)[2:]
                        if cw * 1.5 < w and cw * 5 > w and ch * 20 > h and ch * 3 < h:
                            shape = self.shapeDetector.detect(contour)
                            print( f'button shape:{shape}')
                            if shape == 1:
                                cv2.drawContours(img_rgb, [contour],0,(255,0,0),3)
                            if shape == 2:
                                cv2.drawContours(img_rgb, [contour],0,(0,255,0),3)
                            if shape == 9:
                                cv2.drawContours(img_rgb, [contour],0,(0,0,255),3)
                            if shape in [ShapeDetector.SHAPE_RECTANGLE, ShapeDetector.SHAPE_SQUARE, ShapeDetector.SHAPE_CIRCLE]:
                                fitContours += (contour,)
            except Exception as e:
                ratio = 1.0
                print(f'exception while find buttons:{e}')
                            
                #cv2.imshow('aaa', img_rgb)
                #cv2.waitKey()
            return (fitContours, px, py, ratio)
                    

        with ThreadPoolExecutor() as executor:
            ocrFuture = executor.submit( ocrDialog, x, y, w, h, img_src)
            rubyFuture = executor.submit( rubyTemplateMatch, x,y, w, h, img_gray)
            buttonFuture = executor.submit( findButtons, x,y, w, h, img_gray)
            headlineFuture = executor.submit(headlineMatch, x,y,w,h, img_gray)

            head_line = ocrFuture.result()
            rubyResult = rubyFuture.result()
            buttonResult = buttonFuture.result()
            headlineFuture = headlineFuture.result()

            fitButtons, buttonPx, buttonPy, btnRatio = buttonResult
            btnCount = len(fitButtons)

            buttonBoxes = list()
            if btnCount > 0 and btnCount < 3:
                for i in range( 0, btnCount ):
                    fitButton = fitButtons[i]
                    a, b, c, d = cv2.boundingRect(fitButton)
                    brect = [a, b, c, d]
                    for j in range(0, len(brect)):
                         brect[j] = int( brect[j] * btnRatio )
                    bx, by, bw, bh = brect
                    btnBox = ( buttonPx + bx, buttonPy + by, buttonPx + bx + bw,  buttonPy +by + bh)
                    self.addRect.emit( btnBox, 255,0,0,200, 5)
                    buttonBoxes += (btnBox,)
                self.reportState.emit(f'button(s): {btnCount}', True)
            else:
                self.reportState.emit(f'button(s): none', True)
            
            headlineState = self.DIALOG_UNKNOWN if headlineFuture is None else headlineFuture[0]
            if rubyResult:
                self.reportState.emit( 'dialog: ruby', True)
            elif '사용' in head_line or '순서' in head_line or headlineState == self.DIALOG_ROBOT2:
                headlineBox = (x,y,x,y) if headlineFuture is None else headlineFuture[1]
                self.changeState.emit(self.DIALOG_ROBOT2)
                self.reportState.emit('dialog: check robot2', True)
                if len(buttonBoxes) == 1:
                    self.analyzeRobot2Dialog( img_gray, bbox, buttonBoxes[0], headlineBox)
            elif '보상' in head_line or headlineState == self.DIALOG_ROBOT1:
                self.changeState.emit(self.DIALOG_ROBOT1)
                self.reportState.emit('dialog: check robot1', True)

                
            else:
                self.changeState.emit(self.DIALOG_UNKNOWN)
                self.reportState.emit('dialog: unknown', True)

    def detectDialog(self, img_gray:np.ndarray = None):
        if img_gray is None:
            img_gray = cv2.cvtColor(self.img_src,cv2.COLOR_BGR2GRAY)

        for th in [TH_RECT_DIALOG2, TH_RECT_DIALOG3]:
            contourExist, bbox, detected = self.selectBigRectContour(img_gray, th, minRate=0.05, maxRate=0.6, max = True)
            if contourExist:
                break
        if contourExist:
            self.changeScreen.emit( detected )
            return bbox
        else:
            self.state_dialog = self.NO_DIALOG
            self.changeScreen.emit( img_gray )
            self.changeState.emit(self.NO_DIALOG)
            self.reportState.emit('dialog: none', True)
        return None

    def selectBigRectContour( self, img_gray: np.ndarray, tVal, minRate=0.7, maxRate = 1.0, max = False ):
        contours, img_thresh, ratio = selectContours( img_gray, tVal )
        contoursCount = len(contours)
        if contoursCount > 0:
            ih,iw = img_thresh.shape[:2]
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
                    #print( f'bigContourFinder: stopped in {str(i)}try(s)')
                    break
            if fitContour is not None:
                a, b, c, d = cv2.boundingRect(fitContour)
                brect = [a, b, c, d]
                for i in range(0, len(brect)):
                    brect[i] = int( brect[i] * ratio )
                x, y, w, h = brect

                gray2Rgb = cv2.cvtColor(img_thresh,cv2.COLOR_GRAY2RGB)
                cv2.drawContours(gray2Rgb,[fitContour],0,(0,255,0),3)
                detected = imutils.resize(gray2Rgb, width = img_gray.shape[1])
                
                return (True, (x,y,x+w,y+h), detected)
        return (False,None,None)
            
    def detectNightAndDay( self, img_gray:np.ndarray = None ):
        if img_gray is None:
            img_gray = cv2.cvtColor(self.img_src,cv2.COLOR_BGR2GRAY)
        img_thresh = cv2.threshold(img_gray, TH_NIGHT_AND_DAY, 255, cv2.THRESH_BINARY)[1]

        try:
            number_of_white = np.sum(img_thresh == 255)
            number_of_black = np.sum(img_thresh == 0)

            wbRatio = round(number_of_white/number_of_black, 2)
        
            daytime = bool(TH_CONTRAST_RATIO_WB_ND < wbRatio)
        
            if daytime is True:
                self.state_when = self.WHEN_DAY
                self.reportState.emit(f'contrast ratio: {str(wbRatio)}\nwhen: daytime', True)
            else:
                 self.state_when = self.WHEN_NIGHT
                 self.reportState.emit(f'contrast ratio: {str(wbRatio)}\nwhen: night', True)
            return True
        except Exception as e:
            print( f'Exception: {e}')
            self.state_when = self.WHEN_NONE
        return False
            
    def detectScreen(self, args=None):
        if args is None or len(args)==0:
            print( 'no args')
            return
        rect = args[0]
        if rect is None or not isinstance(rect, tuple) or len(rect) != 4 or not all(isinstance(n,int) for n in rect):
            print( f'no rect: {str(rect)}')
            return

        self.bbox = (rect[0],rect[1],rect[0]+rect[2],rect[1]+rect[3])
        captured = self.captureScreen()
        if captured is None:
            return
        img_src, img_gray = captured
        contourExist, bbox, detected = self.selectBigRectContour(img_gray, TH_RECT_APP, minRate=0.6)
        
        if contourExist is True:
            x1, y1 = rect[:2]
            x3, y3, x4, y4 = bbox
            self.changeBbox.emit( bbox )
            self.bbox = (x1 + x3, y1 + y3, x1 + x4, y1 + y4)
            self.img_src = img_src[ y3:y4, x3:x4 ]
            self.changeScreen.emit( detected )
        else:
            self.changeScreen.emit( img_gray )
            self.changeBbox.emit( (0,0,rect[2],rect[3]) )

    def findRuby(self, img_gray:np.ndarray = None):
        if img_gray is None:
            img_gray = cv2.cvtColor(self.img_src,cv2.COLOR_BGR2GRAY)
        
        img_th = None
        match_result = None

        def rubyMatch( img:np.ndarray, template:np.ndarray, th:int ):
            print(f'ruby match th({th})')
            self.changeTemplate.emit( template )
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
            print('findRuby : attribute error')
            
        if match_result is not None and img_th is not None:
            matched = cv2.cvtColor(img_th, cv2.COLOR_GRAY2RGB)
            matchVal,top_left,bottom_right,r = match_result
            
            rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
            rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))

            cv2.rectangle(matched, rTopLeft,rBottomRight, (0,0,255),5)
            self.changeScreen.emit(matched)
            rubyBox = rTopLeft + rBottomRight
            self.reportState.emit( f'ruby match value: {matchVal}', True )
            self.addRect.emit( rubyBox, 255,0,0,255, 5 )
            return rubyBox
        
        self.changeScreen.emit( img_gray )
        
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

    def analyzeRobot2Dialog( self, img_gray:np.ndarray, dialogBox:tuple, buttonBox:tuple, headlineBox:tuple):
      try:  
        print( f'dialog:{dialogBox}, button:{buttonBox}, headline:{headlineBox}')
        dx1, dy1, dx2, dy2 = dialogBox
        dw = dx2 - dx1
        dh = dy2 - dy1
        
        bx1, by1, bx2,by2 = buttonBox
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
                self.addRect.emit(tm_box,0,0,255,255, 1)
                self.crack_tm_box_list += (tm_box,)
        
        if len( self.crack_tm_box_list) > 0:
            self.crack_image_box = ( dx1, dy1+int(RATIO_HEAD_IN_DIALOG*dh), dx2, by1 - 5)
            self.addRect.emit( self.crack_image_box, 255,255,0,255, 2)
            self.crack_button_box = buttonBox
            
            print( f'crack tm count: {len(self.crack_tm_box_list)}')
        
      except Exception as e:
          print(e)


    def crackRobotCheck( self, img_src:np.ndarray = None, img_gray:np.ndarray = None, adjustMode = False ):

        if self.crack_image_box is None or self.crack_button_box is None or len(self.crack_tm_box_list)<1:
            print( 'crack data unsatisfied')
            return

        if img_src is None:
            img_src = self.img_src.copy()
        if img_gray is None:
            img_gray = cv2.cvtColor(img_src,cv2.COLOR_BGR2GRAY)

        cx1, cy1, cx2, cy2 = self.crack_image_box
        img_to_crack = img_src[cy1:cy2, cx1:cx2]
        self.c_src = img_to_crack
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
        self.changeScreen.emit( content_canny )
        content_canny_rgb = cv2.cvtColor(content_canny, cv2.COLOR_GRAY2RGB)

        def matchCrackTemplate( number:int, img_template:np.ndarray, content_canny:np.ndarray):
            template_canny = cv2.Canny(cv2.GaussianBlur(img_template,(1,1),0) , 2, 0)
            #self.changeTemplate.emit( template_canny )
            print( f'template matching #{number} launched')
            match_result = None
            for thVal in [0.5,0.4,0.3]:
                for angle in np.linspace(360, 0, 180)[::-1]:
                    self.changeTmRotate.emit( int( angle ))
                    rotated = rotateImage( template_canny, angle)
                    self.changeTmRotate.emit( rotated )
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
                        self.addRect.emit( globalMatchBox, 255,0,0,255, 2 )
                        self.changeScreen.emit( content_canny_rgb )
                        print(f'#{number} end')
                        return (number, globalMatchBox)
            return (number, None)

        tmBoxCount = len(self.crack_tm_box_list)
        
        with ThreadPoolExecutor(max_workers=tmBoxCount) as executor:
            futuresGroup = {executor.submit( matchCrackTemplate, int(i+1), img_src[
                self.crack_tm_box_list[i][1]:self.crack_tm_box_list[i][3], 
                self.crack_tm_box_list[i][0]:self.crack_tm_box_list[i][2]], content_canny ):
            i for i in range(0,tmBoxCount)}

            matchBoxes = dict()
            for future in futures.as_completed(futuresGroup):
                num, box = future.result()
                #print(f'#{num} result returned')
                matchBoxes[num] = box
            
            for n in range( 1, len(matchBoxes) + 1):
                box = matchBoxes[n]
                if box is not None:
                    mx1, my1, mx2, my2 = box
                    pyautogui.moveTo( self.bbox[0] + (mx1+mx2)//2, self.bbox[1]+ (my1+my2)//2, 0.5 )
                    pyautogui.click()
            print('all templates clicked')

            bx1, by1, bx2, by2 = self.crack_button_box
            pyautogui.moveTo( self.bbox[0] + (bx1+bx2)//2, self.bbox[1]+ (by1+by2)//2, 1 )
            pyautogui.click()



            

            

                                    
    def multiScaleMatch( self, template, img, min=0.01, max=4.0, counts=40, matchVal=0.65 ):
        th, tw = template.shape[:2]
        
        i = 0
        for scale in np.linspace(min, max, counts)[::-1]:
            resized = imutils.resize(img, width = int(img.shape[1] * scale))
            r = img.shape[1] / float(resized.shape[1])
            ratioProgress = int ( 100 / (max-min) * ( 1 / r - min ) )
            self.changeTmRatio.emit( ratioProgress )
            if resized.shape[0] < th or resized.shape[1] < tw:
                break
            match_result = match(template,resized,self.method, matchVal)
            if match_result is not None:
                #print('template found in ' + str(i+1) + 'try(s) ratio: ' +  str(1/r) )
                return match_result + (r,)
            i+=1
            
        return None
            




