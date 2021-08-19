from logging import Formatter, LogRecord, StreamHandler, INFO, DEBUG, WARNING, getLogger
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from multiprocessing import Queue
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtBoundSignal, pyqtSignal

def make_q_handled_logger(queue:Queue, name:str):
    
    logger = getLogger()
    if not logger.hasHandlers():
        print( f'{name} logger has no handlers -> create new q-handler')
        qHandler = QueueHandler(queue)
        logger.addHandler(qHandler)
        
    logger.setLevel(DEBUG)
    return logger

class MultiProcessLogging():
    
    def init_logger(self, name:str, signalObj:QObject=None):
        handlers = self.make_handlers(signalObj)
        q = Queue()
        ql = QueueListener(q, *handlers)

        logger = getLogger()
        logger.setLevel(DEBUG)
        for handler in handlers:
            logger.addHandler(handler)

        ql.start()
        return ql, q

    def make_handlers(self, signalObj:QObject):
        source_path = Path(__file__).resolve()
        dst_dir = str(source_path.parent) + '/dst'

        errorFileHandler = RotatingFileHandler(dst_dir + '/error.log', 'a', 300, 10)
        errorFileHandler.setLevel(WARNING)

        debugFileHandler = RotatingFileHandler(dst_dir + '/debug.log', 'a', 300, 10)
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
            #print(f'emit:{msg}')