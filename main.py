import sys
from PyQt5.QtWidgets import QApplication
from amu import RokAMU

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    rokAiMainUi = RokAMU()
    sys.exit(app.exec_())