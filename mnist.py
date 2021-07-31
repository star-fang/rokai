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


crbW = coord_removed_bg.shape[1]

                    
                    
                    row_pixel_sum = np.sum(coord_removed_bg, axis=1)
                    proj = row_pixel_sum / 255
                    vHist = np.zeros_like( coord_removed_bg )

                    projStartPos = 0
                    maxPos = [0, 0]
                    row_score_sum = 0
                    max_score_sum = 0
                    row_start = False
                    for i, val in enumerate( proj ):
                        invVal = int(crbW - val)
                        score = invVal / float(crbW)
                        if score > 0.01:
                            if not row_start:
                                row_start = True
                                projStartPos = i
                                row_score_sum = score
                            else:
                                row_score_sum += score
                        else:
                            if row_start:
                                row_start = False
                                if row_score_sum > max_score_sum:
                                    max_score_sum = row_score_sum
                                    maxPos[0] = projStartPos
                                    maxPos[1] = i
                        cv2.line( vHist, (0, i), (invVal, i), 255, 1)

                    print( f'maxPos:{maxPos}')
                    if maxPos[1] - maxPos[0] == 0:
                        return
                    self.addRect.emit( (cbox[0], cbox[1] + maxPos[0], cbox[2], cbox[1] + maxPos[1]),0,255,0,255, 1  )
                    
                    histDist = np.hstack([coord_removed_bg, vHist])
                    #cv2.imshow('histDst', histDist)
                    #cv2.waitKey(0)
                    coord_removed_bg = coord_removed_bg[ maxPos[0]: maxPos[1], 0:]
                    crbH = coord_removed_bg.shape[0]
                    #cv2.imshow('coord_removed_bg', coord_removed_bg)
                    #cv2.waitKey(0)
                    return

                    column_pixel_sum = np.sum(coord_removed_bg, axis = 0 )
                    proj = column_pixel_sum / 255

                    hHist = np.zeros_like( coord_removed_bg )
                    word_start = False
                    word_start_pos = 0
                    score_sum = 0
                    for i, val in enumerate( proj ):
                        invVal = crbH - int(val)
                        #cv2.line( hist, (i, 0), (i, invVal), 255, 1)
                        score = invVal / float(crbH) # 0 ~ 1
                        if score < 0.01:
                            #cv2.line( hist, (i, 0), (i, crbH), 0, 1) # not word
                            if word_start:
                                #print( f'word end at {i}')
                                word_start = False
                                if( i - word_start_pos > 1 ):
                                    self.addRect.emit( (cbox[0] + word_start_pos, cbox[1], cbox[0] + i, cbox[3]),255,0,0,255, 1  )
                                    word_image = coord_removed_bg[ 0: , word_start_pos: i]
                                    
                                    mnistImageRatio = MnistCnnModel.IMG_COLS / float(MnistCnnModel.IMG_ROWS)
                                    wordImageRatio = word_image.shape[1] / word_image.shape[0]
                                    if( mnistImageRatio < wordImageRatio ):
                                        word_image = imutils.resize( word_image, width = int(6* MnistCnnModel.IMG_COLS // 7) )
                                    else:
                                        word_image = imutils.resize( word_image, height = int(6* MnistCnnModel.IMG_ROWS // 7) )
                                    wiH, wiW = word_image.shape[:2]
                                    wimg_padding = np.zeros(( MnistCnnModel.IMG_ROWS, MnistCnnModel.IMG_COLS ), dtype=np.uint8)
                                    wimg_padding = 255 - wimg_padding
                                    try:
                                        wimg_padding[ int((MnistCnnModel.IMG_ROWS - wiH) / 2): int((MnistCnnModel.IMG_ROWS + wiH) / 2),
                                              int((MnistCnnModel.IMG_COLS - wiW) / 2): int((MnistCnnModel.IMG_COLS + wiW) / 2)  ] = word_image
                                    except ValueError:
                                        pass

                                    #if not cv2.imwrite(os.path.join(os.path.expanduser('~'),'Desktop',f'word{i}.png'), wimg_stable):
                                    #    raise Exception("Could not write image")
                                    print('score sum: %.3f' % score_sum )
                                    cv2.imshow('wi', wimg_padding)
                                    cv2.waitKey(0)
                                    #coords_txt = self.ocr.read( wimg_padding, config='-l eng --oem 1 --psm 8')
                                    #coords_txt = coords_txt.replace('\n',' ')
                                    #print( coords_txt )
                                    self.mnist.predict( wimg_padding )
                                    print('-----------------------')
                                    
                        else:
                            cv2.line( hHist, (i, 0), (i, invVal), 255, 1) # word
                            if not word_start:
                                word_start = True
                                score_sum = 0
                                word_start_pos = i
                            else:
                                score_sum += score
                    
                    histDist = np.vstack([coord_removed_bg, hHist])
                    cv2.imshow('histDst', histDist)
                    cv2.waitKey(0)