# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Contexte

Projet **MicroPython** (pas CPython) pour le module ESP32-2424S012 : ESP32-C3 + écran rond GC9A01 240x240 (SPI) + tactile CST816D (I2C). Tout ce qui est dans `src/` tourne sur la carte ; seuls `mpremote` et `esptool` (`requirements.txt`) tournent sur le PC. Le brochage complet est dans `src/board.py` et le README. L'utilisateur est francophone : commentaires et textes en français.

## Commandes

```powershell
.venv\Scripts\Activate.ps1
.\tools\deploy.ps1 [-Port COM5]   # copie src/ à la racine de la carte (lib/ -> :lib) puis reset
mpremote run src\main.py          # exécute main.py sans le copier
mpremote repl
python -m py_compile src\board.py src\main.py src\lib\gc9a01.py src\lib\cst816.py src\lib\font_rond.py src\tempo.py   # seule vérif possible sans carte
python tools\make_font.py --size 48                  # régénère src\lib\font_rond.py (Pillow)
python tools\make_font.py --size 22 --chars "OutsideT °CIn" --out src\lib\font_petit.py
```

Il n'y a pas de tests automatisés : la validation se fait sur la carte.

## Architecture

- `src/lib/` est copié dans `/lib` sur la carte, qui fait partie du `sys.path` de MicroPython : on y importe `gc9a01` et `cst816` directement (pas de package).
- `board.py` est le seul endroit qui connaît les numéros de GPIO ; il construit les objets matériels (`init_display`, `init_touch`, `set_backlight`, `boot_button`). Le code applicatif passe par lui.
- `gc9a01.py` n'utilise **pas** de framebuffer plein écran (240x240x2 = 115 Ko, trop pour le tas de l'ESP32-C3). Chaque primitive ouvre une fenêtre (CASET/RASET/RAMWR) et envoie les pixels en flux via un tampon de 512 octets. Les couleurs sont en RGB565 et envoyées en big-endian. Le texte utilise la police 8x8 de `framebuf`, en ASCII seulement (pas d'accents à l'écran), et lève `ValueError` s'il dépasse l'écran. Pour les gros chiffres, `font_text`/`font_width` affichent une police lissée 4 bits (`font_rond.py`, Arial Rounded MT Bold 48 px, glyphes `0-9 . - ° C` seulement) et `font_petit.py` (22 px, lettres de « Outside T°C » et « Inside T°C » seulement), générées par `tools/make_font.py` : ne pas les éditer à la main, et ajouter les caractères manquants via `--chars`.
- `main.py` affiche toutes les 60 s les températures extérieure (idx 66) et intérieure (idx 83) de Domoticz (`DOMOTICZ_URL`, `SENSORS`) via `requests`, sur deux lignes libellé + valeur (48 px est la plus grande taille qui fait tenir les deux lignes dans l'anneau intérieur), après connexion Wi-Fi avec `secrets.py` (exclu de git, modèle dans `secrets_example.py`). L'heure vient de NTP (RTC en UTC) ; `deploy.ps1` ne règle plus le RTC.
- Carte de test : COM5, MicroPython v1.29.0 (`firmware/` est ignoré par git). Si `main.py` tourne, mpremote l'interrompt tout seul à la connexion.
- `tempo.py` lit la couleur du jour Tempo sur l'API RTE « Tempo Like Supply Contract » (même méthode que le projet GitHub Bosoochee/EDF-Tempo) : jeton OAuth avec `secrets.RTE_ID_BASE64`, puis calendrier en JSON (`BLUE`/`WHITE`/`RED`). Le jour Tempo va de 6 h à 6 h, en heure française calculée à la main (pas de fuseaux en MicroPython). `sync_clock()` règle le RTC en **UTC** via NTP. Le HTTPS ne vérifie pas le certificat (comportement par défaut de `requests` en MicroPython). Le fond est toujours noir, le texte blanc. `main.py` dessine la couleur Tempo en anneau au bord du cadran (rayons 111-119) et, juste à l'intérieur, un second anneau (rayons 104-109) vert en heures creuses (22 h - 6 h, `tempo.off_peak`) et orange en heures pleines, noir tant que NTP n'a pas réglé l'heure. `fill_ring` prend environ 1 s, donc la classe `Screen` ne redessine un anneau que quand sa couleur change ; `clear_band` efface le texte sans déborder sur `HOURS_R_IN` (103, juste assez pour « -10.5°C »). Le rétroéclairage passe à `BACKLIGHT_NIGHT` (20 %) de 22 h à 7 h.
- `main.py` affiche en rotation 0 (`ROTATION`). Toutes les requêtes HTTP ont un `timeout` (10 s Domoticz, 15 s RTE) : sans lui, un serveur muet bloque la boucle indéfiniment.
- L'écran est rond : les coins du carré 240x240 ne sont pas visibles, donc le contenu utile est à garder dans le cercle de rayon 120.
- `cst816.py` désactive la mise en veille automatique (registre 0xFE), sinon la puce cesse de répondre en I2C. `read()` avale les `OSError` et renvoie `None`. Les coordonnées tactiles ne correspondent à l'écran qu'en rotation 0.

## Contraintes MicroPython

- ESP32-C3 : un seul bus SPI matériel utilisable, `SPI(1, ...)` ; I2C en `I2C(0, ...)`.
- Utiliser `micropython.const`, `time.sleep_ms` et les API `machine`. Pas de f-strings complexes, de dataclasses ni de typing.
- Mémoire limitée : éviter les grosses allocations dans les boucles et réutiliser les tampons.

## Non vérifié sur le matériel

Vérifié sur la carte : l'écran, le rétroéclairage et le vert s'affichent. L'orientation a été corrigée à l'œil sur la carte : `_ROTATIONS[0] = 0x08` (BGR seul, ni MX ni MY) dans `gc9a01.py`, au lieu du 0x48 habituel des autres pilotes GC9A01. 0x48 et 0x88 donnent tous deux un texte retourné ou en miroir.

Le code a été écrit sans carte branchée. À confirmer : l'ordre RGB/BGR sur d'autres couleurs que le vert, l'inversion (`0x21` INVON dans `_INIT`), la polarité du rétroéclairage sur GPIO3, le sens haut/bas des gestes CST816, et si les coordonnées tactiles suivent la nouvelle rotation 0.
