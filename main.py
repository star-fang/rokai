import sys

import pyautogui
from PyQt5.QtWidgets import QApplication
from ocr import OcrEngine
from ui import RokAU
from sweeper import Sweeper

if __name__ == '__main__':
    print(sys.argv)

    
    screenSize = pyautogui.size() #get screensize
    print(f"width={screenSize[0]}\theight={screenSize[1]}")

    app = QApplication(sys.argv)

    sweeper = Sweeper('cv2.TM_CCOEFF_NORMED')
    ocr = OcrEngine()
    rokAiUi = RokAU(screenSize, ocr, sweeper)

    exit(app.exec_())
