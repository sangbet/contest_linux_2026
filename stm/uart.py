#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RK3566 串口收发测试工具
用于与STM32下位机进行UART通信测试

依赖安装:
    pip install pyserial

使用方法:
    python3 serial_test.py /dev/ttyS3 115200
"""

import sys
import time
import threading
import argparse
from datetime import datetime


import serial
import serial.tools.list_ports


# ============================================================
# 模块一: 基础串口收发 (适合简单测试)
# ============================================================
class SimpleSerialTest:
    """基础收发测试: 发送一条指令, 等待回复"""

    def __init__(self, port, baudrate=115200, timeout=1.0):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout
        )
        if self.ser.is_open:
            print(f"[OK] 串口已打开: {port} @ {baudrate}bps")
        else:
            print(f"[ERROR] 串口打开失败: {port}")
            sys.exit(1)

    def send_text(self, text):
        """发送ASCII文本"""
        data = (text + '\n').encode('ascii')
        self.ser.write(data)
        print(f"[TX->] {text}")

    def send_hex(self, hex_str):
        """发送十六进制数据, 如 "01 03 00 00 00 01 84 0A" """
        hex_str = hex_str.replace(' ', '').replace('\n', '')
        data = bytes.fromhex(hex_str)
        self.ser.write(data)
        print(f"[TX->] HEX: {data.hex(' ').upper()} ({len(data)} bytes)")

    def recv(self, timeout=2.0):
        """接收数据并打印"""
        self.ser.timeout = timeout
        data = self.ser.read(1024)
        if data:
            try:
                text = data.decode('ascii')
                print(f"[<-RX] {text.strip()}")
            except UnicodeDecodeError:
                print(f"[<-RX] HEX: {data.hex(' ').upper()} ({len(data)} bytes)")
        else:
            print(f"[<-RX] (超时, 未收到数据)")
        return data

    def close(self):
        self.ser.close()
        print("[OK] 串口已关闭")


# ============================================================
# 模块二: 多线程连续收发 (适合实际项目使用)
# ============================================================
class ThreadedSerial:
    """
    多线程串口通信类
    - 后台线程持续接收数据
    - 主线程可随时发送
    - 支持回调函数处理接收到的数据
    """

    def __init__(self, port, baudrate=115200, callback=None):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        self.callback = callback
        self._running = False
        self._recv_thread = None
        self._lock = threading.Lock()
        self.rx_count = 0
        self.tx_count = 0

        if self.ser.is_open:
            print(f"[OK] 串口已打开: {port} @ {baudrate}bps")
        else:
            raise RuntimeError(f"串口打开失败: {port}")

    def _recv_loop(self):
        """后台接收线程"""
        print("[INFO] 接收线程已启动")
        while self._running:
            data = self.ser.read(256)
            if data:
                self.rx_count += len(data)
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                try:
                    text = data.decode('ascii')
                    print(f"[{timestamp} RX] {text.strip()}")
                except UnicodeDecodeError:
                    print(f"[{timestamp} RX] HEX: {data.hex(' ').upper()}")
                if self.callback:
                    self.callback(data)
        print("[INFO] 接收线程已停止")

    def send(self, data):
        """发送数据 (bytes或str)"""
        if isinstance(data, str):
            data = data.encode('ascii')
        with self._lock:
            self.ser.write(data)
            self.tx_count += len(data)
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        try:
            text = data.decode('ascii')
            print(f"[{timestamp} TX] {text.strip()}")
        except UnicodeDecodeError:
            print(f"[{timestamp} TX] HEX: {data.hex(' ').upper()}")

    def send_hex(self, hex_str):
        """发送十六进制字符串"""
        hex_str = hex_str.replace(' ', '').replace('\n', '')
        data = bytes.fromhex(hex_str)
        self.send(data)

    def start(self):
        """启动接收线程"""
        self._running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def stop(self):
        """停止接收线程并关闭串口"""
        self._running = False
        if self._recv_thread:
            self._recv_thread.join(timeout=2.0)
        self.ser.close()
        print(f"\n[统计] 发送: {self.tx_count} 字节, 接收: {self.rx_count} 字节")
        print("[OK] 串口已关闭")


# ============================================================
# 模块三: 交互式命令行 (最实用的测试工具)
# ============================================================
def interactive_mode(port, baudrate):
    ser = ThreadedSerial(port, baudrate)
    ser.start()

    print("\n" + "=" * 60)
    print("  交互式串口测试工具")
    print("  - 直接输入文本发送 (自动加换行符)")
    print("  - 输入 hex:01 03 00 00 00 01 84 0A 发送十六进制")
    print("  - 输入 quit 退出")
    print("=" * 60 + "\n")

    try:
        while True:
            user_input = input(">> ")
            if not user_input:
                continue
            if user_input.strip().lower() == 'quit':
                break
            if user_input.lower().startswith('hex:'):
                hex_data = user_input[4:].strip()
                ser.send_hex(hex_data)
            else:
                ser.send(user_input + '\n')
    except KeyboardInterrupt:
        print("\n[INFO] 用户中断")
    finally:
        ser.stop()


# ============================================================
# 模块四: 自动化测试 (发送指令并验证回复)
# ============================================================
def auto_test(port, baudrate):
    print("\n" + "=" * 60)
    print("  自动化串口测试")
    print("=" * 60)

    test = SimpleSerialTest(port, baudrate, timeout=2.0)

    test_cases = [
        ("测试1: 发送HELLO",       "HELLO",     "text", "WORLD"),
        ("测试2: 发送LED ON",      "LED ON",    "text", "OK"),
        ("测试3: 发送LED OFF",     "LED OFF",   "text", "OK"),
        ("测试4: 读取温度",         "GET_TEMP",  "text", "TEMP"),
        ("测试5: 发送Modbus帧",    "01 03 00 00 00 01 84 0A", "hex", None),
    ]

    pass_count = 0
    fail_count = 0

    for desc, data, dtype, expected in test_cases:
        print(f"\n{'─' * 50}")
        print(f"[执行] {desc}")
        print(f"{'─' * 50}")

        if dtype == "hex":
            test.send_hex(data)
        else:
            test.send_text(data)

        time.sleep(0.1)
        reply = test.recv(timeout=2.0)

        if expected:
            if reply and expected.encode('ascii') in reply:
                print(f"[结果] ✅ PASS (收到预期关键字: {expected})")
                pass_count += 1
            else:
                print(f"[结果] ❌ FAIL (未收到预期关键字: {expected})")
                fail_count += 1
        else:
            print(f"[结果] ⏭️  SKIP (无预期校验)")
            pass_count += 1

    test.close()
    print(f"\n{'=' * 60}")
    print(f"  测试完成: ✅ {pass_count} 通过, ❌ {fail_count} 失败")
    print(f"{'=' * 60}")


# ============================================================
# 工具函数: 列出可用串口
# ============================================================
def list_ports():
    print("可用串口设备:")
    print("-" * 50)
    ports = serial.tools.list_ports.comports()
    if not ports:
        import glob
        dev_ports = glob.glob('/dev/ttyS*') + glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        if dev_ports:
            for p in sorted(dev_ports):
                print(f"  {p}")
        else:
            print("  未找到任何串口设备")
    else:
        for p in ports:
            print(f"  {p.device}  -  {p.description}")
    print("-" * 50)


# ============================================================
# 主函数
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='RK3566 串口收发测试工具 (与STM32通信)',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('port', nargs='?', default=None,
                        help='串口设备路径, 如 /dev/ttyS3\n不指定则列出可用串口')
    parser.add_argument('baudrate', nargs='?', type=int, default=115200,
                        help='波特率, 默认 115200')
    parser.add_argument('-m', '--mode', choices=['interactive', 'auto', 'simple'],
                        default='interactive',
                        help='运行模式:\n'
                             '  interactive (默认): 交互式命令行\n'
                             '  auto: 自动化测试\n'
                             '  simple: 简单收发测试')
    parser.add_argument('-l', '--list', action='store_true',
                        help='列出可用串口后退出')

    args = parser.parse_args()

    if args.list or args.port is None:
        list_ports()
        if not args.port:
            print("\n用法: python3 serial_test.py /dev/ttyS3 115200")
            return

    print(f"\n串口: {args.port}  波特率: {args.baudrate}  模式: {args.mode}\n")

    if args.mode == 'interactive':
        interactive_mode(args.port, args.baudrate)
    elif args.mode == 'auto':
        auto_test(args.port, args.baudrate)
    elif args.mode == 'simple':
        simple_test(args.port, args.baudrate)


def simple_test(port, baudrate):
    """简单收发测试示例"""
    test = SimpleSerialTest(port, baudrate)
    test.send_text("HELLO STM32")
    time.sleep(0.2)
    test.recv()
    test.send_hex("01 03 00 00 00 01 84 0A")
    time.sleep(0.2)
    test.recv()
    test.close()


if __name__ == '__main__':
    main()
