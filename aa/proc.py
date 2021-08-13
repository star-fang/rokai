from pynput.keyboard import Listener as KL, Key
from multiprocessing import Process, Pipe, connection
from PyQt5.QtCore import QRunnable, QThreadPool, QThread,QObject, pyqtBoundSignal, pyqtSignal
from time import sleep
from random import choice
from threading import Thread

class MainSignals(QObject):
    signal = pyqtSignal(str)

class MainEmitThread(QThread):
    def __init__(self, signals:QObject, conn:connection.Connection, name:str):
        QThread.__init__(self)
        self._conn = conn
        self._name = name
        self._signals = signals

    def run(self):
        print( f'thread in {self._name} start')
        while True:
            try:
                recvd = self._conn.recv()
            except EOFError:
                print( f'thread{self._name}: eof error')
                break
            except OSError:
                print( f'thread{self._name}: os error')
                break
            else:
                if recvd is None:
                    break
                print( f'thread in {self._name} recvd:{recvd}' )
                if isinstance( self._signals.signal, pyqtBoundSignal ):
                    self._signals.signal.emit( f'thread in {self._name} recvd:{recvd}' )
                    self._conn.send(f'thanks for {recvd[1]}')
        self._conn.send(None)
        self._conn.close()
        print( f'thread in {self._name} end')

class ProcRunner(QRunnable):
    
    def on_release(self, key):
        if key == Key.esc:
            self.proc.end_proc()
            return False

    def __init__(self):
        QRunnable.__init__(self)
        conn1, conn2 = Pipe()
        self.keyListener = KL(on_release=self.on_release)
        signals = MainSignals()
        signals.signal.connect(lambda m: print(m))
        self.meThread = MainEmitThread(signals,conn1,'main')
        self.proc = Proc(conn2)
        
    def run(self):
        self.meThread.start()
        self.proc.start()
        self.keyListener.start()

        self.proc.join()
        self.keyListener.stop()
        self.meThread.wait()
        print('proc runner end')


class Proc(Process):
    random_args = ('COLORATURA', 'YELLOW', 'A HEAD FULL OF DREAMS', 'SCIENTIST')
    def funcA( self, *args ):
        print(f'args:{args}')
        for count in range(5):
            data = choice(args)
            capsule = (count,)
            capsule += (data,)
            self.__conn.send(capsule)
            sleep(1)
        print('threadA fin')
    
    def funcB( self ):
        while True:
            try:
                recvd = self.__conn.recv()
            except Exception as e:
                print(f'funcB error:{e}')
                break
            else:
                if isinstance(recvd, str):
                    print(f'proc recvd: {recvd}')
                elif recvd is None:
                    break
        print('threadB fin')

    def __init__(self, conn:connection.Connection):
        Process.__init__(self)
        self.__conn = conn
        
    
    def end_proc(self):
        self.__conn.send(None)
        print( 'proc end abnormaly')
        self.terminate()

    def run(self):
        print( 'proc start')

        thA = Thread( target=self.funcA, args=self.random_args )
        thB = Thread( target=self.funcB )
        thB.start()
        thA.start()
        thA.join()
        self.__conn.send(None)
        thB.join()
        print( 'proc end normaly')

if __name__ == '__main__':
    pool = QThreadPool()
    pool.start( ProcRunner())
    pool.waitForDone()
    print('end program')
    
    #print(f'object from subproc{conn1.recv()}')
