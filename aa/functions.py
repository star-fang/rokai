self.template_expand_troops = cv2.threshold(cv2.imread(f'{assets_dir}/btn_expand_troops.png',cv2.IMREAD_GRAYSCALE), 
                                                     TH_BUTTON0, 255, cv2.THRESH_BINARY)[1]

def checkCurrentTroops( self, img_src:np.ndarray=None, img_gray:np.ndarray=None):
        if img_src is None or img_gray is None:
            img_src, img_gray = self.captureScreen()
        h, w = img_gray.shape[:2]
        ix = int(0.9*w)
        iy = int(0.1*h)
        img_right_bar = img_gray[ iy:h-iy, ix: w ]
        img_right_bar_thresh = cv2.threshold(img_right_bar, TH_BUTTON1, 255, cv2.THRESH_BINARY)[1]

        match_result = self.multiScaleMatch(self.template_expand_troops, img_right_bar_thresh)
        if match_result is not None:
            matchVal,top_left,bottom_right,r = match_result
            rTopLeft = (int(r*top_left[0]),int(r*top_left[1]))
            rBottomRight = (int(r*bottom_right[0]),int(r*bottom_right[1]))
            localExpandButtonBox = rTopLeft + rBottomRight
            x1,y1,x2,y2 = localExpandButtonBox
            buttonWidth = x2 - x1
            tmpBox = (ix+x2, iy+y1, w, iy+y2)
            tx1, ty1, tx2, ty2 = tmpBox
            tw = tx2 - tx1
            th = ty2 - ty1
            if tw > 3*buttonWidth:
                try:
                    tx1 += buttonWidth // 2
                    tx2 -= buttonWidth
                    ty2 = int( ty2 - 0.15*th )
                    globalTroopsCountBox = (tx1, ty1, tx2 , ty2)
                    self.addRect.emit( globalTroopsCountBox,255,0,255,255, 2 )
                    cnt_gray, r = self.ocr.preprocessing(src_gray = img_gray[ty1:ty2,tx1:tx2], height= 64, adjMode=False, stackAxis=1)
                    
                    #hsv = cv2.cvtColor(cv2.cvtColor(cnt_gray, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2HSV )
                    #mask = self.ocr.hsvMasking( hsv, adjMode = True )
                    #a = np.full_like(cnt_gray, 255)
                    #cnt_color = cv2.bitwise_and( a, a, mask = mask )
                    #cv2.imshow('cnt',cnt_color)
                    #cv2.waitKey(0)
                    
                    if cnt_gray is not None:
                        troops_txt = self.ocr.read(cnt_gray,config='--oem 1 --psm 13')
                        print( f't count: {troops_txt}')
                except Exception as e:
                    print( f'exception while count troops:{e}')