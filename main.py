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

    ocr = OcrEngine('-l eng+kor --oem 1 --psm3') #default config
    sweeper = Sweeper('cv2.TM_CCOEFF_NORMED', ocr) # default TM_option
    rokAiUi = RokAU(screenSize, ocr, sweeper)

    exit(app.exec_())