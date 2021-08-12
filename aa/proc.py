from multiprocessing import Process, Queue, Pipe, connection

class Proc(Process):
    def __init__(self, conn:connection.Connection, level:int = 1):
        Process.__init__(self)
        self.__conn = conn

    def run(self):
        signature = 1
        args1 = 'ccccc'
        args2 = 'ddddd'
        data = (signature,)
        #data += (args1,)
        #data += (args2,)
        print( f'send:{data}' )
        self.__conn.send(data)
        #print(f'object from main proc{self.__conn.recv()}')

def _emit(signature, *args):
        testFunc(*args)
        if args:
            pass
            #print(f'sign:{signature}, args:{args}')
            #testFunc(*args)
        else:
            pass
            #print(f'sign:{signature}')

def testFunc(*args):
    print(f'test: args{args}')

if __name__ == '__main__':
    conn1, conn2 = Pipe(True)
    proc = Proc(conn2)
    proc.start()
    #conn1.send({'c':'d'})
    recvd = conn1.recv()
    _emit(*recvd)

    
    #print(f'object from subproc{conn1.recv()}')
