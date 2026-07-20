from read_imu import *


def main():
    try:
        spi = spidev.SpiDev()
        spi.open(3, 0)              # bus 3, CS 0
        spi.max_speed_hz = 1000000  # 1MHz (Burst mode max = 1MHz)
        spi.mode = 0b11             # Mode 3 (CPOL=1, CPHA=1)
        spi.bits_per_word = 8

        init_sensor(spi)

        while True:
            data = get_data(spi)
            print(data)
            # print(type(data))

    except KeyboardInterrupt:
        print("\n退出")

    finally:
        spi_write_reg8(spi, ADDR_MODE_CTRL + 1, 0x02)
        spi.close()



if __name__ == "__main__":
    main()