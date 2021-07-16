import threading
import pyautogui
import time
from threading import Thread
from numpy.random import Generator, MT19937, SeedSequence

easeOptions = ['easeInQuad','easeOutQuad','easeInOutQuad','easeInCubic', 'easeOutCubic',
'easeInOutCubic','easeInQuart','easeOutQuart','easeInOutQuart','easeInQuint',
'easeOutQuint','easeInOutQuint','easeInSine','easeOutSine','easeInOutSine',
'easeInExpo','easeOutExpo','easeInOutExpo','easeInCirc','easeOutCirc',
'easeInOutCirc','easeInElastic','easeOutElastic','easeInOutElastic','easeInBack',
'easeOutBack','easeInOutBack','easeInBounce','easeOutBounce','easeInOutBounce']

class Tracker(Thread):
    def __init__(self, seed, sweeper, bbox):
        Thread.__init__(self)
        self.times = 0
        self.__flag = threading.Event()
        self.__flag.set()
        self.__running = threading.Event()
        self.__running.clear()
        self.setDaemon( True )
        self.changeSeed(seed)
        self.sweeper = sweeper
        self.bbox = bbox #(x1, y1, x2, y2) detected screen size

        self.cx = (bbox[2] + bbox[0])//2
        self.cy = (bbox[3] + bbox[1])//2

        self.halfWidth = (self.bbox[2] - self.bbox[0])/2
        self.halfHeight = (self.bbox[3] - self.bbox[1])/2
    
    def calcRandomX( self ):
        random = self.generateRandomNumber(1.4) - 0.7 # -0.7~0.7
        return int(self.cx + self.halfWidth * random)

    def calcRandomY( self ):
        random = self.generateRandomNumber(1.2) - 0.6 # -0.6~0.6
        return int(self.cy + self.halfHeight * random)

    def randomMovingOption( self ):
        randomIndex = int(self.generateRandomNumber(30))
        if (randomIndex >= 0) and (randomIndex < 30): 
            optionName = 'pyautogui.'+easeOptions[randomIndex]
            print(str(randomIndex) + ', ' + optionName)
            return eval(optionName)
        
        return None

    def move( self ):
        pyautogui.moveTo(self.calcRandomX(), self.calcRandomY(), self.generateRandomNumber(1.5))
        pyautogui.dragTo(self.calcRandomX(), self.calcRandomY(), self.generateRandomNumber(2), self.randomMovingOption())
        time.sleep(0.5)
        r = self.sweeper.findRuby(self.bbox)
        if r is not None:
            print(r)
            pyautogui.moveTo( r[0], r[1], self.generateRandomNumber(1.5))
            time.sleep(0.1)
            pyautogui.click()
            return True
        return False
    
    def changeSeed( self, seed ):
        sg = SeedSequence(seed)
        self.bitGenerator = MT19937(sg)

    def generateRandomNumber(self, n): # generate 0 ~ n ( hundredths 0.00 )
        return Generator(self.bitGenerator).random() * float(n)
    
    def generateRandomInt(self):
        randomInt = self.int_32(self.bitGenerator.random_raw())
        self.bitGenerator = self.bitGenerator.jumped()
        return randomInt
    
    def int_32(self, number):
        return int(0xFFFFFFFF & number)
    
    def run(self):
        self.__running.set()
        print('start thread')
        while self.__running.is_set():
            try:
                self.__flag.wait()
                self.times += 1
                if self.move():
                    raise KeyboardInterrupt
                
                #random = self.generateRandomNumber(2)
                #print( str(self.times) + ", " + str(random) )
                
                time.sleep(1.5)
            except KeyboardInterrupt:
                print('keyboard interruption occured')
                self.pause()
                
    def pause(self):
        print('pause thread')
        self.__flag.clear()
    
    def resume(self):
        print('resume thread')
        self.__flag.set()
    
    def stop(self):
        print('stop thread')
        self.__flag.set()
        self.__running.clear()

    def isPaused(self):
        return bool( not self.__flag.is_set() and self.__running.is_set() )

    def isStopped(self):
        return bool( self.__flag.is_set() and not self.__running.is_set() )



    
        
    
