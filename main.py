import sys
from pyautogui import size
from PyQt5.QtWidgets import QApplication
from amu import RokAMU

if __name__ == '__main__':
    print(sys.argv)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    systemResolution = size() #get screensize
    print(f"width={systemResolution[0]}\theight={systemResolution[1]}")
    
    rokAiMainUi = RokAMU(systemResolution)
    

    sys.exit(app.exec_())