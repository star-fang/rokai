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
    
    def removeBackground(self, img_gray, kernel1 = 3, kernel2 = 7): # ksize must must be odd
        mb1 = cv2.medianBlur(img_gray, kernel1)
        mb2 = cv2.medianBlur(img_gray,kernel2)
        d = np.ma.divide(mb1,mb2).data
        return np.uint8(255*d/d.max())

    def hsvMasking( self, src_bgr:np.ndarray, interval:int = 40 ):
        hsv = cv2.cvtColor(src_bgr, cv2.COLOR_BGR2HSV )
        def changeHsv():
            lower_th = np.array([0,0,0])
            uppper_th = np.array([0,0,255])
            mask = cv2.inRange(hsv, lower_th, uppper_th)
            dst = cv2.bitwise_and( src_bgr, src_bgr, mask = mask )
            cv2.imshow('hsv', mask)
            changeHsv.dst = dst
        
        changeHsv.dst = None
        changeHsv()
        #cv2.createTrackbar('h', 'ddd', 0, 180-interval, lambda k: changeHsv( k ))
        cv2.waitKey(0)
        return changeHsv.dst
        
    def preprocessing( self, src_gray:np.ndarray, height = 64, stackAxis=0, inv = True, adjMode:bool =False, **kwargs  ):
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

                coord_removed_bg = self.removeBackground(resized, kernel1=rk1, kernel2=rk2)
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
        except Exception as e:
            print( 'orc preprocess fail: %s' % e )
        return None, 0
        

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
    