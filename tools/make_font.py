# Convertit une police TrueType en module MicroPython (bitmaps lissés 4 bits).
# Tourne sur le PC (Pillow). Usage :
#   python tools\make_font.py [--ttf C:\Windows\Fonts\ARLRDBD.TTF] [--size 56]
#                             [--chars "0123456789.-°C"] [--out src\lib\font_rond.py]
#
# Format du module produit :
#   HEIGHT = hauteur commune de tous les glyphes (px)
#   GLYPHS = {caractère: (largeur, octets)} ; 4 bits par pixel (0 = fond,
#   15 = encre), poids fort d'abord, chaque ligne complétée à l'octet.
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ttf", default=r"C:\Windows\Fonts\ARLRDBD.TTF")
    p.add_argument("--size", type=int, default=56)
    p.add_argument("--chars", default="0123456789.-\u00b0C")
    p.add_argument("--out", default=os.path.join("src", "lib", "font_rond.py"))
    a = p.parse_args()

    font = ImageFont.truetype(a.ttf, a.size)
    # Bande verticale commune : de l'encre la plus haute à la plus basse
    boxes = [font.getbbox(c, anchor="ls") for c in a.chars]
    top = min(b[1] for b in boxes)
    bottom = max(b[3] for b in boxes)
    height = bottom - top

    lines = [
        "# Généré par tools/make_font.py depuis {} ({} px). Ne pas éditer.".format(
            os.path.basename(a.ttf), a.size),
        "HEIGHT = {}".format(height),
        "GLYPHS = {",
    ]
    total = 0
    for c in a.chars:
        width = math.ceil(font.getlength(c))
        img = Image.new("L", (width, height), 0)
        ImageDraw.Draw(img).text((0, -top), c, font=font, fill=255, anchor="ls")
        px = img.load()
        data = bytearray()
        for y in range(height):
            for x in range(0, width, 2):
                hi = px[x, y] >> 4
                lo = px[x + 1, y] >> 4 if x + 1 < width else 0
                data.append((hi << 4) | lo)
        total += len(data)
        lines.append("    {!r}: ({}, {!r}),".format(c, width, bytes(data)))
    lines.append("}")

    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("{} : hauteur {} px, {} glyphes, {} octets".format(
        a.out, height, len(a.chars), total))
    for c in a.chars:
        print("  {!r} largeur {}".format(c, math.ceil(font.getlength(c))))


main()
