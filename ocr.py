import pytesseract
import html5lib
from bs4 import BeautifulSoup

class OcrEngine:
    def __init__(self, config):
        self.config = config

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
        print(config)
            
        #config lang oem psm
        ocr = pytesseract.image_to_string(im, config=config)
        print(ocr)
        return ocr