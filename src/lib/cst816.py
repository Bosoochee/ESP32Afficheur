# Pilote MicroPython pour le contrôleur tactile CST816S/CST816D (I2C).
import time

from machine import Pin
from micropython import const

_ADDR = const(0x15)
_REG_GESTURE = const(0x01)
_REG_DIS_AUTO_SLEEP = const(0xFE)

NONE = const(0x00)
SWIPE_UP = const(0x01)
SWIPE_DOWN = const(0x02)
SWIPE_LEFT = const(0x03)
SWIPE_RIGHT = const(0x04)
CLICK = const(0x05)
DOUBLE_CLICK = const(0x0B)
LONG_PRESS = const(0x0C)


class CST816:
    def __init__(self, i2c, rst=None, irq=None, addr=_ADDR):
        self.i2c = i2c
        self.addr = addr
        self.irq = irq
        if irq is not None:
            irq.init(Pin.IN, Pin.PULL_UP)
        if rst is not None:
            rst.init(Pin.OUT, value=0)
            time.sleep_ms(10)
            rst(1)
            time.sleep_ms(50)
        # En veille automatique, la puce ne répond plus sur l'I2C.
        try:
            self.i2c.writeto_mem(self.addr, _REG_DIS_AUTO_SLEEP, b"\x01")
        except OSError:
            pass

    def read(self):
        """Renvoie (x, y, geste) si un doigt est posé, sinon None."""
        try:
            d = self.i2c.readfrom_mem(self.addr, _REG_GESTURE, 6)
        except OSError:
            return None
        if not d[1]:
            return None
        x = ((d[2] & 0x0F) << 8) | d[3]
        y = ((d[4] & 0x0F) << 8) | d[5]
        return x, y, d[0]
