import cv2
from PIL import ImageGrab
import numpy as np
import imutils

def captureAndTresholding(bbox):
        img_pil = ImageGrab.grab(bbox=bbox)
        img_gray = cv2.cvtColor(np.array(img_pil), cv2.COLOR_BGR2GRAY)
        img_tresholding = thresholding(img_gray)
        return (img_pil,img_gray,img_tresholding)

#edge detection(Canny) vs thresholdng
def thresholding(image):
        return cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)[1]

#A ruby finder in rok
class Sweeper:
    def __init__(self, methodName):
        templatePath = 'C:/Users/clavi/Downloads/ruby/template.png'
        self.template = thresholding(cv2.imread(templatePath, 0))
        if methodName is not None:
            self.setMethodName(methodName)
        self.view = None
    
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
        img_thresh = captureAndTresholding( (0,0,pw,ph) )[2]
        print( 'detecting screen using contours (cv2 version: ' + str(cv2.__version__) + ')')
        if (int(cv2.__version__[0]) > 3):
            contours, hierarchy = cv2.findContours(img_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        else:
            im2, contours, hierarchy = cv2.findContours(img_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if len(contours) != 0:
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
    def find(self, bbox):
        if self.template is not None:

            img = captureAndTresholding(bbox)[2]
            self.setViewImage(img)
            
            #view.setImage(Image.fromarray(np.ones((100, 100, 3), dtype=np.uint8)))
            th, tw = self.template.shape[:2]

            i = 0
            match_result = None
            for scale in np.linspace(0.1, 2.5, 20)[::-1]:
                resized = imutils.resize(img, width = int(img.shape[1] * scale))
                r = img.shape[1] / float(resized.shape[1])
                if resized.shape[0] < th or resized.shape[1] < tw:
                    break
                match_result = self.match(resized)
                if match_result is not None:
                    print('template found in ' + str(i+1) + ' try (ratio:' + str(r) + ')')
                    self.setViewImage(match_result[1])
                    self.setViewText('보석 발견 (매칭값: '+str(match_result[0])+')')
                    match_result = (int(r*match_result[2]+bbox[0]),int(r*match_result[3]+bbox[1]))
                    break
                i+=1
            
            if match_result is None:
                print('template not found')
                self.setViewText('보석 없심더...')
            
            return match_result
                

    def match(self, resized):
        th, tw = self.template.shape[:2]
        match_result = cv2.matchTemplate(resized, self.template, self.method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match_result)
        targetExist = False
        #in case of TM_SQDIFF, matching value is min value
        #in other case, the opposite is true

        if self.method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
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
                cv2.rectangle(matched, top_left,bottom_right, (0,0,255),5)
                #cv2.putText(matched, str(match_val), top_left, cv2.FONT_HERSHEY_PLAIN, 
                #5, (0,255,0), 2, cv2.LINE_4)
                return (match_val, matched, (top_left[0]+bottom_right[0])//2, (top_left[1]+bottom_right[1])//2)
        else:
            return None
            




