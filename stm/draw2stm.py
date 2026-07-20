#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 ThreadedSerial 的主函数 + 回调函数
- 主线程: 持续向 STM32 发送传感器数据 (根据工作状态调整发送策略)
- 回调函数: 解析 STM32 发来的指令, 改变上位机工作状态
"""

import time
import threading
from datetime import datetime
from imu.read_imu import *
from uart import ThreadedSerial  # 导入你提供的类


# ==================================================
# 全局工作状态 (通过线程锁保护)
# ==================================================
work_state = "NORMAL"
state_lock = threading.Lock()


def get_state():
    with state_lock:
        return work_state


def set_state(new_state):
    global work_state
    with state_lock:
        old = work_state
        work_state = new_state
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{ts} STATE] 工作状态变更: {old} -> {new_state}")


# ==================================================
# 回调函数: 每次收到 STM32 数据时自动触发
# ==================================================
def on_stm32_data_received(data):
    """
    STM32 数据回调函数
    - 由后台接收线程调用, data 是 bytes 类型
    - 根据 STM32 发来的内容改变工作状态
    """
    try:
        text = data.decode('ascii').strip()
    except UnicodeDecodeError:
        print(f"[回调] 收到非ASCII数据: {data.hex(' ').upper()}")
        return

    # 如果一次收到多条指令 (用换行分隔), 逐条处理
    messages = text.split('\n')
    for msg in messages:
        msg = msg.strip().upper()
        if not msg:
            continue

        # ----- 根据你的协议修改下面的判断逻辑 -----

        if "STOP" in msg:
            set_state("STOP")

        elif "NORMAL" in msg:
            set_state("NORMAL")

        elif "ALARM" in msg:
            set_state("ALARM")

        elif "LOWPOWER" in msg:
            set_state("LOWPOWER")

        elif msg.startswith("FREQ:"):
            # 示例: STM32 可动态指定发送频率, 如 "FREQ:100"
            try:
                freq = int(msg.split(":")[1])
                print(f"[回调] STM32 要求发送频率: {freq}ms")
            except ValueError:
                print(f"[回调] 频率解析失败: {msg}")

        else:
            print(f"[回调] 未识别的指令: {msg}")


# ==================================================
# 主函数: 发送循环
# ==================================================
def main():
    PORT = "/dev/ttyS3"
    BAUD = 115200

    # 创建串口实例, 注册回调函数
    ser = ThreadedSerial(port=PORT, baudrate=BAUD, callback=on_stm32_data_received)
    ser.start()   # 启动后台接收线程
    try:
        #-----初始化代码开始-----
        i = 0
        speed_x , speed_y = 0,0
        #-----初始化代码结束-----
        while True:
            state = get_state()
            # ----- 循环代码开始 -----
            if i <=100:
                speed_x,speed_y = 10,0
            elif 100<i<=150:
                speed_x,speed_y = 0,10
            elif 150<i<=250:
                speed_x,speed_y = -10,0
            elif 250<i<=300:
                speed_x,speed_y = 0,-10
            else:
                i = -5
            
            #-----循环代码结束-----

            # -----状态代码开始-----
            if state == "NORMAL":
                ser.send(f"{speed_x} {speed_y}\n")
                i = i + 5
                time.sleep(0.1)        

            elif state == "ALARM":
                ser.send(f"ALARM:\n")
                time.sleep(0.2)  

            elif state == "STOP":
                # 停止发送, 但仍监听 STM32 指令 (等待 NORMAL 恢复)
                time.sleep(1.0)        # 空转等待

            elif state == "LOWPOWER":
                ser.send(f"LP:\n")
                time.sleep(2.0)        # 2秒一次, 省电

            else:
                print(f"[WARN] 未知状态: {state}, 使用默认策略")
                ser.send(f"SENSOR:\n")
                time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n[INFO] 用户中断 (Ctrl+C)")
    finally:
        ser.stop()


if __name__ == '__main__':
    main()
