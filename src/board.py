# Brochage du module ESP32-2424S012 :
# ESP32-C3, écran rond 1,28" GC9A01 240x240 (SPI), tactile CST816D (I2C).
from machine import I2C, PWM, SPI, Pin

import cst816
import gc9a01

LCD_SCK = 6
LCD_MOSI = 7
LCD_CS = 10
LCD_DC = 2
LCD_BL = 3
LCD_SPI_BAUD = 40_000_000

TOUCH_SDA = 4
TOUCH_SCL = 5
TOUCH_INT = 0
TOUCH_RST = 1

BTN_BOOT = 9  # bouton BOOT, actif à l'état bas

_backlight = None


def init_display(rotation=0):
    # L'ESP32-C3 n'a qu'un bus SPI utilisable : SPI(1)
    spi = SPI(1, baudrate=LCD_SPI_BAUD, polarity=0, phase=0,
              sck=Pin(LCD_SCK), mosi=Pin(LCD_MOSI))
    lcd = gc9a01.GC9A01(spi, dc=Pin(LCD_DC), cs=Pin(LCD_CS), rotation=rotation)
    set_backlight(100)
    return lcd


def set_backlight(percent):
    global _backlight
    if _backlight is None:
        _backlight = PWM(Pin(LCD_BL), freq=1000)
    _backlight.duty_u16(max(0, min(100, percent)) * 65535 // 100)


def init_touch():
    i2c = I2C(0, sda=Pin(TOUCH_SDA), scl=Pin(TOUCH_SCL), freq=400_000)
    return cst816.CST816(i2c, rst=Pin(TOUCH_RST), irq=Pin(TOUCH_INT))


def boot_button():
    return Pin(BTN_BOOT, Pin.IN, Pin.PULL_UP)
