from logging import Handler, FileHandler, Formatter, getLogger, INFO, DEBUG
from pathlib import Path
from PyQt5.QtCore import pyqtBoundSignal

class LogSignalHandler( Handler ):
    def __init__(self, signal:pyqtBoundSignal=None ):
        super().__init__()
        self.signal = signal
    
    def emit(self, record):
        msg = self.format(record)
        if self.signal is not None:
            self.signal.emit(msg)

def makeLogger(signal:pyqtBoundSignal=None, name=None ):
    logger = getLogger(name)
    logger.setLevel( DEBUG )
        
    logSignalHandler = LogSignalHandler( signal )
    
    source_path = Path(__file__).resolve()
    dst_dir = str(source_path.parent) + '/dst'
    fileLogHandler = FileHandler(filename= dst_dir + '/debug.log')

    logSignalHandler.setLevel( INFO )
    fileLogHandler.setLevel( DEBUG )

    logSignalHandler.setFormatter( Formatter('[%(asctime)s] %(name)s:%(levelname)s - %(message)s') )
    fileLogHandler.setFormatter( Formatter('[%(asctime)s] (%(module)s:%(lineno)d) %(name)s:%(levelname)s - %(message)s') )

    logger.addHandler(logSignalHandler)
    logger.addHandler(fileLogHandler)

    return logger