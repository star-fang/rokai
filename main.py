import sys

import pyautogui
from PyQt5.QtWidgets import QApplication
from ocr import OcrEngine
from mainui import RokAMU
from minimap import MiniMap

if __name__ == '__main__':
    print(sys.argv)

    
    systemResolution = pyautogui.size() #get screensize
    print(f"width={systemResolution[0]}\theight={systemResolution[1]}")

    app = QApplication(sys.argv)

    ocr = OcrEngine('-l eng+kor --oem 1 --psm3') #default config
    rokAiMainUi = RokAMU(systemResolution, ocr)
    rokAiMainUi.show()

    rokMiniMap = MiniMap(rokAiMainUi.centralWidget())
    rokMiniMap.show()

    exit(app.exec_())