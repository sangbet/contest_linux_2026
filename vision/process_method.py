import numpy as np
import cv2


def FindCounter_cv2(img):
    img_gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    img_blur = cv2.GaussianBlur(img_gray,(7,7),1)
    img_canny = cv2.Canny(img_blur,50,150)

    kernel = np.ones((5,5),np.uint8)
    img_dilated = cv2.dilate(img_canny,kernel,1)

    contours,_ = cv2.findContours(img_dilated,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)

    max_area = 0
    best_appr = None
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000:
            peri = cv2.arcLength(cnt,True)
            appr = cv2.approxPolyDP(cnt,0.04*peri,True)


            if len(appr) == 4 and cv2.isContourConvex(appr):
                if area > max_area:
                    max_area = area
                    best_appr = appr
    if best_appr is not None:
        cv2.drawContours(img,[best_appr],0,(0,255,0),3)
        for point in best_appr:
            cv2.circle(img,(point[0][0],point[0,1]),6,[255,0,0],0)

        M = cv2.moments(best_appr)
        if M["m00"] != 0:
            cx,cy = int(M["m10"]/M["m00"]),int(M["m01"]/M["m00"])
            cv2.circle(img,(cx,cy),3,(0,0,255),2,0)
    
    return img