import os
import sys
from PyQt5.QtWidgets import QApplication
from amu import RokAMU
from multiprocessing import freeze_support

if __name__ == '__main__':
    freeze_support()
    try:
        os.chdir(sys._MEIPASS)
        print(sys._MEIPASS)
    except:
        os.chdir(os.getcwd()+'/rokRss')
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    rokAiMainUi = RokAMU()
    sys.exit(app.exec_())