import cv2
from process_method import *


img = cv2.imread("C:/Users/sangbet/Pictures/Camera Roll/WIN_20260720_13_01_45_Pro.jpg")
# img = cv2.imread('C:/Users/sangbet/Pictures/Camera Roll/WIN_20260720_13_01_45_Pro.jpg', cv2.IMREAD_GRAYSCALE)
# img = cv2.resize(img,(640,480))
if img is None:
    print("Error: Could not load image.")
    exit()

img0 = img
#图像处理开始

img,_,_ = FindCounter_cv2(img)

# sobel_x = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
# sobel_y = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
# img = np.sqrt(sobel_x**2 + sobel_y**2)





#图像处理结束

cv2.imshow("Display window", img)
# cv2.imshow("Display window", img0)

k = cv2.waitKey(0)

if k == 27:
    # 关闭所有 OpenCV 窗口
    cv2.destroyAllWindows()