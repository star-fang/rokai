from logging import Formatter, Logger, StreamHandler, INFO, DEBUG, WARNING, getLogger
from logging.handlers import QueueHandler, RotatingFileHandler
from threading import Thread
from multiprocessing import Queue
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtBoundSignal, pyqtSignal

def make_q_handled_logger(queue:Queue, name:str):
    
    logger = getLogger(name)
    if not logger.hasHandlers():
        print( f'{name} logger has no handler -> create new q-handler')
        qHandler = QueueHandler(queue)
        logger.addHandler(qHandler)
    logger.setLevel(DEBUG)
    
    return logger

class MultiProcessLogging(QObject):
    logSignal = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)
        self.qDataGetter:Thread = None
    
    def startGetter(self, queue:Queue, name:str):
        self.qDataGetter = Thread(target=self._run_getter, args=(queue, name))
        self.qDataGetter.start()
    
    def stopGetter(self, queue:Queue):
        queue.put(None)
        self.qDataGetter.join()
        print( 'q-log getter finished' )
    
    def _run_getter(self, queue:Queue, name:str):
        logger:Logger = self.make_logger( name )
        while True:
            try:
                record = queue.get()
            except EOFError:
                print('queue closed abnormally')
                break
            else:
                if record is None:
                    break
                logger.handle(record)

    

    def make_logger(self, name:str):
        source_path = Path(__file__).resolve()
        dst_dir = str(source_path.parent) + '/dst'

        errorFileHandler = RotatingFileHandler(dst_dir + '/error.log', 'a', 300, 10)
        errorFileHandler.setLevel(WARNING)

        debugFileHandler = RotatingFileHandler(dst_dir + '/debug.log', 'a', 300, 10)
        debugFileHandler.setLevel(DEBUG)

        debugConsoleHandler = StreamHandler()
        debugConsoleHandler.setLevel(DEBUG)

        informationHandler = LogSignalHandler(self.logSignal)
        informationHandler.setLevel(INFO)

        debugFormat = Formatter('[%(asctime)s - %(levelname)s] %(module)s:%(lineno)d, pid:%(process)d -> %(message)s')
        infoFormat = Formatter('[%(asctime)s] %(message)s')

        errorFileHandler.setFormatter(debugFormat)
        debugFileHandler.setFormatter(debugFormat)
        debugConsoleHandler.setFormatter(debugFormat)
        informationHandler.setFormatter(infoFormat)

        logger = getLogger(name)
        logger.setLevel(DEBUG)
        logger.addHandler(errorFileHandler)
        logger.addHandler(debugFileHandler)
        logger.addHandler(debugConsoleHandler)
        logger.addHandler(informationHandler)
        return logger

class LogSignalHandler( StreamHandler ):
    def __init__(self, signal=None ):
        super().__init__()
        self.signal = signal
    
    def emit(self, record):
        msg = self.format(record)
        if isinstance( self.signal, pyqtBoundSignal ):
            self.signal.emit(msg)
        else:
            super().emit(record)