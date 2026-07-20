#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
import time

# def i2cInit():
#     serial = i2c(port=3, address=0x3C)   # 常见树莓派配置
#     device = ssd1306(serial, rotate=0)
#     device.contrast(100)  #调整对比度（亮度）

def main():
    try:
        # 根据实际扫描结果修改 port 和 address
        serial = i2c(port=3, address=0x3C)   # 常见树莓派配置
        device = ssd1306(serial, rotate=0)
        device.contrast(100)  #调整对比度（亮度）
    
        print("OLED 初始化成功")
    except Exception as e:
        print(f"初始化失败: {e}")
        return
    # i2cInit()
    with canvas(device) as draw:
        draw.text((0, 0), "Hello World!", fill="white")

    print("按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        device.cleanup()
        print("程序已退出")

if __name__ == "__main__":
    main()