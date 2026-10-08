# Affiche au centre du cadran la température d'un capteur Domoticz, entourée
# d'un anneau à la couleur du jour Tempo d'EDF, sur un fond vert en heures
# creuses et orange en heures pleines.
import time

import network
import requests

import board
import font_petit
import font_rond
import secrets
import tempo
from gc9a01 import BLACK, BLUE, GREEN, RED, WHITE, color565

DOMOTICZ_URL = "http://192.168.0.10:8080"
DOMOTICZ_IDX = 66
PERIOD_S = 60  # le capteur se met à jour toutes les 5 min environ
HTTP_TIMEOUT_S = 10  # sans délai, un Domoticz muet bloquerait toute la boucle

# Affichage tourné de 90° vers la droite (voir _ROTATIONS dans gc9a01.py)
ROTATION = 1

STATUS_Y = 176

# Couleur Tempo : anneau au bord de l'écran, relu toutes les heures et au
# changement de jour Tempo (6 h), ou 10 min après un échec
RING_R_IN = 105  # anneau de 14 px
RING_COLORS = {tempo.BLUE: BLUE, tempo.WHITE: WHITE, tempo.RED: RED}
TEMPO_REFRESH_S = 3600
TEMPO_RETRY_S = 600

# Fond : vert en heures creuses (22 h - 6 h), orange en heures pleines
# Couleurs assombries pour ne pas éblouir ; le texte est alors en blanc
GREEN_DIM = color565(0, 80, 0)
ORANGE_DIM = color565(110, 50, 0)

# Rétroéclairage réduit la nuit, de 22 h à 7 h (heure française)
NIGHT_START_H = 22
NIGHT_END_H = 7
BACKLIGHT_DAY = 100
BACKLIGHT_NIGHT = 20

LABEL = "Outside T°C"
LABEL_GAP = 10  # entre le libellé et la température


def connect_wifi(timeout_ms=20000):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                return False
            time.sleep_ms(200)
    return True


def read_temperature():
    url = "{}/json.htm?type=command&param=getdevices&rid={}".format(DOMOTICZ_URL, DOMOTICZ_IDX)
    r = requests.get(url, timeout=HTTP_TIMEOUT_S)
    try:
        data = r.json()
    finally:
        r.close()
    return data["result"][0]["Temp"]


class Screen:
    """Mémorise ce qui est affiché pour tout redessiner au changement de fond."""

    def __init__(self, lcd):
        self.lcd = lcd
        self.bg = BLACK
        self.temp = None
        self.status = ""
        self.tempo = None

    def fg(self):
        # Vert sur noir tant que l'heure est inconnue, blanc sur fond coloré
        return GREEN if self.bg == BLACK else WHITE

    def set_background(self, bg):
        if bg == self.bg:
            return
        self.bg = bg
        self.lcd.fill(bg)
        self.set_tempo(self.tempo, force=True)
        self.draw_label()
        self.set_temperature(self.temp)
        self.set_status(self.status, force=True)

    def clear_band(self, y, h):
        # Efface une bande horizontale sans toucher l'anneau Tempo : on s'arrête
        # à la corde du cercle intérieur sur la ligne la plus éloignée du centre
        dy = max(abs(y - 120), abs(y + h - 1 - 120))
        half = int((RING_R_IN * RING_R_IN - dy * dy) ** 0.5)
        self.lcd.fill_rect(120 - half, y, 2 * half + 1, h, self.bg)

    def draw_label(self):
        lcd = self.lcd
        x = (lcd.width - lcd.font_width(font_petit, LABEL)) // 2
        y = (lcd.height - font_rond.HEIGHT) // 2 - LABEL_GAP - font_petit.HEIGHT
        lcd.font_text(font_petit, LABEL, x, y, self.fg(), self.bg)

    def set_temperature(self, value):
        self.temp = value
        lcd = self.lcd
        s = ("--.-" if value is None else "{:.1f}".format(value)) + "°C"
        x = (lcd.width - lcd.font_width(font_rond, s)) // 2
        y = (lcd.height - font_rond.HEIGHT) // 2
        self.clear_band(y, font_rond.HEIGHT)
        lcd.font_text(font_rond, s, x, y, self.fg(), self.bg)

    def set_status(self, msg, force=False):
        if msg == self.status and not force:
            return
        self.status = msg
        self.clear_band(STATUS_Y, 8)
        if msg:
            self.lcd.text_center(msg, STATUS_Y, RED if self.bg == BLACK else WHITE, self.bg)

    def set_tempo(self, color, force=False):
        # Anneau au bord du cadran ; de la couleur du fond tant que la couleur est inconnue
        if color == self.tempo and not force:
            return
        self.tempo = color
        self.lcd.fill_ring(120, 120, 119, RING_R_IN, RING_COLORS.get(color, self.bg))


def main():
    lcd = board.init_display(ROTATION)
    lcd.fill(BLACK)
    scr = Screen(lcd)
    # Test de l'anneau au démarrage : chaque couleur Tempo pendant 1 s
    for c in (tempo.BLUE, tempo.WHITE, tempo.RED):
        scr.set_tempo(c)
        time.sleep(1)
    scr.set_tempo(None)
    scr.draw_label()
    scr.set_temperature(None)
    if not secrets.WIFI_SSID:
        scr.set_status("Wi-Fi non configure")
        return
    rte = getattr(secrets, "RTE_ID_BASE64", "")
    synced = False  # RTC réglé en UTC par NTP
    backlight = BACKLIGHT_DAY  # niveau posé par board.init_display()
    day_ok = None  # jour Tempo de la dernière lecture réussie
    next_tempo = time.ticks_ms()
    while True:
        online = connect_wifi()
        if online and not synced:
            try:
                tempo.sync_clock()
                synced = True
            except Exception as e:
                print("NTP:", repr(e))
        if synced:
            now_s = time.time()
            scr.set_background(GREEN_DIM if tempo.off_peak(now_s) else ORANGE_DIM)
            h = tempo.local_hour(now_s)
            light = BACKLIGHT_NIGHT if h >= NIGHT_START_H or h < NIGHT_END_H else BACKLIGHT_DAY
            if light != backlight:
                backlight = light
                board.set_backlight(light)
        try:
            if not online:
                scr.set_status("Wi-Fi injoignable")
            else:
                scr.set_temperature(read_temperature())
                scr.set_status("")
        except Exception as e:  # réseau ou réponse inattendue : on réessaie
            print("Domoticz:", repr(e))
            scr.set_status("Domoticz injoignable")
        now = time.ticks_ms()
        if online and rte and (time.ticks_diff(now, next_tempo) >= 0
                               or (day_ok and tempo.tempo_day(time.time()) != day_ok)):
            try:
                tempo.sync_clock()
                day = tempo.tempo_day(time.time())
                c = tempo.fetch_color(day)
                print("Tempo:", day, c)
                day_ok = day
                next_tempo = time.ticks_add(now, TEMPO_REFRESH_S * 1000)
                scr.set_tempo(c)
            except Exception as e:  # on garde la dernière couleur connue
                print("Tempo:", repr(e))
                next_tempo = time.ticks_add(now, TEMPO_RETRY_S * 1000)
        time.sleep(PERIOD_S)


main()
