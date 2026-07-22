#!/usr/bin/env python3
"""
泰山派 RK3566 读取 MPU6050 数据
MPU6050 I2C 地址: 0x68 (AD0 接 GND)
"""

import smbus2
import time

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
ACCEL_RANGE_2G  = 0x00  # ±2g
ACCEL_RANGE_4G  = 0x08  # ±4g
ACCEL_RANGE_8G  = 0x10  # ±8g
ACCEL_RANGE_16G = 0x18  # ±16g

GYRO_RANGE_250  = 0x00  # ±250°/s
GYRO_RANGE_500  = 0x08  # ±500°/s
GYRO_RANGE_1000 = 0x10  # ±1000°/s
GYRO_RANGE_2000 = 0x18  # ±2000°/s


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
        # 1. 唤醒 MPU6050（写入 0 到电源管理寄存器）
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
        # 写入加速度配置寄存器 (0x1C)
        self.bus.write_byte_data(self.address, 0x1C, range_val)
        if range_val == ACCEL_RANGE_2G:
            self.accel_lsb = 16384.0      # ±2g => 16384 LSB/g
        elif range_val == ACCEL_RANGE_4G:
            self.accel_lsb = 8192.0
        elif range_val == ACCEL_RANGE_8G:
            self.accel_lsb = 4096.0
        else:
            self.accel_lsb = 2048.0

    def _set_gyro_range(self, range_val):
        # 写入陀螺仪配置寄存器 (0x1B)
        self.bus.write_byte_data(self.address, 0x1B, range_val)
        if range_val == GYRO_RANGE_250:
            self.gyro_lsb = 131.0         # ±250°/s => 131 LSB/(°/s)
        elif range_val == GYRO_RANGE_500:
            self.gyro_lsb = 65.5
        elif range_val == GYRO_RANGE_1000:
            self.gyro_lsb = 32.8
        else:
            self.gyro_lsb = 16.4

    def read_accel(self):
        """读取加速度计数据 (单位: g)"""
        x = read_word(self.bus, REG_ACCEL_XOUT_H) / self.accel_lsb
        y = read_word(self.bus, REG_ACCEL_XOUT_H + 2) / self.accel_lsb
        z = read_word(self.bus, REG_ACCEL_XOUT_H + 4) / self.accel_lsb
        return x, y, z

    def read_gyro(self):
        """读取陀螺仪数据 (单位: °/s)"""
        x = read_word(self.bus, REG_GYRO_XOUT_H) / self.gyro_lsb
        y = read_word(self.bus, REG_GYRO_XOUT_H + 2) / self.gyro_lsb
        z = read_word(self.bus, REG_GYRO_XOUT_H + 4) / self.gyro_lsb
        return x, y, z

    def read_temp(self):
        """读取温度数据 (单位: °C)"""
        raw = read_word(self.bus, REG_TEMP_OUT_H)
        temp = raw / 340.0 + 36.53
        return temp

    def read_all(self):
        """一次性读取所有数据"""
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
    try:
        mpu = MPU6050(bus_num=I2C_BUS)
        print("-" * 60)
        print("  泰山派 RK3566 + MPU6050 数据读取")
        print("-" * 60)

        while True:
            data = mpu.read_all()
            print(f"加速度 | X: {data['accel']['x']:+.2f} g  "
                  f"Y: {data['accel']['y']:+.2f} g  "
                  f"Z: {data['accel']['z']:+.2f} g")
            print(f"陀螺仪 | X: {data['gyro']['x']:+.2f} °/s  "
                  f"Y: {data['gyro']['y']:+.2f} °/s  "
                  f"Z: {data['gyro']['z']:+.2f} °/s")
            print(f"温度   | {data['temp']:.1f} °C")
            print("-" * 60)
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n程序已停止")
    finally:
        if 'mpu' in dir():
            mpu.close()
