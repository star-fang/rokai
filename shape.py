import cv2

class ShapeDetector:
    SHAPE_UNIDENTIFIED = 0
    SHAPE_TRIANGLE = 1
    SHAPE_RECTANGLE = 2
    SHAPE_SQUARE = 3
    SHAPE_PENTAGON = 5
    SHAPE_CIRCLE = 9
    def __init__(self) -> None:
        pass

    def detect(self, contour, epsilon = 0.04):
        shape = self.SHAPE_UNIDENTIFIED
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon * peri, True)

        len_approx = len(approx)
        if len_approx == 3:
            shape = self.SHAPE_TRIANGLE
        elif len_approx == 4:
            x, y, w, h = cv2.boundingRect(approx)
            ar = w / float(h)
            shape = self.SHAPE_SQUARE if  ar >= 0.95 and ar <= 1.05 else self.SHAPE_RECTANGLE
        elif len_approx == 5:
            shape = self.SHAPE_PENTAGON
        else:
            shape = self.SHAPE_CIRCLE
        return shape