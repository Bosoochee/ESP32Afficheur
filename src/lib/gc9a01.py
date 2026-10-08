# Pilote MicroPython minimal pour l'écran rond GC9A01 (240x240, RGB565).
# Pas de framebuffer complet (115 Ko) : on écrit directement dans la RAM
# de l'écran par fenêtres, avec un petit tampon réutilisé.
import struct
import time

import framebuf
from machine import Pin
from micropython import const

_SWRESET = const(0x01)
_CASET = const(0x2A)
_RASET = const(0x2B)
_RAMWR = const(0x2C)
_MADCTL = const(0x36)

# MADCTL : MY=0x80, MX=0x40, MV=0x20, BGR=0x08
# Orientation constatée sur l'ESP32-2424S012 : rotation 0 = BGR seul.
_ROTATIONS = (0x08, 0x68, 0xC8, 0xA8)

# Séquence d'initialisation du fabricant : (commande, données, délai ms)
_INIT = (
    (0xEF, b"", 0),
    (0xEB, b"\x14", 0),
    (0xFE, b"", 0),
    (0xEF, b"", 0),
    (0xEB, b"\x14", 0),
    (0x84, b"\x40", 0),
    (0x85, b"\xFF", 0),
    (0x86, b"\xFF", 0),
    (0x87, b"\xFF", 0),
    (0x88, b"\x0A", 0),
    (0x89, b"\x21", 0),
    (0x8A, b"\x00", 0),
    (0x8B, b"\x80", 0),
    (0x8C, b"\x01", 0),
    (0x8D, b"\x01", 0),
    (0x8E, b"\xFF", 0),
    (0x8F, b"\xFF", 0),
    (0xB6, b"\x00\x20", 0),
    (0x3A, b"\x05", 0),  # COLMOD : 16 bits/pixel
    (0x90, b"\x08\x08\x08\x08", 0),
    (0xBD, b"\x06", 0),
    (0xBC, b"\x00", 0),
    (0xFF, b"\x60\x01\x04", 0),
    (0xC3, b"\x13", 0),
    (0xC4, b"\x13", 0),
    (0xC9, b"\x22", 0),
    (0xBE, b"\x11", 0),
    (0xE1, b"\x10\x0E", 0),
    (0xDF, b"\x21\x0C\x02", 0),
    (0xF0, b"\x45\x09\x08\x08\x26\x2A", 0),
    (0xF1, b"\x43\x70\x72\x36\x37\x6F", 0),
    (0xF2, b"\x45\x09\x08\x08\x26\x2A", 0),
    (0xF3, b"\x43\x70\x72\x36\x37\x6F", 0),
    (0xED, b"\x1B\x0B", 0),
    (0xAE, b"\x77", 0),
    (0xCD, b"\x63", 0),
    (0x70, b"\x07\x07\x04\x0E\x0F\x09\x07\x08\x03", 0),
    (0xE8, b"\x34", 0),
    (0x62, b"\x18\x0D\x71\xED\x70\x70\x18\x0F\x71\xEF\x70\x70", 0),
    (0x63, b"\x18\x11\x71\xF1\x70\x70\x18\x13\x71\xF3\x70\x70", 0),
    (0x64, b"\x28\x29\xF1\x01\xF1\x00\x07", 0),
    (0x66, b"\x3C\x00\xCD\x67\x45\x45\x10\x00\x00\x00", 0),
    (0x67, b"\x00\x3C\x00\x00\x00\x01\x54\x10\x32\x98", 0),
    (0x74, b"\x10\x85\x80\x00\x00\x4E\x00", 0),
    (0x98, b"\x3E\x07", 0),
    (0x35, b"", 0),  # TEON
    (0x21, b"", 0),  # INVON : nécessaire sur ce panneau
    (0x11, b"", 120),  # SLPOUT
    (0x29, b"", 20),  # DISPON
)


def color565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


BLACK = const(0x0000)
WHITE = const(0xFFFF)
RED = const(0xF800)
GREEN = const(0x07E0)
BLUE = const(0x001F)
YELLOW = const(0xFFE0)
CYAN = const(0x07FF)
MAGENTA = const(0xF81F)


class GC9A01:
    def __init__(self, spi, dc, cs, rst=None, width=240, height=240, rotation=0):
        self.spi = spi
        self.dc = dc
        self.cs = cs
        self.rst = rst
        self.width = width
        self.height = height
        self._buf = bytearray(512)
        self._buf_color = None
        dc.init(Pin.OUT, value=0)
        cs.init(Pin.OUT, value=1)
        if rst is not None:
            rst.init(Pin.OUT, value=1)
        self.reset()
        for cmd, data, delay in _INIT:
            self._cmd(cmd, data)
            if delay:
                time.sleep_ms(delay)
        self.rotation(rotation)

    def _cmd(self, cmd, data=None):
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes((cmd,)))
        if data:
            self.dc(1)
            self.spi.write(data)
        self.cs(1)

    def _data(self, data):
        self.cs(0)
        self.dc(1)
        self.spi.write(data)
        self.cs(1)

    def _window(self, x0, y0, x1, y1):
        self._cmd(_CASET, struct.pack(">HH", x0, x1))
        self._cmd(_RASET, struct.pack(">HH", y0, y1))
        self._cmd(_RAMWR)

    def reset(self):
        if self.rst is not None:
            self.rst(0)
            time.sleep_ms(10)
            self.rst(1)
        else:
            self._cmd(_SWRESET)
        time.sleep_ms(120)

    def rotation(self, r):
        self._cmd(_MADCTL, bytes((_ROTATIONS[r % 4],)))

    def blit_buffer(self, buf, x, y, w, h):
        """Envoie un tampon RGB565 big-endian de w*h pixels."""
        self._window(x, y, x + w - 1, y + h - 1)
        self._data(buf)

    def fill_rect(self, x, y, w, h, color):
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, self.width), min(y + h, self.height)
        if x0 >= x1 or y0 >= y1:
            return
        buf = self._buf
        if self._buf_color != color:
            hi, lo = color >> 8, color & 0xFF
            for i in range(0, len(buf), 2):
                buf[i] = hi
                buf[i + 1] = lo
            self._buf_color = color
        self._window(x0, y0, x1 - 1, y1 - 1)
        chunks, rest = divmod((x1 - x0) * (y1 - y0) * 2, len(buf))
        self.cs(0)
        self.dc(1)
        for _ in range(chunks):
            self.spi.write(buf)
        if rest:
            self.spi.write(memoryview(buf)[:rest])
        self.cs(1)

    def fill(self, color):
        self.fill_rect(0, 0, self.width, self.height, color)

    def pixel(self, x, y, color):
        self.fill_rect(x, y, 1, 1, color)

    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.fill_rect(x, y, 1, h, color)

    def fill_circle(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.hline(cx - dx, cy + dy, 2 * dx + 1, color)

    def fill_ring(self, cx, cy, r_out, r_in, color):
        """Anneau plein entre les rayons r_in (exclu) et r_out (inclus)."""
        for dy in range(-r_out, r_out + 1):
            xo = int((r_out * r_out - dy * dy) ** 0.5)
            if -r_in < dy < r_in:
                xi = int((r_in * r_in - dy * dy) ** 0.5)
                self.hline(cx - xo, cy + dy, xo - xi, color)
                self.hline(cx + xi + 1, cy + dy, xo - xi, color)
            else:
                self.hline(cx - xo, cy + dy, 2 * xo + 1, color)

    def text(self, s, x, y, color=WHITE, bg=BLACK, scale=1):
        """Police 8x8 intégrée de MicroPython (ASCII seulement, pas d'accents)."""
        w = 8 * len(s)
        sw, sh = w * scale, 8 * scale
        if not w:
            return
        if x < 0 or y < 0 or x + sw > self.width or y + sh > self.height:
            raise ValueError("texte hors de l'écran")
        mono = bytearray(w)
        fb = framebuf.FrameBuffer(mono, w, 8, framebuf.MONO_HLSB)
        fb.text(s, 0, 0, 1)
        fg_hi, fg_lo, bg_hi, bg_lo = color >> 8, color & 0xFF, bg >> 8, bg & 0xFF
        line = bytearray(sw * 2)
        self._window(x, y, x + sw - 1, y + sh - 1)
        self.cs(0)
        self.dc(1)
        for row in range(8):
            i = 0
            for col in range(w):
                if fb.pixel(col, row):
                    hi, lo = fg_hi, fg_lo
                else:
                    hi, lo = bg_hi, bg_lo
                for _ in range(scale):
                    line[i] = hi
                    line[i + 1] = lo
                    i += 2
            for _ in range(scale):
                self.spi.write(line)
        self.cs(1)

    def text_center(self, s, y, color=WHITE, bg=BLACK, scale=1):
        self.text(s, (self.width - 8 * len(s) * scale) // 2, y, color, bg, scale)

    def font_width(self, font, s):
        w = 0
        for c in s:
            w += font.GLYPHS[c][0]
        return w

    def font_text(self, font, s, x, y, color=WHITE, bg=BLACK):
        """Police lissée 4 bits produite par tools/make_font.py (glyphes limités)."""
        h = font.HEIGHT
        if x < 0 or y < 0 or x + self.font_width(font, s) > self.width or y + h > self.height:
            raise ValueError("texte hors de l'écran")
        # 16 niveaux de mélange fond -> couleur, en RGB565 big-endian
        pal = bytearray(32)
        fr, fg, fb = color >> 11, (color >> 5) & 0x3F, color & 0x1F
        br, bgg, bb = bg >> 11, (bg >> 5) & 0x3F, bg & 0x1F
        for v in range(16):
            c = (((br + (fr - br) * v // 15) << 11) | ((bgg + (fg - bgg) * v // 15) << 5)
                 | (bb + (fb - bb) * v // 15))
            pal[2 * v] = c >> 8
            pal[2 * v + 1] = c & 0xFF
        line = None
        for ch in s:
            w, data = font.GLYPHS[ch]
            bw = (w + 1) // 2
            if line is None or len(line) < bw * 4:
                line = bytearray(bw * 4)
            row_bytes = memoryview(line)[:w * 2]
            self._window(x, y, x + w - 1, y + h - 1)
            self.cs(0)
            self.dc(1)
            k = 0
            for _ in range(h):
                i = 0
                for _ in range(bw):
                    b = data[k]
                    p = (b >> 4) << 1
                    line[i] = pal[p]
                    line[i + 1] = pal[p + 1]
                    p = (b & 0x0F) << 1
                    line[i + 2] = pal[p]
                    line[i + 3] = pal[p + 1]
                    i += 4
                    k += 1
                self.spi.write(row_bytes)
            self.cs(1)
            x += w
