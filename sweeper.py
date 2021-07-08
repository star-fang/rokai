import cv2
from PIL import ImageGrab
import numpy as np
import imutils

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

    STATE_NORMAL = 0
    STATE_CHECK_ROBOT1 = 1
    STATE_CHECK_ROBOT2 = 2

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
            self.view.setScreenImage(image)
    
    def setTemplateImage( self, tImg):
        if self.view is not None:
            self.view.setTemplateImage(tImg)

    def setViewText( self, txt ):
        if self.view is not None:
            self.view.setText(txt)

    
    def detectState(self, bbox):
        screen_thresh = captureAndTresholding( bbox, 127 )[1]
        self.setViewImage(screen_thresh)
        contours = findContourList(screen_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cMax = max( contours, key=cv2.contourArea)
        x,y,w,h = cv2.boundingRect(cMax)
        ocr_txt = self.ocr.read(screen_thresh[y:y+h,x:x+w],config='-l kor --oem 1 --psm 3')
        ocr_txt_no_blank = str(ocr_txt).replace(' ','')
        print(ocr_txt_no_blank)

        if '사용' in ocr_txt_no_blank:
            self.setViewText('state: check robot1')
            return self.STATE_CHECK_ROBOT2
        elif '보상' in ocr_txt_no_blank:
            self.setViewText('state: check robot2')
            return self.STATE_CHECK_ROBOT1
        else:
            self.setViewText('state: normal')
            return self.STATE_NORMAL
        #self.setViewImage(screen_thresh[y:y+h,x:x+w])

    #detect rok screen and resize bbox
    def detectScreen(self, pw, ph, bbox):
        img_thresh = captureAndTresholding( (0,0,pw,ph), 60 )[1]
        
        contours = findContourList(img_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) > 0:
            #detected = cv2.cvtColor(img_thresh, cv2.COLOR_GRAY2RGB)
            # draw in blue the contours that were founded
            #cv2.drawContours(detected, contours, -1, 255, 2)

            # find the biggest countour (c) by the area
            c = max(contours, key = cv2.contourArea)
            x,y,w,h = cv2.boundingRect(c)
            
            # draw the biggest contour (c) in green
            
            if bool( w / pw < 0.7 ) or bool( h / ph < 0.7):
                bbox[0] = 0
                bbox[1] = 0
                bbox[2] = pw
                bbox[3] = ph
                self.setViewText('화면 감지 실패: 앱플레이어를 실행하고 화면 감지 버튼을 다시 눌러보세요')
                print('---screen detection failure')
            else:
                #cv2.rectangle(detected,(x,y),(x+w,y+h),(0,255,0), 4)
                bbox[0] = x
                bbox[1] = y
                bbox[2] = x + w
                bbox[3] = y + h
                self.setViewText('화면 감지 성공' )
                print('---screen detected ' + str(bbox))
                self.setViewImage( img_thresh[y:y+h,x:x+w])
                return True
        return False

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

    def crackRobotCheck( self, bbox ):
        #thresholding -> (multiscale <> ratate matching) -> click

        img_src,img_thresh = captureAndTresholding( bbox, 127 )

        contours = findContourList(img_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) > 0:
            if len(contours) > 1:
                contours.sort(key = cv2.contourArea, reverse=True)
                c = contours[0]
            else:
                c = contours[0]
            
            #c = max(contours, key = cv2.contourArea)
            x,y,w,h = cv2.boundingRect(c)

            #img_dialog_head = cv2.cvtColor(np.array(img_pil)[y+2:y+2+int(0.2*h),x:x+w],cv2.COLOR_BGR2GRAY)
            
            #img_src_head = img_src[y:y+int(0.12*h),x:x+w]
            img_dialog_head_thresh = img_thresh[y:y+int(0.12*h),x:x+w]
            img_dialog_head_blur = cv2.GaussianBlur(img_dialog_head_thresh,(3,3),0)  #advanced config # blur value
            img_dialog_head_canny = cv2.Canny(img_dialog_head_blur, 50, 100)  #advanced config # canny value

            #img_dialog = img_src[y:y+h,x:x+w]
            img_dialog_content= img_src[y+int(0.12*h):y+h,x:x+w]
            img_dialog_head = img_src[y:y+int(0.12*h),x:x+w]
            
            self.setViewImage(img_dialog_head_thresh)
            ocr_txt = self.ocr.read(img_dialog_head_thresh,config='-l kor --oem 1 --psm 3')
            #print(ocr_txt)
            if '사용' not in str(ocr_txt).replace(' ',''):
                self.setViewText('인증 화면 인식 실패')
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
                self.setViewImage(head_color)

                cI = 0
                self.c_src = img_dialog_content
                self.c_dst = self.c_src.copy()
                
                cv2.imshow('Canny',self.c_dst)
                
                self.th1 = 0
                self.th2 = 0
                self.gb = 1
                self.windowName = 'Canny'

                cv2.createTrackbar('th1', 'Canny', 0, 300, self.onChange_th1)
                cv2.createTrackbar('th2', 'Canny', 0, 300, self.onChange_th2)
                cv2.createTrackbar('gb', 'Canny', 0, 10, self.onChange_gb)
                cv2.waitKey()

                content_canny = self.c_dst
                self.setViewImage(content_canny)

                '''
                a = cv2.GaussianBlur(img_dialog_content,(9,9),0)  #advanced config # blur value
                b = cv2.Canny(a, 300, 300)  #advanced config # canny value
                cv2.imshow('canny', b)
                cv2.waitKey()
                self.setViewImage(b)
                '''

                self.c_src = img_dialog_head
                self.c_dst = self.c_src.copy()
                self.windowName = 'Template'
                #cv2.namedWindow('Template',cv2.WINDOW_NORMAL)
                #cv2.resizeWindow('Template', 300,300)
                cv2.imshow('Template',self.c_dst)
            
                self.th1 = 0
                self.th2 = 0
                self.gb = 1

                cv2.createTrackbar('th1', 'Template', 0, 300, self.onChange_th1)
                cv2.createTrackbar('th2', 'Template', 0, 300, self.onChange_th2)
                cv2.createTrackbar('gb', 'Template', 0, 10, self.onChange_gb)
                cv2.waitKey()

                templates_canny = self.c_dst
                
                
                detected = cv2.cvtColor(content_canny, cv2.COLOR_GRAY2RGB)

                for (rx,ry,rw,rh) in rects_no_duplicates:
                        cI += 1

                        template_canny = templates_canny[ry:ry+rh, rx:rx+rw]
                        self.setTemplateImage(template_canny)
                        print( '----- template matching #'+ str(cI)+' ----')

                        match_result = None
                        for matchVal in [0.5,0.4,0.3]:
                            print( ' -> threshold: ' + str(matchVal))
                            for angle in np.linspace(360, 0, 180)[::-1]:
                                #print( 'angle:' + str(angle))
                                rotated = rotateImage( template_canny, angle)
                                self.setTemplateImage(rotated)
                                self.setViewText(str(cI)+"번째 매칭 진행중 (angle:"+ str(angle)+")")
                                match_result = self.multiScaleMatch( rotated, content_canny,0.2, 0.6, 40, matchVal )

                                if match_result is not None:
                                    matchScore,matched,tl,br,r = match_result
                                    top_left = (int(tl[0]*r), int(tl[1]*r))
                                    bottom_right = (int(br[0]*r), int(br[1]*r))
                                    cv2.rectangle(detected, top_left,bottom_right, (0,0,255),5)
                                    cv2.putText(detected, str(cI), top_left, cv2.FONT_HERSHEY_SIMPLEX, 1,(255,255,255))
                                
                                    print( 'match score:' + str(matchScore) )
                                    self.setViewImage(detected)
                                    break
                            
                            if match_result is not None:
                                break
                            else:
                                print( ' ---')
                        
             
    def multiScaleMatch( self, template, img, min=0.1, max=2.5, counts=20, matchVal=0.7 ):
        th, tw = template.shape[:2]
        
        i = 0
        for scale in np.linspace(min, max, counts)[::-1]:
            resized = imutils.resize(img, width = int(img.shape[1] * scale))
            r = img.shape[1] / float(resized.shape[1])
            if resized.shape[0] < th or resized.shape[1] < tw:
                break
            match_result = match(template,resized,self.method, matchVal)
            if match_result is not None:
                print('template found in ' + str(i+1) + 'try(s) ratio: ' +  str(1/r) )
                return match_result + (r,)
            i+=1
            
        return None
            




