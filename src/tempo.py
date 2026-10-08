# Couleur du jour Tempo d'EDF, lue sur l'API "Tempo Like Supply Contract" de RTE
# (même méthode que le projet EDF-Tempo : jeton OAuth, puis calendrier J..J+2).
# L'heure vient de NTP : après sync_clock(), le RTC est en UTC.
import time

import ntptime
import requests

import secrets

_TOKEN_URL = "https://digital.iservices.rte-france.com/token/oauth/"
_CAL_URL = ("https://digital.iservices.rte-france.com/open_api/"
            "tempo_like_supply_contract/v1/tempo_like_calendars")

# Valeurs renvoyées par l'API
BLUE = "BLUE"
WHITE = "WHITE"
RED = "RED"

_DAY = 86400
_TIMEOUT_S = 15  # délai maximal par requête HTTPS


def sync_clock():
    ntptime.settime()


def _last_sunday(year, month):
    # Dernier dimanche de mars ou d'octobre (31 jours) à 01:00 UTC
    t = time.mktime((year, month, 31, 1, 0, 0, 0, 0))
    return t - ((time.localtime(t)[6] + 1) % 7) * _DAY


def utc_offset_h(t):
    """Décalage de l'heure française (1 l'hiver, 2 l'été) à l'instant UTC t."""
    y = time.localtime(t)[0]
    return 2 if _last_sunday(y, 3) <= t < _last_sunday(y, 10) else 1


def tempo_day(t):
    """Date (a, m, j) du jour Tempo en cours : il va de 6 h à 6 h le lendemain."""
    return time.localtime(t + (utc_offset_h(t) - 6) * 3600)[:3]


def local_hour(t):
    """Heure française (0-23) à l'instant UTC t."""
    return time.localtime(t + utc_offset_h(t) * 3600)[3]


def off_peak(t):
    """Heures creuses Tempo : de 22 h à 6 h, heure française."""
    h = local_hour(t)
    return h >= 22 or h < 6


def _param(day):
    t = time.mktime(day + (12, 0, 0, 0, 0))
    return "{:04d}-{:02d}-{:02d}T00:00:00%2B0{}:00".format(
        day[0], day[1], day[2], utc_offset_h(t))


def _token():
    r = requests.post(_TOKEN_URL, headers={
        "Authorization": "Basic " + secrets.RTE_ID_BASE64,
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": "0",
    }, timeout=_TIMEOUT_S)
    try:
        if r.status_code != 200:
            raise OSError("RTE jeton HTTP {}".format(r.status_code))
        return r.json()["access_token"]
    finally:
        r.close()


def fetch_color(day):
    """Couleur (BLUE, WHITE, RED) du jour Tempo day, ou None si pas encore publiée."""
    end = time.localtime(time.mktime(day + (12, 0, 0, 0, 0)) + 2 * _DAY)[:3]
    url = "{}?start_date={}&end_date={}".format(_CAL_URL, _param(day), _param(end))
    r = requests.get(url, headers={"Authorization": "Bearer " + _token()}, timeout=_TIMEOUT_S)
    try:
        if r.status_code != 200:
            raise OSError("RTE calendrier HTTP {}".format(r.status_code))
        values = r.json()["tempo_like_calendars"]["values"]
    finally:
        r.close()
    key = "{:04d}-{:02d}-{:02d}".format(day[0], day[1], day[2])
    for v in values:
        if v["start_date"].startswith(key):
            return v["value"]
    return None
