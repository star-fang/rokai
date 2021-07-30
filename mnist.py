from PyQt5.QtCore import QObject, pyqtSignal
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from time import time

class MnistCnnModel(QObject):

    IMG_ROWS = 28
    IMG_COLS = 28
    IMG_CHANNELS = 1

    loadingSignal = pyqtSignal( str )
    loadCompleteSignal = pyqtSignal( str, float )

    def __init__(self):
        QObject.__init__(self)
    
    def loadKerasModule( self ):
        self.loadingSignal.emit( 'keras')
        time_load_start = time()
        import tensorflow.keras as tk
        self.kerasImageMethods:tk.preprocessing.image = tk.preprocessing.image
        self.model:tk.Sequential = tk.models.load_model('final_model.h5')
        self.loadCompleteSignal.emit( 'keras', time()- time_load_start)

    def predict(self, img):
        img_norm = self.prepareImg(img)
        digit = np.argmax( self.model.predict(img_norm), axis=-1 )
        print(f'result:{digit}')

    def prepareImg( self, img ):
        if not isinstance(img, np.ndarray):
            pil_img:Image = self.kerasImageMethods.array_to_img(img)
            img = self.kerasImageMethods.img_to_array(pil_img)

        img:np.ndarray = img.reshape(1, 28, 28, 1)
        img = img.astype('float32')
        img = img / 255.0 # normalize 0 ~ 1

        return img
        
    def loadDataset(self):
        from tensorflow.keras.datasets import mnist
        from tensorflow.keras.utils import to_categorical
        (trainX, trainY), (testX, testY) = mnist.load_data()
        trainX = trainX.reshape((trainX.shape[0], 28, 28, 1))
        testX = testX.reshape((testX.shape[0], 28, 28, 1))

        trainY = to_categorical(trainY)
        testY = to_categorical(testY)
        self.dataset = {'trainX': trainX, 'trainY': trainY, 'testX': testX, 'testY': testY}
    
    def loadImageFile(self, filename):
        img_origin = self.kerasImageMethods.load_img(filename, color_mode='grayscale', target_size=(28, 28))
        plt.imshow(img_origin)
        plt.show()

        img = self.kerasImageMethods.img_to_array(img_origin)
        img = img.reshape(1, 28, 28, 1)
        img = img.astype('float32')
        img = img / 255.0

        return img

# scale pixels
def prep_pixels(train, test):
	# convert from integers to floats
	train_norm = train.astype('float32')
	test_norm = test.astype('float32')
	# normalize to range 0-1
	train_norm = train_norm / 255.0
	test_norm = test_norm / 255.0
	# return normalized images
	return train_norm, test_norm