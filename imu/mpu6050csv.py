#!/usr/bin/env python3
"""
泰山派 RK3566 读取 MPU6050 数据并保存为 CSV 文件
MPU6050 I2C 地址: 0x68 (AD0 接 GND)
"""

import smbus2
import time
import csv
from datetime import datetime

# ====== 配置 ======
I2C_BUS = 3              # 泰山派 I2C 总线号（根据实际情况修改）
MPU_ADDR = 0x68          # MPU6050 I2C 地址

# ====== MPU6050 寄存器地址 ======
REG_PWR_MGMT_1 = 0x6B   # 电源管理寄存器
REG_ACCEL_XOUT_H = 0x3B # 加速度计 X 轴高字节
REG_GYRO_XOUT_H  = 0x43 # 陀螺仪 X 轴高字节
REG_TEMP_OUT_H   = 0x41 # 温度高字节
REG_WHO_AM_I     = 0x75 # 器件ID寄存器

# 量程配置
ACCEL_RANGE_2G  = 0x00
ACCEL_RANGE_4G  = 0x08
ACCEL_RANGE_8G  = 0x10
ACCEL_RANGE_16G = 0x18

GYRO_RANGE_250  = 0x00
GYRO_RANGE_500  = 0x08
GYRO_RANGE_1000 = 0x10
GYRO_RANGE_2000 = 0x18


def read_word(bus, reg):
    """读取 16 位数据（大端序，高位在前）"""
    high = bus.read_byte_data(MPU_ADDR, reg)
    low  = bus.read_byte_data(MPU_ADDR, reg + 1)
    value = (high << 8) | low
    # 转为有符号数
    if value >= 0x8000:
        value -= 0x10000
    return value


class MPU6050:
    def __init__(self, bus_num=I2C_BUS, address=MPU_ADDR):
        self.bus = smbus2.SMBus(bus_num)
        self.address = address
        self._init_sensor()

    def _init_sensor(self):
        # 1. 唤醒 MPU6050
        self.bus.write_byte_data(self.address, REG_PWR_MGMT_1, 0x00)
        time.sleep(0.1)

        # 2. 验证设备 ID
        who_am_i = self.bus.read_byte_data(self.address, REG_WHO_AM_I)
        if who_am_i == 0x68:
            print("✅ MPU6050 识别成功 (WHO_AM_I = 0x68)")
        else:
            print(f"⚠️ WHO_AM_I = 0x{who_am_i:02X}，非预期值，请检查接线")

        # 3. 设置量程
        self._set_accel_range(ACCEL_RANGE_2G)
        self._set_gyro_range(GYRO_RANGE_500)
        time.sleep(0.05)

    def _set_accel_range(self, range_val):
        self.bus.write_byte_data(self.address, 0x1C, range_val)
        if range_val == ACCEL_RANGE_2G:
            self.accel_lsb = 16384.0
        elif range_val == ACCEL_RANGE_4G:
            self.accel_lsb = 8192.0
        elif range_val == ACCEL_RANGE_8G:
            self.accel_lsb = 4096.0
        else:
            self.accel_lsb = 2048.0

    def _set_gyro_range(self, range_val):
        self.bus.write_byte_data(self.address, 0x1B, range_val)
        if range_val == GYRO_RANGE_250:
            self.gyro_lsb = 131.0
        elif range_val == GYRO_RANGE_500:
            self.gyro_lsb = 65.5
        elif range_val == GYRO_RANGE_1000:
            self.gyro_lsb = 32.8
        else:
            self.gyro_lsb = 16.4

    def read_accel(self):
        x = read_word(self.bus, REG_ACCEL_XOUT_H) / self.accel_lsb
        y = read_word(self.bus, REG_ACCEL_XOUT_H + 2) / self.accel_lsb
        z = read_word(self.bus, REG_ACCEL_XOUT_H + 4) / self.accel_lsb
        return x, y, z

    def read_gyro(self):
        x = read_word(self.bus, REG_GYRO_XOUT_H) / self.gyro_lsb
        y = read_word(self.bus, REG_GYRO_XOUT_H + 2) / self.gyro_lsb
        z = read_word(self.bus, REG_GYRO_XOUT_H + 4) / self.gyro_lsb
        return x, y, z

    def read_temp(self):
        raw = read_word(self.bus, REG_TEMP_OUT_H)
        temp = raw / 340.0 + 36.53
        return temp

    def read_all(self):
        accel = self.read_accel()
        gyro  = self.read_gyro()
        temp  = self.read_temp()
        return {
            'accel': {'x': accel[0], 'y': accel[1], 'z': accel[2]},
            'gyro':  {'x': gyro[0],  'y': gyro[1],  'z': gyro[2]},
            'temp':  temp
        }

    def close(self):
        self.bus.close()


# ====== 主程序 ======
if __name__ == '__main__':
    # 生成带时间戳的 CSV 文件名
    current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"mpu6050_data_{current_time_str}.csv"

    try:
        mpu = MPU6050(bus_num=I2C_BUS)
        print("-" * 70)
        print(f"  泰山派 RK3566 + MPU6050 数据采集 (保存至: {csv_filename})")
        print("-" * 70)

        # 打开 CSV 文件准备写入
        with open(csv_filename, mode='w', newline='') as csv_file:
            # 定义表头
            fieldnames = [
                'Timestamp', 
                'Accel_X(g)', 'Accel_Y(g)', 'Accel_Z(g)', 
                'Gyro_X(deg/s)', 'Gyro_Y(deg/s)', 'Gyro_Z(deg/s)', 
                'Temp(C)'
            ]
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            
            # 写入表头
            writer.writeheader()
            
            # 设置采样间隔（秒），这里设为 0.1 秒 (10Hz)
            sample_interval = 0.1 
            
            while True:
                loop_start = time.time()
                
                # 读取传感器数据
                data = mpu.read_all()
                # 获取当前精确时间
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                # 写入 CSV 行
                writer.writerow({
                    'Timestamp': now,
                    'Accel_X(g)': f"{data['accel']['x']:.4f}",
                    'Accel_Y(g)': f"{data['accel']['y']:.4f}",
                    'Accel_Z(g)': f"{data['accel']['z']:.4f}",
                    'Gyro_X(deg/s)': f"{data['gyro']['x']:.4f}",
                    'Gyro_Y(deg/s)': f"{data['gyro']['y']:.4f}",
                    'Gyro_Z(deg/s)': f"{data['gyro']['z']:.4f}",
                    'Temp(C)': f"{data['temp']:.2f}"
                })
                
                # 刷新缓存，防止突然断电或 Ctrl+C 退出时数据丢失
                csv_file.flush()

                # 终端打印
                print(f"[{now}] "
                      f"Accel: X={data['accel']['x']:+.2f}, Y={data['accel']['y']:+.2f}, Z={data['accel']['z']:+.2f} g | "
                      f"Gyro: X={data['gyro']['x']:+.2f}, Y={data['gyro']['y']:+.2f}, Z={data['gyro']['z']:+.2f} °/s")

                # 保证采样间隔准确
                elapsed = time.time() - loop_start
                if elapsed < sample_interval:
                    time.sleep(sample_interval - elapsed)

    except KeyboardInterrupt:
        print("\n检测到 Ctrl+C，程序已停止")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        if 'mpu' in dir():
            mpu.close()
        print(f"✅ 数据已成功保存至 {csv_filename}")
