# Affiche au centre du cadran les températures extérieure et intérieure de deux
# capteurs Domoticz, sur fond noir, entourée d'un anneau à la couleur du jour Tempo d'EDF et, juste à
# l'intérieur, d'un anneau vert en heures creuses et orange en heures pleines.
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
PERIOD_S = 60  # les capteurs se mettent à jour toutes les 5 min environ
HTTP_TIMEOUT_S = 10  # sans délai, un Domoticz muet bloquerait toute la boucle

# Orientation de l'affichage (voir _ROTATIONS dans gc9a01.py)
ROTATION = 0

# Deux lignes (libellé + température), centrées verticalement dans l'anneau
# intérieur ; le message d'état en dessous, 18 caractères au plus
SENSORS = (("Outside T°C", 66), ("Inside T°C", 83))  # (libellé, idx Domoticz)
LABEL_GAP = 4  # entre un libellé et sa température
ROW_GAP = 7  # entre la première température et le second libellé
ROW_H = font_petit.HEIGHT + LABEL_GAP + font_rond.HEIGHT
TOP_Y = 120 - (2 * ROW_H + ROW_GAP) // 2
STATUS_Y = 186

# Couleur Tempo : anneau au bord de l'écran, relu toutes les heures et au
# changement de jour Tempo (6 h), ou 10 min après un échec
RING_R_IN = 110  # anneau de 9 px (rayons 111 à 119)
RING_COLORS = {tempo.BLUE: BLUE, tempo.WHITE: WHITE, tempo.RED: RED}
TEMPO_REFRESH_S = 3600
TEMPO_RETRY_S = 600

# Anneau intérieur : vert en heures creuses (22 h - 6 h), orange en heures
# pleines, noir tant que NTP n'a pas réglé l'heure. 1 px de noir le sépare de
# l'anneau Tempo ; son rayon intérieur laisse passer "-10.5°C" (199 px de large)
HOURS_R_OUT = 109
HOURS_R_IN = 103  # anneau de 6 px (rayons 104 à 109)
ORANGE = color565(255, 120, 0)

# Rétroéclairage réduit la nuit, de 22 h à 7 h (heure française)
NIGHT_START_H = 22
NIGHT_END_H = 7
BACKLIGHT_DAY = 100
BACKLIGHT_NIGHT = 20


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


def read_temperature(idx):
    url = "{}/json.htm?type=command&param=getdevices&rid={}".format(DOMOTICZ_URL, idx)
    r = requests.get(url, timeout=HTTP_TIMEOUT_S)
    try:
        data = r.json()
    finally:
        r.close()
    return data["result"][0]["Temp"]


class Screen:
    """Mémorise ce qui est affiché pour ne redessiner que ce qui change."""

    def __init__(self, lcd):
        self.lcd = lcd
        self.status = ""
        self.tempo = None
        self.off_peak = None

    def clear_band(self, y, h):
        # Efface une bande horizontale sans toucher les anneaux : on s'arrête
        # à la corde du cercle intérieur sur la ligne la plus éloignée du centre
        dy = max(abs(y - 120), abs(y + h - 1 - 120))
        half = int((HOURS_R_IN * HOURS_R_IN - dy * dy) ** 0.5)
        self.lcd.fill_rect(120 - half, y, 2 * half + 1, h, BLACK)

    def draw_labels(self):
        lcd = self.lcd
        for i in range(len(SENSORS)):
            label = SENSORS[i][0]
            x = (lcd.width - lcd.font_width(font_petit, label)) // 2
            lcd.font_text(font_petit, label, x, TOP_Y + i * (ROW_H + ROW_GAP), WHITE, BLACK)

    def set_temperature(self, i, value):
        # i : rang du capteur dans SENSORS
        lcd = self.lcd
        s = ("--.-" if value is None else "{:.1f}".format(value)) + "°C"
        x = (lcd.width - lcd.font_width(font_rond, s)) // 2
        y = TOP_Y + i * (ROW_H + ROW_GAP) + font_petit.HEIGHT + LABEL_GAP
        self.clear_band(y, font_rond.HEIGHT)
        lcd.font_text(font_rond, s, x, y, WHITE, BLACK)

    def set_status(self, msg):
        if msg == self.status:
            return
        self.status = msg
        self.clear_band(STATUS_Y, 8)
        if msg:
            self.lcd.text_center(msg, STATUS_Y, RED, BLACK)

    def set_tempo(self, color):
        # Anneau au bord du cadran ; noir tant que la couleur est inconnue
        if color == self.tempo:
            return
        self.tempo = color
        self.lcd.fill_ring(120, 120, 119, RING_R_IN, RING_COLORS.get(color, BLACK))

    def set_hours(self, off_peak):
        # Anneau intérieur : vert en heures creuses, orange en heures pleines
        if off_peak == self.off_peak:
            return
        self.off_peak = off_peak
        self.lcd.fill_ring(120, 120, HOURS_R_OUT, HOURS_R_IN, GREEN if off_peak else ORANGE)


def main():
    lcd = board.init_display(ROTATION)
    lcd.fill(BLACK)
    scr = Screen(lcd)
    # Test de l'anneau au démarrage : chaque couleur Tempo pendant 1 s
    for c in (tempo.BLUE, tempo.WHITE, tempo.RED):
        scr.set_tempo(c)
        time.sleep(1)
    scr.set_tempo(None)
    scr.draw_labels()
    for i in range(len(SENSORS)):
        scr.set_temperature(i, None)
    if not secrets.WIFI_SSID:
        scr.set_status("Wi-Fi a configurer")
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
            scr.set_hours(tempo.off_peak(now_s))
            h = tempo.local_hour(now_s)
            light = BACKLIGHT_NIGHT if h >= NIGHT_START_H or h < NIGHT_END_H else BACKLIGHT_DAY
            if light != backlight:
                backlight = light
                board.set_backlight(light)
        if not online:
            scr.set_status("Wi-Fi injoignable")
        else:
            ok = True
            for i in range(len(SENSORS)):
                try:
                    scr.set_temperature(i, read_temperature(SENSORS[i][1]))
                except Exception as e:  # réseau ou réponse inattendue : on réessaie
                    print("Domoticz:", SENSORS[i][1], repr(e))
                    ok = False
            scr.set_status("" if ok else "Domoticz HS")
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
