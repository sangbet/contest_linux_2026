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
from GPIO.UART.uart import ThreadedSerial  # 导入你提供的类

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306


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


    serial = i2c(port=3, address=0x3C)   # 常见树莓派配置
    device = ssd1306(serial, rotate=0)
    device.contrast(100)  #调整对比度（亮度）

    # 创建串口实例, 注册回调函数
    ser = ThreadedSerial(port=PORT, baudrate=BAUD, callback=on_stm32_data_received)
    ser.start()   # 启动后台接收线程

    spi = spidev.SpiDev()
    spi.open(3, 0)              # bus 3, CS 0
    spi.max_speed_hz = 1000000  # 1MHz (Burst mode max = 1MHz)
    spi.mode = 0b11             # Mode 3 (CPOL=1, CPHA=1)
    spi.bits_per_word = 8

    init_sensor(spi)

    try:
        error = [0,0]
        for i in range(100):
            data = get_data(spi)
            error[0] = error[0] + data['gyro_z']
            error[1] = error[1] + data['gyro_y']
        error[0],error[1] = error[0]/100,error[1]/100
        while True:
            state = get_state()

            # ----- 读取传感器 -----
            data = get_data(spi)
            sensor_data = [data['gyro_z'] - error[0],data['gyro_y']-error[1]]
            with canvas(device) as draw:
                draw.text((0, 0), f"X:{sensor_data[0]:.5f}", fill="white")
                draw.text((0, 0), f"X:{sensor_data[1]:.5f}", fill="white")
            if abs(sensor_data[0])<0.5 :sensor_data[0]=0
            if abs(sensor_data[1])<0.5 :sensor_data[1]=0
            # ----- 根据工作状态决定发送策略 -----
            if state == "NORMAL":
                ser.send(f"{sensor_data[0]} {sensor_data[1]}\n")
                time.sleep(0.1)        # 500ms 一次

            elif state == "ALARM":
                ser.send(f"ALARM:{sensor_data}\n")
                time.sleep(0.2)        # 200ms 加快上报

            elif state == "STOP":
                # 停止发送, 但仍监听 STM32 指令 (等待 NORMAL 恢复)
                time.sleep(1.0)        # 空转等待

            elif state == "LOWPOWER":
                ser.send(f"LP:{sensor_data}\n")
                time.sleep(2.0)        # 2秒一次, 省电

            else:
                print(f"[WARN] 未知状态: {state}, 使用默认策略")
                ser.send(f"SENSOR:{sensor_data}\n")
                time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n[INFO] 用户中断 (Ctrl+C)")
    finally:
        ser.stop()


if __name__ == '__main__':
    main()
