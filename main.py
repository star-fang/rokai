import sys

import pyautogui
from PyQt5.QtWidgets import QApplication
from mainui import RokAMU

if __name__ == '__main__':
    print(sys.argv)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    systemResolution = pyautogui.size() #get screensize
    print(f"width={systemResolution[0]}\theight={systemResolution[1]}")
    
    rokAiMainUi = RokAMU(systemResolution)
    

    sys.exit(app.exec_())