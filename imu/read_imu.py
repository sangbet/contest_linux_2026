#!/usr/bin/env python3
"""G354 SPI 读取"""
import spidev
import time

# ─── 寄存器地址 ───
ADDR_WIN_CTRL    = 0x7E
ADDR_MODE_CTRL   = 0x02
ADDR_BURST_CTRL1 = 0x0C
ADDR_BURST_CTRL2 = 0x0E
ADDR_SMPL_CTRL   = 0x04
ADDR_FILTER_CTRL = 0x06
ADDR_UART_CTRL   = 0x08
ADDR_GLOB_CMD    = 0x0A
ADDR_MSC_CTRL    = 0x02
ADDR_DIAG_STAT   = 0x04

# ─── SPI 读写函数 ───
def spi_write_reg8(spi, addr, value):
    """写 8-bit 到寄存器（写命令格式: bit15=1, bit14:8=addr, bit7:0=data）"""
    cmd = 0x8000 | ((addr & 0x7F) << 8) | (value & 0xFF)
    spi.xfer2([(cmd >> 8) & 0xFF, cmd & 0xFF])
    time.sleep(25e-6)  # tWRITERATE = 40us min, 使用 25us+传输时间≈满足

def spi_write_reg16(spi, addr_lo, value):
    """写 16-bit 到寄存器（低字节在前）"""
    spi_write_reg8(spi, addr_lo,     value & 0xFF)
    spi_write_reg8(spi, addr_lo + 1, (value >> 8) & 0xFF)

def spi_read_reg16(spi, addr_even):
    """读 16-bit 寄存器（读命令格式: bit15=0, bit14:8=addr, bit7:0=don't care）"""
    cmd = (addr_even & 0x7E) << 8
    # 第一次发送读命令（响应数据在本次返回但无效）
    spi.xfer2([(cmd >> 8) & 0xFF, cmd & 0xFF])
    time.sleep(25e-6)  # tSTALL = 20us min
    # 第二次发送 dummy，获取响应数据
    resp = spi.xfer2([0x00, 0x00])
    time.sleep(25e-6)  # tREADRATE = 40us min
    return (resp[0] << 8) | resp[1]

# ─── 辅助函数 ───
def to_signed16(val):
    if val >= 0x8000:
        val -= 0x10000
    return val

def to_signed32(val):
    if val >= 0x80000000:
        val -= 0x100000000
    return val

# ─── 初始化 ───
def init_sensor(spi):
    """配置 G354 SPI 模式（按数据手册 8.1 节流程）"""

    # 0. 等待上电初始化完成
    print("等待 IMU 上电初始化...")
    time.sleep(0.9)  # Power-On Start-Up Time: 800ms max

    # 0a. 检查 NOT_READY 位 (Window 1, GLOB_CMD bit[10])
    spi_write_reg8(spi, ADDR_WIN_CTRL, 0x01)  # WINDOW=1
    for _ in range(100):
        glob_cmd = spi_read_reg16(spi, ADDR_GLOB_CMD)
        if (glob_cmd & 0x0400) == 0:  # NOT_READY == 0
            break
        time.sleep(0.05)
    else:
        print("NOT_READY 超时!")
    print("  IMU 就绪")

    # 0b. 检查 HARD_ERR (Window 0, DIAG_STAT bit[6:5])
    spi_write_reg8(spi, ADDR_WIN_CTRL, 0x00)  # WINDOW=0
    diag = spi_read_reg16(spi, ADDR_DIAG_STAT)
    hard_err = (diag >> 5) & 0x03
    if hard_err != 0:
        print(f"HARD_ERR = {hard_err:02b}, IMU 可能故障!")
    else:
        print("  硬件检查通过")

    # 1. 确保在配置模式 (Window 0, MODE_CTRL bit[9:8] = 10)
    spi_write_reg8(spi, ADDR_MODE_CTRL + 1, 0x02)  # Config mode
    time.sleep(0.2)

    # 2. 切到 Window 1 配置寄存器
    spi_write_reg8(spi, ADDR_WIN_CTRL, 0x01)
    time.sleep(0.05)

    # 3. 设置采样率 (SMPL_CTRL: DOUT_RATE = 0x03 → 250Sps)
    spi_write_reg16(spi, ADDR_SMPL_CTRL, 0x0303)  # 250Sps, TAP>=8
    time.sleep(0.01)

    # 4. 设置滤波器 (FILTER_CTRL: Moving Average TAP=8 → 00011)
    spi_write_reg16(spi, ADDR_FILTER_CTRL, 0x0003)  # TAP=8
    time.sleep(0.01)

    # 5. 确保 UART Auto 模式关闭（SPI 必须用 Manual 模式）
    spi_write_reg16(spi, ADDR_UART_CTRL, 0x0000)
    time.sleep(0.01)

    # 6. 设置 DRDY 输出 (MSC_CTRL: DRDY_ON=1, DRDY_POL=0 active low)
    spi_write_reg16(spi, ADDR_MSC_CTRL, 0x0006)  # DRDY_ON=1, DRDY_POL=0(low)
    time.sleep(0.01)

    # 7. 配置 Burst 输出
    #    BURST_CTRL1 = 0xF007: FLAG+TEMP+GYRO+ACCL+GPIO+COUNT+CHKSM 输出
    #    BURST_CTRL2 = 0x7000: TEMP+GYRO+ACCL 均为 32-bit
    spi_write_reg16(spi, ADDR_BURST_CTRL1, 0xF007)
    spi_write_reg16(spi, ADDR_BURST_CTRL2, 0x7000)
    time.sleep(0.01)

    # 8. 回读验证
    b1 = spi_read_reg16(spi, ADDR_BURST_CTRL1)
    b2 = spi_read_reg16(spi, ADDR_BURST_CTRL2)
    print(f"  BURST_CTRL1=0x{b1:04X}  BURST_CTRL2=0x{b2:04X}")

    # 9. 切回 Window 0
    spi_write_reg8(spi, ADDR_WIN_CTRL, 0x00)
    time.sleep(0.05)

    # 10. 启动采样 (MODE_CTRL bit[9:8] = 01 → Sampling mode)
    spi_write_reg8(spi, ADDR_MODE_CTRL + 1, 0x01)
    time.sleep(0.2)
    print("配置完成，开始读取数据...\n")

# ─── Burst 读取 ───
def read_burst(spi):
    """读取一帧 Burst 数据 (18 words)
    
    BURST_CTRL1=0xF007, BURST_CTRL2=0x7000 时的数据格式:
    Word 0:  FLAG(ND/EA)
    Word 1:  TEMP_HIGH      ← 温度高16位
    Word 2:  TEMP_LOW       ← 温度低16位
    Word 3:  XGYRO_HIGH     ← X陀螺高16位
    Word 4:  XGYRO_LOW      ← X陀螺低16位
    Word 5:  YGYRO_HIGH
    Word 6:  YGYRO_LOW
    Word 7:  ZGYRO_HIGH
    Word 8:  ZGYRO_LOW
    Word 9:  XACCL_HIGH
    Word 10: XACCL_LOW
    Word 11: YACCL_HIGH
    Word 12: YACCL_LOW
    Word 13: ZACCL_HIGH
    Word 14: ZACCL_LOW
    Word 15: GPIO           ← 16-bit
    Word 16: COUNT          ← 16-bit
    Word 17: CHECKSUM       ← 16-bit
    """
    # 发送 Burst 命令 0x8000
    spi.xfer2([0x80, 0x00])
    time.sleep(50e-6)  # tSTALL1 = 45us min

    words = []
    for i in range(18):
        resp = spi.xfer2([0x00, 0x00])
        words.append((resp[0] << 8) | resp[1])
        # tREADRATE2 = 32us min; 1MHz下16bit=16us, 需额外 >= 16us
        time.sleep(20e-6)

    # 校验: checksum = sum(words[0:17]) & 0xFFFF
    checksum = sum(words[0:17]) & 0xFFFF
    if checksum != words[17]:
        print(f"校验错误: calc=0x{checksum:04X} recv=0x{words[17]:04X}")
        return None

    return words

# ─── 数据解析 ───
def parse_data(words):
    """解析 18 words Burst 数据 (32-bit 模式)
    
    数据手册 Table 6.17 格式 + 比例因子
    """
    flag    = words[0]
    temp_raw  = to_signed32((words[1] << 16) | words[2])    # TEMP (32-bit)
    gyro_x    = to_signed32((words[3] << 16) | words[4])    # XGYRO (32-bit)
    gyro_y    = to_signed32((words[5] << 16) | words[6])    # YGYRO (32-bit)
    gyro_z    = to_signed32((words[7] << 16) | words[8])    # ZGYRO (32-bit)
    acc_x     = to_signed32((words[9] << 16) | words[10])   # XACCL (32-bit)
    acc_y     = to_signed32((words[11] << 16) | words[12])  # YACCL (32-bit)
    acc_z     = to_signed32((words[13] << 16) | words[14])  # ZACCL (32-bit)
    gpio      = words[15]      # ★ 修正: GPIO 是独立的 16-bit word
    counter   = words[16]      # ★ 修正: COUNT 是 16-bit, 不是 32-bit!


    # 陀螺仪: 16-bit SF = 0.016 (deg/s)/LSB → 32-bit: SF/65536
    gyro_scale = 0.016 / 65536.0  # deg/s per LSB (32-bit)

    # 加速度计: 16-bit SF = 0.2 mG/LSB → 32-bit: SF/65536
    acc_scale = 0.2 / 65536.0  # mG per LSB (32-bit)

    # 温度: 16-bit SF = -0.0037918 °C/LSB
    # 32-bit 公式: T = (SF/65536) * (A - 172621824) + 25
    temp_sf = -0.0037918 / 65536.0  # °C per LSB (32-bit)
    temp_c = temp_sf * (temp_raw - 172621824) + 25.0

    return {
        'gyro_x': gyro_x * gyro_scale,
        'gyro_y': gyro_y * gyro_scale,
        'gyro_z': gyro_z * gyro_scale,
        'acc_x':  acc_x * acc_scale,
        'acc_y':  acc_y * acc_scale,
        'acc_z':  acc_z * acc_scale,
        'temp':   temp_c,
        'gpio':   gpio,
        'counter': counter,
        'flag':   flag,
    }


def  get_data(spi):

    words = read_burst(spi)
    if words:
        data = parse_data(words)
    return data    

# ─── 主循环 ───
def main():
    spi = spidev.SpiDev()
    spi.open(3, 0)              # bus 3, CS 0
    spi.max_speed_hz = 1000000  # 1MHz (Burst mode max = 1MHz)
    spi.mode = 0b11             # Mode 3 (CPOL=1, CPHA=1)
    spi.bits_per_word = 8

    init_sensor(spi)

    print(f"{'GyroX(dps)':>12} {'GyroY(dps)':>12} {'GyroZ(dps)':>12} "
          f"{'AcclX(mG)':>12} {'AcclY(mG)':>12} {'AcclZ(mG)':>12} "
          f"{'Temp(C)':>8} {'Count':>8}")
    print("-" * 96)

    try:
        while True:
            words = read_burst(spi)
            if words:
                data = parse_data(words)
                print(f"{data['gyro_x']:12.4f} {data['gyro_y']:12.4f} {data['gyro_z']:12.4f} "
                      f"{data['acc_x']:12.2f} {data['acc_y']:12.2f} {data['acc_z']:12.2f} "
                      f"{data['temp']:8.2f} {data['counter']:8d}", end='\r')
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n\n退出")
    finally:
        # 返回配置模式
        spi_write_reg8(spi, ADDR_MODE_CTRL + 1, 0x02)
        spi.close()

if __name__ == "__main__":
    main()



