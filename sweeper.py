import threading
import cv2
from PIL import ImageGrab
import numpy as np
import imutils
import pyautogui
import time

def captureAndTresholding(bbox, threshold_value):
    
    img_pil = ImageGrab.grab(bbox=bbox)
    img_src = np.array(img_pil)
    img_tresholding = thresholding(img_src, threshold_value)
    return (img_src,img_tresholding)

#edge detection(Canny) vs thresholdng
def thresholding(image, tVal):
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


def match(template, resized, method):
        th, tw = template.shape[:2]
        match_result = cv2.matchTemplate(resized, template, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match_result)
        targetExist = False
        #in case of TM_SQDIFF, matching value is min value
        #in other case, the opposite is true

        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                top_left = min_loc
                match_val = min_val
                targetExist = bool(match_val < 0.2)
        else:
                top_left = max_loc
                match_val = max_val
                targetExist = bool(match_val > 0.7)
                
        #print(str(match_val) + str(targetExist))
            
        if( targetExist ):
                bottom_right = (top_left[0] + tw, top_left[1] + th)
                matched = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
                #cv2.putText(matched, str(match_val), top_left, cv2.FONT_HERSHEY_PLAIN, 
                #5, (0,255,0), 2, cv2.LINE_4)
                return (match_val, matched, top_left, bottom_right)
        else:
            return None

def rotateImage( image, angle ):
    center = tuple(np.array(image.shape[1::-1]) / 2)
    rotationMatrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, rotationMatrix, image.shape[1::-1], flags=cv2.INTER_LINEAR )
    return rotated

#A ruby finder in rok
class Sweeper:
    def __init__(self, methodName, ocr):
        templatePath = 'C:/Users/clavi/Downloads/ruby/template.png'
        self.template = thresholding(cv2.imread(templatePath), 90)
        if methodName is not None:
            self.setMethodName(methodName)
        self.view = None
        self.ocr = ocr
    
    def setMethodName(self, name):
        self.methodName = name
        self.method = eval(name)

    def setTemplate(self,template):
        self.template = template
    
    def setView( self, view ):
        self.view = view

    def setViewImage( self, image ):
        if self.view is not None:
            self.view.setImage(image)

    def setViewText( self, txt ):
        if self.view is not None:
            self.view.setText(txt)

    
            

    #detect rok screen and resize bbox
    def detectScreen(self, pw, ph, bbox):
        img_thresh = captureAndTresholding( (0,0,pw,ph), 100 )[1]
        
        contours = findContourList(img_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        if len(contours) > 0:
            detected = cv2.cvtColor(img_thresh, cv2.COLOR_GRAY2RGB)
            # draw in blue the contours that were founded
            cv2.drawContours(detected, contours, -1, 255, 2)

            # find the biggest countour (c) by the area
            c = max(contours, key = cv2.contourArea)
            x,y,w,h = cv2.boundingRect(c)
            
            # draw the biggest contour (c) in green
            cv2.rectangle(detected,(x,y),(x+w,y+h),(0,255,0), 4)
            self.setViewImage(detected)

            if bool( w / pw < 0.7 ) or bool( h / ph < 0.7):
                bbox[0] = 0
                bbox[1] = 0
                bbox[2] = pw
                bbox[3] = ph
                self.setViewText('화면 감지 실패: 앱플레이어를 실행하고 화면 감지 버튼을 다시 눌러보세요')
                print('---screen detection failure')
            else:
                bbox[0] = x
                bbox[1] = y
                bbox[2] = x + w
                bbox[3] = y + h
                self.setViewText('화면 감지 성공: 이제부터 초록색 사각형 안의 내용만 탐색합니다. (성능 향상 기대)' )
                print('---screen detected ' + str(bbox))

    #find ruby using Template Matching (cv2)
    #methods: 'cv2.TM_CCOEFF_NORMED', 'cv2.TM_CCORR_NORMED','cv2.TM_SQDIFF_NORMED'
    def findRuby(self, bbox):
        if self.template is not None:

            img = captureAndTresholding(bbox, 90)[1]
            self.setViewImage(img)

            match_result = self.multiScaleMatch( self.template, img )

            if match_result is not None:
                matchVal,matched,top_left,bottom_right,r = match_result
                cv2.rectangle(matched, top_left,bottom_right, (0,0,255),5)
                self.setViewImage(matched)
                self.setViewText('보석 발견 (매칭값: '+str(matchVal)+')')
                return (int(r*(top_left[0]+bottom_right[0])//2+bbox[0]),int(r*(top_left[1]+bottom_right[1])//2+bbox[1]))
            else:
                self.setViewText('보석 없심더...')

            return None

    def crackRobotCheck( self, bbox ):
        #thresholding -> (multiscale <> ratate matching) -> click
        img_src,img_thresh = captureAndTresholding( bbox, 127 )

        contours = findContourList(img_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) > 0:

            c = max(contours, key = cv2.contourArea)
            x,y,w,h = cv2.boundingRect(c)

            #img_dialog_head = cv2.cvtColor(np.array(img_pil)[y+2:y+2+int(0.2*h),x:x+w],cv2.COLOR_BGR2GRAY)
            img_dialog = img_thresh[y:y+h,x:x+w]
            #img_src_head = img_src[y:y+int(0.12*h),x:x+w]
            img_dialog_head= img_thresh[y:y+int(0.12*h),x:x+w]
            img_dialog_head_blur = cv2.GaussianBlur(img_dialog_head,(3,3),0)  #advanced config # blur value
            img_dialog_head_canny = cv2.Canny(img_dialog_head_blur, 50, 100)  #advanced config # canny value

            img_dialog_content= img_thresh[y+int(0.12*h):y+h,x:x+w]
            
            #self.setViewImage(img_dialog_head_canny)

            ocr_txt = self.ocr.read(img_dialog_head,config='-l kor --oem 1 --psm 3')
            #print(ocr_txt)
            if '사용' not in str(ocr_txt).replace(' ',''):
                self.setViewText('인증 화면 인식 실패')
                #return False

           
            contours_in_dialog = findContourList(img_dialog_head_canny, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            #print(contours_in_dialog)

            if (contours_in_dialog is not None) and (len(contours_in_dialog) > 0):
                #detected = cv2.cvtColor(img_dialog_head_canny, cv2.COLOR_GRAY2RGB)
                #cv2.drawContours(detected, contours_in_dialog, -1, 255, 2)
                
                headHeight, headWidth = img_dialog_head_canny.shape[:2]
                head_area = headHeight * headWidth
                
                template_rects = []
                for c in contours_in_dialog:
                    cx,cy,cw,ch = cv2.boundingRect(c)
                    area = cw * ch
                    
                    if (area * 65 > head_area) and (cw * 10 < headWidth) and (cx > headWidth // 2):
                        template_rects.append((cx,cy,cw,ch))

                rects_sorted = sorted( template_rects, key=lambda t: t[0], reverse=False)

                rects_duplicates = []
                for i in range(0,len(rects_sorted)):
                    if (i > 0) and abs(rects_sorted[i-1][0] - rects_sorted[i][0]) < rects_sorted[i-1][2]:
                        continue
                    rects_duplicates.append(rects_sorted[i])

                cI = 0
                detected = cv2.cvtColor(img_dialog_content, cv2.COLOR_GRAY2RGB)
                for (rx,ry,rw,rh) in rects_duplicates:
                    cI += 1
                    #cv2.rectangle(detected,(rx,ry),(rx+rw,ry+rh),(0,0,255), 1)
                    #cv2.putText(detected, str(cI), (rx,ry), cv2.FONT_HERSHEY_SIMPLEX, 1,(255,255,255))

                    template = img_dialog_head[ry:ry+rh, rx:rx+rw]
                    #self.setViewImage(template)

                    for angle in np.linspace(180, 0, 180)[::-1]:
                        #print( 'angle:' + str(angle))
                        rotated = rotateImage( template, angle)
                        match_result = self.multiScaleMatch( rotated, img_dialog_content,0.1, 1.0, 30 )
                        if match_result is None:
                            match_result = self.multiScaleMatch( 255-rotated, img_dialog_content,0.1, 1.0, 30 )
                        if match_result is not None:
                            matchVal,matched,tl,br,r = match_result
                            top_left = (int(tl[0]*r), int(tl[1]*r))
                            bottom_right = (int(br[0]*r), int(br[1]*r))
                            cv2.rectangle(detected, top_left,bottom_right, (0,0,255),5)
                            cv2.putText(detected, str(cI), top_left, cv2.FONT_HERSHEY_SIMPLEX, 1,(255,255,255))
                            
                            print( top_left + bottom_right )
                            break
                self.setViewImage(detected)
                    
               

            

    def multiScaleMatch( self, template, img, min=0.1, max=2.5, counts=20 ):
        th, tw = template.shape[:2]
        i = 0
        match_result = None
        for scale in np.linspace(min, max, counts)[::-1]:
            resized = imutils.resize(img, width = int(img.shape[1] * scale))
            r = img.shape[1] / float(resized.shape[1])
            if resized.shape[0] < th or resized.shape[1] < tw:
                break
            match_result = match(template,resized,self.method)
            if match_result is not None:
                print('template found in ' + str(i+1) + ' try (ratio:' + str(r) + ')')
                match_result += (r,) # concatenate tutples
                break
            i+=1
            
        return match_result
            




