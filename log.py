from logging import FileHandler, Formatter, Handler, StreamHandler, INFO, DEBUG, ERROR, getLogger
from pathlib import Path
from PyQt5.QtCore import pyqtBoundSignal

class LogSignalHandler( Handler ):
    def __init__(self, signal:pyqtBoundSignal=None ):
        super().__init__()
        self.signal = signal
    
    def emit(self, record):
        super().emit( record )
        msg = self.format(record)
        if self.signal is not None:
            self.signal.emit(msg)

def makeLogger(signal:pyqtBoundSignal=None, name=None ):
    logger = getLogger(name)
    logger.setLevel( DEBUG )
        
    logSignalHandler = LogSignalHandler( signal )
    
    source_path = Path(__file__).resolve()
    dst_dir = str(source_path.parent) + '/dst'

    debugLogHandler = StreamHandler()
    errorLogHandler = FileHandler(filename= dst_dir + '/error.log')

    logSignalHandler.setLevel( INFO )
    debugLogHandler.setLevel( DEBUG )
    errorLogHandler.setLevel( ERROR )

    logSignalHandler.setFormatter( Formatter('[%(asctime)s] %(name)s:%(levelname)s - %(message)s') )
    debugLogHandler.setFormatter( Formatter('(%(module)s:%(lineno)d) %(name)s:%(levelname)s - %(message)s') )
    errorLogHandler.setFormatter( Formatter('[%(asctime)s] (%(module)s:%(lineno)d) %(name)s:%(levelname)s - %(message)s') )

    logger.addHandler(logSignalHandler)
    logger.addHandler( debugLogHandler )
    logger.addHandler(errorLogHandler)

    return logger