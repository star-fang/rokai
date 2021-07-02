import pytesseract
import html5lib
from bs4 import BeautifulSoup

class OcrEngine:
    def __init__(self):
        self.a = 1

    def readHtml(self,im):
        config = '--oem 1 --psm 3'
        hocr = pytesseract.image_to_pdf_or_hocr(im, extension='hocr', config=config)
        soup = BeautifulSoup(hocr, 'html5lib')
        all_spans = soup.find_all('span')
        spans_with_classes = [s for s in soup('span') if s.get('class')]
        
        for ss in spans_with_classes:
               print(ss.getText())

    def read(self,im):
         config = '--oem 1 --psm 3'
         ocr = pytesseract.image_to_string(im, None)
         print(ocr)


