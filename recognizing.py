import logging
import imutils
import pytesseract
import numpy as np
import cv2
from bs4 import BeautifulSoup

'''
page segment mode (--psm) options
0    Orientation and script detection (OSD) only.
1    Automatic page segmentation with OSD.
2    Automatic page segmentation, but no OSD, or OCR.
3    Fully automatic page segmentation, but no OSD. (Default)
4    Assume a single column of text of variable sizes.
5    Assume a single uniform block of vertically aligned text.
6    Assume a single uniform block of text.
7    Treat the image as a single text line.
8    Treat the image as a single word.
9    Treat the image as a single word in a circle.
10    Treat the image as a single character.
11    Sparse text. Find as much text as possible in no particular order.
12    Sparse text with OSD.
13    Raw line. Treat the image as a single text line, bypassing hacks that

engine mode (--oem) options
0	Legacy engine only
1	Neural net LSTM only
2	Legacy + LSTM mode only
3	By Default, based on what is currently available
'''

def detectShape(contour, epsilon = 0.04):
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon * peri, True)

        len_approx = len(approx)
        w, h = cv2.boundingRect(approx)[2:]
        ar = w / float(h)

        return len_approx, ar

def template_match(template:np.ndarray, resized:np.ndarray, method:int, mThreshold:int):
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

def hsvMasking( src_hsv:np.ndarray, hsvLower:list=[0,0,0], hsvUpper:list=[180,255,255], adjMode = False ):
        def changeHsv(k,ki:int = -1, adj:bool = False):
            if ki == 0:
                changeHsv.hl = k
            elif ki == 1:
                changeHsv.hu = k
            elif ki == 2:
                changeHsv.sl = k
            elif ki == 3:
                changeHsv.su = k
            elif ki == 4:
                changeHsv.vl = k
            elif ki == 5:
                changeHsv.vu = k

            lower_th = np.array([changeHsv.hl,changeHsv.sl,changeHsv.vl])
            uppper_th = np.array([changeHsv.hu,changeHsv.su,changeHsv.vu])

            mask = cv2.inRange(src_hsv, lower_th, uppper_th)
            
            if adj:
                resized = imutils.resize(mask,height=200)
                cv2.imshow('hsv',  resized)
            changeHsv.dst = mask

        changeHsv.hl = hsvLower[0]
        changeHsv.sl = hsvLower[1]
        changeHsv.vl = hsvLower[2]
        changeHsv.hu = hsvUpper[0]
        changeHsv.su = hsvUpper[1]
        changeHsv.vu = hsvUpper[2]
        changeHsv.dst = None
        changeHsv(0, adj=adjMode)
        if adjMode:
            cv2.createTrackbar('h_l', 'hsv', changeHsv.hl, 180, lambda k: changeHsv( k, ki=0, adj=True ))
            cv2.createTrackbar('h_u', 'hsv', changeHsv.hu, 180, lambda k: changeHsv( k, ki=1, adj=True ))
            cv2.createTrackbar('s_l', 'hsv', changeHsv.sl, 255, lambda k: changeHsv( k, ki=2, adj=True ))
            cv2.createTrackbar('s_u', 'hsv', changeHsv.su, 255, lambda k: changeHsv( k, ki=3, adj=True ))
            cv2.createTrackbar('v_l', 'hsv', changeHsv.vl, 255, lambda k: changeHsv( k, ki=4, adj=True ))
            cv2.createTrackbar('v_u', 'hsv', changeHsv.vu, 255, lambda k: changeHsv( k, ki=5, adj=True))
        cv2.waitKey(0)
        return changeHsv.dst

def removeBackground(img_gray, kernel1 = 3, kernel2 = 7): # ksize must must be odd
        mb1 = cv2.medianBlur(img_gray, kernel1)
        mb2 = cv2.medianBlur(img_gray,kernel2)
        d = np.ma.divide(mb1,mb2).data
        return np.uint8(255*d/d.max())

def ocr_preprocessing( src_gray:np.ndarray, height = 64, stackAxis=0, inv = True, adjMode:bool=False, **kwargs  ):
        try:
            if inv:
                src_gray = cv2.bitwise_not(src_gray)
            resizeRatio:float = src_gray.shape[0] / float( height )
            resized = imutils.resize( src_gray, height=height )

            def onChange_ksize( k:int==0 , ki:int=-1, adj:bool=False ):
                if ki == 0:
                    onChange_ksize.bkf = k
                elif ki == 1:
                    onChange_ksize.rkf1 = k
                elif ki == 2:
                    onChange_ksize.rkf2 = k
                elif ki == 3:
                    onChange_ksize.ekf = k
                elif ki == 4:
                    onChange_ksize.it = k
                bk = 2 * onChange_ksize.bkf + 1
                rk1 = 2 * onChange_ksize.rkf1 + 1
                rk2 = 2 * onChange_ksize.rkf2 + 1 
                ek = 2 * onChange_ksize.ekf + 1

                coord_removed_bg = removeBackground(resized, kernel1=rk1, kernel2=rk2)
                blur = cv2.GaussianBlur( coord_removed_bg, (bk,bk), 0 )          
                coord_thresh_otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
                #coord_thresh_gauss = cv2.adaptiveThreshold(blur,255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                coord_thresh_mean = cv2.adaptiveThreshold(blur,255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
                otsuAndMean = cv2.bitwise_or(coord_thresh_otsu, coord_thresh_mean )         
                ed = cv2.dilate(otsuAndMean, np.ones(( ek , ek ), np.uint8), iterations = (onChange_ksize.it+1))

                column_pixel_sum = np.sum(ed, axis = 0 )
                proj = column_pixel_sum / 255

                hHist = np.full_like( ed, 255 )
                word_start = False
                for i, val in enumerate( proj ):
                    invVal = height - int(val)
                    score = invVal / float( height ) # 0 ~ 1
                    if score > 0.05:
                        cv2.line( hHist, (i, 0), (i, height), 0, 1)

                dst = cv2.bitwise_or( ed, hHist )
                onChange_ksize.dst = dst

                if adj:
                    cv2.imshow('coord', 
                    np.vstack([ resized, coord_removed_bg, otsuAndMean, ed, hHist, dst]) if stackAxis == 0
                    else  np.hstack([ resized, coord_removed_bg, otsuAndMean, ed, hHist, dst]))
                #end function onChange_ksize
            onChange_ksize.bkf = kwargs.get('bkf',6)
            onChange_ksize.rkf1 = kwargs.get('rkf1',0)
            onChange_ksize.rkf2 = kwargs.get('rkf2',20)
            onChange_ksize.ekf = kwargs.get('ekf',0)
            onChange_ksize.it = kwargs.get('it',0)
            onChange_ksize( 0, adj = adjMode )
            if adjMode:
                print('adj...')
                cv2.createTrackbar('bk', 'coord', onChange_ksize.bkf, 20, lambda k: onChange_ksize( k, 0, adj = True ))
                cv2.createTrackbar('rk1', 'coord', onChange_ksize.rkf1, 10, lambda k: onChange_ksize( k, 1, adj = True))
                cv2.createTrackbar('rk2', 'coord', onChange_ksize.rkf2, 25, lambda k: onChange_ksize( k, 2, adj = True))
                cv2.createTrackbar('ek', 'coord', onChange_ksize.ekf, 20, lambda k: onChange_ksize( k, 3, adj = True))
                cv2.createTrackbar('iter', 'coord', onChange_ksize.it, 10, lambda k: onChange_ksize( k, 4, adj = True))
                cv2.waitKey(0)
            
            if hasattr(onChange_ksize, 'dst'):
                return onChange_ksize.dst, resizeRatio
        except Exception:
            logging.exception('ocr preprocssing')
            #print( 'orc preprocess fail: %s' % e )
        return None, 0

class OcrEngine:
    def __init__(self, config):
        self.config = config
    
    '''def preprocessing(self, img_src, showProcess=False, blockSize=11, C=2):
        img_gray = cv2.cvtColor(img_src,cv2.COLOR_BGR2GRAY)
        noiseRemoved = cv2.fastNlMeansDenoising(img_gray,None,10,7,15)
        img_th = cv2.adaptiveThreshold(noiseRemoved, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,blockSize=blockSize,C=C)
        if showProcess:
            cv2.imshow('pre-gray', img_gray)
            cv2.imshow('pre-nr', noiseRemoved)
            cv2.imshow('pre-th', img_th)
            cv2.waitKey()
        return noiseRemoved, img_th'''

    def readHtml(self,im):
        config = '--oem 1 --psm 3'
        hocr = pytesseract.image_to_pdf_or_hocr(im, extension='hocr', config=config)
        soup = BeautifulSoup(hocr, 'html5lib')
        all_spans = soup.find_all('span')
        spans_with_classes = [s for s in soup('span') if s.get('class')]
        
        for ss in spans_with_classes:
               print(ss.getText())

    def read(self,im,**kwargs):
        for key, val in kwargs.items():
            if key=='config':
                config=val
                break
        #print(config)
            
        #config lang oem psm
        ocr = pytesseract.image_to_string(im, config=config)
        return ocr
    