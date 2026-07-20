import sys
import os
import numpy as np
import cv2
import time
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#-----导入个人包-----
from vision.web_server import VideoStreamer
from vision.process_method import *
from stm.uart import ThreadedSerial
from stm.send2stmbyimu import get_state,set_state,on_stm32_data_received

# work_state = "NORMAL"
# state_lock = threading.Lock()

def main():
    #-----串口设置-----
    PORT = "/dev/ttyS3"
    BAUD = 115200

    #-----摄像机设置-----
    cap = None
    streamer = None

    #-----目标位置-----
    target_x , target_y = 0 , 0

    try:
        # --- 初始化摄像头 ---
        print("正在初始化相机...")
        cap = cv2.VideoCapture(10)
        
        if not cap.isOpened():
            print("无法打开相机！")
            return
            
        print("相机启动成功")

        ser = ThreadedSerial(port=PORT, baudrate=BAUD, callback=on_stm32_data_received)
        ser.start()   # 启动后台接收线程

        # 设置摄像头参数（可选）
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        # --- 创建并启动推流服务 ---
        streamer = VideoStreamer(port=5000)
        streamer.start()

        # --- 主循环 ---
        print("正在采集并推流")
        fps = 0
        last_time = time.time()
        
        while True:
            # 读取帧（OpenCV 标准方式）
            ret, frame = cap.read()
            
            if not ret:
                print("无法读取画面")
                break

            # 计算 FPS
            curr_time = time.time()
            #-----处理代码开始-----

            frame,target_x,target_y = FindCounter_cv2(frame)
            if target_x is not None:
                target_x ,target_y = target_x - (640/2),target_y - (480/2)
                # print(f"{target_x},{target_y}")
                if(abs(target_x)<10):target_x = 0
                if(abs(target_y)<10):target_y = 0
                ser.send(f"{target_x/2} {-target_y/1.5}\n")
            else:
                # print("do not find target")
                ser.send(f"{0} {0}\n")


            #-----处理代码结束-----
            fps = 1 / (curr_time - last_time) * 0.2 + fps * 0.8
            last_time = curr_time
            
            # 添加 FPS 显示
            cv2.putText(frame, "fps:{}".format(round(fps, 2)),
                        (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 2)

            # 推流
            streamer.update_frame(frame)
            
            # 可选：显示画面（调试用）
            # cv2.imshow('Camera', frame)
            # if cv2.waitKey(1) & 0xFF == ord('q'):
            #     break

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("正在释放资源...")
        
        if cap is not None:
            cap.release()
            print("相机已释放")
            
        print("正在停止 Web 服务...")
        if streamer is not None:
            streamer.stop()
            print("Web 服务已停止")
            
        print("程序已完全退出")


if __name__ == "__main__":
    main()
