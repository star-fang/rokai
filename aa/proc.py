from logging.handlers import QueueHandler
from pynput.keyboard import Listener as KL, Key
from multiprocessing import Process, Pipe, connection, Queue
from PyQt5.QtCore import QRunnable, QThreadPool, QThread
from time import sleep
from random import choice
import logging
from multiproc_logging import logger_init
from threading import Thread


class MainEmitThread(QThread):
    def __init__(self, conn:connection.Connection, name:str):
        QThread.__init__(self)
        self.__conn = conn
        self.__name = name

    def run(self):
        logging.info(f'thread in {self.__name} start')
        while True:
            try:
                recvd = self.__conn.recv()
            except EOFError:
                logging.info(f'thread{self.__name}: eof error')
                break
            except OSError:
                logging.info(f'thread{self.__name}: os error')
                break
            else:
                if recvd is None:
                    break
                logging.info(f'thread in {self.__name} recvd:{recvd}' )
                self.__conn.send(f'thanks for {recvd[1]}')
        self.__conn.send(None)
        self.__conn.close()
        logging.info(f'thread in {self.__name} end' )

class ProcRunner(QRunnable):
    
    def on_release(self, key):
        if key == Key.esc:
            self.proc.end_proc()
            return False

    def __init__(self, queue):
        QRunnable.__init__(self)
        conn1, conn2 = Pipe()
        self.keyListener = KL(on_release=self.on_release)
        self.meThread = MainEmitThread(conn1,'main')
        self.proc = Proc(conn2, queue)
        
    def run(self):
        self.meThread.start()
        self.proc.start()
        self.keyListener.start()

        self.proc.join()
        self.keyListener.stop()
        self.meThread.wait()
        logging.info('proc runner end')


class Proc(Process):
    random_args = ('COLORATURA', 'YELLOW', 'A HEAD FULL OF DREAMS', 'SCIENTIST')
    def funcA( self, *args ):
        for count in range(5):
            data = choice(args)
            capsule = (count,)
            capsule += (data,)
            self.__conn.send(capsule)
            sleep(1)
        logging.info( 'threadA fin' )
    
    def funcB( self ):
        while True:
            try:
                recvd = self.__conn.recv()
            except Exception as e:
                logging.info(f'funcB error:{e}')
                break
            else:
                if isinstance(recvd, str):
                    logging.info( f'proc recvd: {recvd}' )
                elif recvd is None:
                    break
        logging.info( 'threadB fin' )

    def __init__(self, conn:connection.Connection, queue:Queue):
        Process.__init__(self)
        self.__conn = conn
        self.__queue = queue
        
    
    def end_proc(self):
        logging.info( 'proc end abnormaly' )
        self.__conn.send(None)
        self.terminate()

    def run(self):
        q_handler = QueueHandler(self.__queue)
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(q_handler)

        logging.info( 'proc start' )
        thA = Thread( target=self.funcA, args=self.random_args )
        thB = Thread( target=self.funcB )
        thB.start()
        thA.start()
        thA.join()
        self.__conn.send(None)
        thB.join()
        logging.info( 'proc end normaly' )

if __name__ == '__main__':
    q_listener, queue = logger_init()
    pool = QThreadPool()
    pool.start( ProcRunner( queue ))
    pool.waitForDone()
    q_listener.stop()
    logging.info('end program')
    
