import sys
import types
import time
import os

# ==========================================
# 第一部分：万能补丁（伪造 RPi.GPIO 模块）
# ==========================================

class _SysfsBackend:
    """底层实际操作 sysfs 的类"""
    def __init__(self):
        self._exported_pins = set()

    def _write(self, path, value):
        try:
            with open(path, "w") as f:
                f.write(str(value))
        except IOError:
            pass

    def setup(self, pin, direction):
        if pin not in self._exported_pins:
            self._write("/sys/class/gpio/export", pin)
            self._exported_pins.add(pin)
            time.sleep(0.1) # 等待节点生成
        
        # direction 可能是 "OUT" 或 11 (RPi.GPIO.OUT的值) 等，统一转为小写
        d = "out" if str(direction).upper() == "OUT" else "in"
        self._write(f"/sys/class/gpio/gpio{pin}/direction", d)

    def output(self, pin, value):
        self._write(f"/sys/class/gpio/gpio{pin}/value", 1 if value else 0)

    def cleanup(self):
        for pin in list(self._exported_pins):
            self._write("/sys/class/gpio/unexport", pin)

# 实例化后端
_backend = _SysfsBackend()

# 定义伪装函数
def fake_setup(pin, mode):
    _backend.setup(pin, mode)

def fake_output(pin, value):
    _backend.output(pin, value)

def fake_setmode(mode):
    pass

def fake_cleanup():
    _backend.cleanup()

# 构建 RPi.GPIO 模块对象
fake_rpi_gpio = types.ModuleType('RPi.GPIO')
fake_rpi_gpio.RPI_INFO = {'P1_REVISION': 1} # 假装是树莓派
fake_rpi_gpio.BOARD = 10
fake_rpi_gpio.BCM = 11
fake_rpi_gpio.OUT = 'OUT' # luma 可能传入字符串或常量，统一用字符串
fake_rpi_gpio.IN = 'IN'
fake_rpi_gpio.HIGH = 1
fake_rpi_gpio.LOW = 0

# 绑定方法
fake_rpi_gpio.setup = fake_setup
fake_rpi_gpio.output = fake_output
fake_rpi_gpio.setmode = fake_setmode
fake_rpi_gpio.cleanup = fake_cleanup

# 注入到 sys.modules，让所有后续的 import RPi.GPIO 都指向我们的假模块
sys.modules['RPi'] = types.ModuleType('RPi')
sys.modules['RPi'].GPIO = fake_rpi_gpio
sys.modules['RPi.GPIO'] = fake_rpi_gpio

# ==========================================
# 第二部分：正常的 luma 驱动代码
# ==========================================

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import st7789

def main():
    # 定义引脚号 (Linux GPIO 编号)
    GPIO_DC  = 109
    GPIO_RST = 103
    
    # 初始化 SPI
    # 这里 gpio 参数传假模块也行，或者不传（因为系统级已经被我们伪造了）
    # 但为了保险，还是传进去，确保 serial 层面也用它
    try:
        serial = spi(
            port=3, 
            device=0, 
            gpio_DC=GPIO_DC, 
            gpio_RST=GPIO_RST, 
            gpio=fake_rpi_gpio,  # 传给 luma.core
            bus_speed_hz=32000000,
            spi_mode=0
        )
    except Exception as e:
        print(f"SPI 初始化失败: {e}")
        print("请确认 /dev/spidev3.0 存在")
        sys.exit(1)

    # 初始化屏幕
    # backlight_enabled=False 防止它去尝试操作我们不接的背光引脚
    try:
        device = st7789(
            serial, 
            width=240, 
            height=240, 
            rotate=3, 
            backlight_enabled=True,  # 尝试开启，如果有报错改为 False
            gpio=fake_rpi_gpio       # 这里也传进去，确保 device 层面用的也是假 GPIO
        )
        print("屏幕初始化成功！")
    except Exception as e:
        print(f"屏幕创建失败: {e}")
        # 如果依然报错，可能是因为 BL 引脚问题，尝试把 backlight_enabled 改为 False
        sys.exit(1)

    # 绘图测试
    print("开始绘图...")
    device.clear()

    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.line((0, 0, 240, 240), fill="red")
        draw.line((240, 0, 0, 240), fill="green")
        
        # 如果需要显示文字，确保系统有可用的字体，否则可能报错
        try:
            draw.text((10, 20), "Taishan Pi", fill="cyan")
        except:
            print("字体绘制失败（忽略）")

    print("显示完成。按 Ctrl+C 退出。")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n退出...")
        device.cleanup()
        fake_cleanup()

if __name__ == "__main__":
    main()
