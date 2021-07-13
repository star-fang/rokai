import sys

import pyautogui
from PyQt5.QtWidgets import QApplication
from ocr import OcrEngine
from mainui import RokAMU
from sweeper import Sweeper

if __name__ == '__main__':
    print(sys.argv)

    app = QApplication(sys.argv)
    print( str(app.quitOnLastWindowClosed()) )

    systemResolution = pyautogui.size() #get screensize
    print(f"width={systemResolution[0]}\theight={systemResolution[1]}")
    ocr = OcrEngine('-l eng+kor --oem 1 --psm3') #default config
    sweeper = Sweeper( ocr ) # default TM_option
    rokAiMainUi = RokAMU(systemResolution, sweeper)
    rokAiMainUi.show()
    

    sys.exit(app.exec_())