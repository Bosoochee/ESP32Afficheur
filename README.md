# ESP32Afficheur

Projet MicroPython pour le module **ESP32-2424S012** :

- ESP32-C3 (RISC-V, 4 Mo de flash, USB série/JTAG intégré)
- écran rond IPS 1,28" **GC9A01**, 240x240, RGB565, en SPI
- dalle tactile capacitive **CST816D**, en I2C (adresse 0x15)

## Brochage

| Fonction | GPIO |
|---|---|
| LCD SCK / MOSI | 6 / 7 |
| LCD CS / DC | 10 / 2 |
| Rétroéclairage (PWM) | 3 |
| Tactile SDA / SCL | 4 / 5 |
| Tactile INT / RST | 0 / 1 |
| Bouton BOOT | 9 |

## Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Flasher MicroPython (une seule fois)

Téléchargez le firmware **ESP32_GENERIC_C3** sur https://micropython.org/download/ESP32_GENERIC_C3/ et placez-le dans `firmware/`.

```powershell
esptool --chip esp32c3 erase-flash
esptool --chip esp32c3 --baud 460800 write-flash 0x0 firmware\ESP32_GENERIC_C3-xxxx.bin
```

Si la carte n'est pas détectée, maintenez BOOT en branchant le câble USB.

## Développement

```powershell
.\tools\deploy.ps1            # copie src/ sur la carte et redémarre
.\tools\deploy.ps1 -Port COM5 # port explicite
mpremote run src\main.py      # exécute sans copier (les libs doivent déjà être sur la carte)
mpremote repl                 # console (Ctrl-] pour quitter)
```

## Structure

- `src/lib/gc9a01.py` : pilote écran (sans framebuffer complet)
- `src/lib/cst816.py` : pilote tactile
- `src/lib/font_rond.py`, `src/lib/font_petit.py` : polices rondes lissées (chiffres et libellé), générées par `tools/make_font.py` (Pillow) depuis Arial Rounded MT Bold
- `src/board.py` : brochage et initialisation du matériel
- `src/tempo.py` : couleur du jour Tempo d'EDF via l'API RTE (identifiant en base 64 dans `secrets.py`, voir `secrets_example.py`)
- `src/main.py` : températures extérieure et intérieure lues sur Domoticz, fond noir, anneau extérieur à la couleur du jour Tempo, anneau intérieur vert en heures creuses et orange en heures pleines, luminosité réduite de 22 h à 7 h

Copiez `src/secrets_example.py` en `src/secrets.py` et renseignez le Wi-Fi et l'identifiant RTE. L'ESP32 n'a pas de pile : l'heure est réglée par NTP au démarrage.
