from logging import Formatter, LogRecord, StreamHandler, INFO, DEBUG, WARNING, getLogger
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from multiprocessing import Queue
from PyQt5.QtCore import QObject, pyqtBoundSignal
import os
import sys

def resource_path(relative):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath('.')

    return os.path.join(
        base_path,
        relative
    )

def make_q_handled_logger(queue:Queue, name:str = None):
    
    logger = getLogger()
    if not logger.hasHandlers():
        print( f'{name} logger has no handlers -> create new q-handler')
        qHandler = QueueHandler(queue)
        logger.addHandler(qHandler)
        
    logger.setLevel(DEBUG)
    return logger

def init_logger(signalObj:QObject=None, name:str = None):
    handlers = make_handlers(signalObj)
    q = Queue()
    ql = QueueListener(q, *handlers)

    logger = getLogger(name)
    logger.setLevel(DEBUG)
    for handler in handlers:
        logger.addHandler(handler)

    ql.start()
    return ql, q    

def make_handlers(signalObj:QObject):

    errorFileHandler = RotatingFileHandler(resource_path('error.log'), 'a', 300, 10)
    errorFileHandler.setLevel(WARNING)

    debugFileHandler = RotatingFileHandler(resource_path('debug.log'), 'a', 300, 10)
    debugFileHandler.setLevel(DEBUG)

    debugConsoleHandler = StreamHandler()
    debugConsoleHandler.setLevel(DEBUG)

    informationHandler = LogSignalHandler(signalObj)
    informationHandler.setLevel(INFO)

    debugFormat = Formatter('[%(asctime)s - %(levelname)s] %(module)s:%(lineno)d, pid:%(process)d -> %(message)s')
    infoFormat = Formatter('%(levelname)s: %(asctime)s - %(process)s - %(message)s')

    errorFileHandler.setFormatter(debugFormat)
    debugFileHandler.setFormatter(debugFormat)
    debugConsoleHandler.setFormatter(debugFormat)
    informationHandler.setFormatter(infoFormat)
    return errorFileHandler, debugFileHandler, debugConsoleHandler, informationHandler
    
class LogSignalHandler( StreamHandler ):
    def __init__(self, signalObj:QObject=None ):
        super().__init__()
        self._signal_obj = signalObj
    
    def emit(self, record:LogRecord):
        msg = self.format(record)
        if isinstance( self._signal_obj, QObject ) \
            and hasattr( self._signal_obj, 'logSign') \
                and isinstance( self._signal_obj.logSign, pyqtBoundSignal):
            #print(self._signal_obj.logSign)
            self._signal_obj.logSign.emit(msg)