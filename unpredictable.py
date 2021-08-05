from numpy.random import Generator, MT19937, SeedSequence

class MT19937Generator():
    def __init__(self, entropy = None):
        self.changeSeed(entropy)
    
    def changeSeed( self, entropy = None ):
        sg = SeedSequence(entropy)
        self.bitGenerator = MT19937(sg)

    def generateRandomFloat(self, min:float = 0.0, max:float = 1.0): # generate 0 ~ n ( hundredths 0.00 )
        if min == max :
            return min

        if min > max:
            temp = min
            min = max
            max = temp
                
        return max - Generator(self.bitGenerator).random() * (max - min)
    
    def generateRandomInt(self):
        randomInt = self.int_32(self.bitGenerator.random_raw())
        self.bitGenerator = self.bitGenerator.jumped()
        return randomInt
    
    def int_32(self, number):
        return int(0xFFFFFFFF & number)
                



    
        
    
