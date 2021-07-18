import pytesseract
import html5lib
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

    def preprocessing(self, img_src, showProcess=False, blockSize=11, C=2):
        img_gray = cv2.cvtColor(img_src,cv2.COLOR_BGR2GRAY)
        noiseRemoved = cv2.fastNlMeansDenoising(img_gray,None,10,7,15)
        img_th = cv2.adaptiveThreshold(noiseRemoved, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,blockSize=blockSize,C=C)
        if showProcess:
            cv2.imshow('pre-gray', img_gray)
            cv2.imshow('pre-nr', noiseRemoved)
            cv2.imshow('pre-th', img_th)
            cv2.waitKey()
        return noiseRemoved, img_th

    def removeBackground(self, img_gray, kernel1 = 3, kernel2 = 51, thresh= True): # ksize must must be odd
        mb1 = cv2.medianBlur(img_gray, kernel1)
        mb2 = cv2.medianBlur(img_gray,kernel2)
        d = np.ma.divide(mb1,mb2).data
        n = np.uint8(255*d/d.max())
        
        return cv2.threshold(n, 100, 255, cv2.THRESH_OTSU) if thresh else n

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