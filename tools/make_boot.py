#!/usr/bin/env python3
# qbdisplay – Startbild der TJC-Datei (Hintergrund von page0)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Zeichnet ``tjc-projekt/boot.png`` (800×480). Das Display zeigt es sofort nach dem
Einschalten, bis qbdisplay die Oberfläche zeichnet (Linux-Start, ca. 30–60 s).

    python tools/make_boot.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

FONTS = os.path.join(ROOT, 'tjc-projekt', 'fonts')
OUT = os.path.join(ROOT, 'tjc-projekt', 'boot.png')
S = 4  # Überabtastung


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font(name, px):
    return ImageFont.truetype(os.path.join(FONTS, name), px * S)


def main():
    bg, surface, line = rgb('#0D1117'), rgb('#111821'), rgb('#1F2A39')
    text, text3, accent = rgb('#F3F6FA'), rgb('#7D8A9C'), rgb('#22D3EE')
    spools = [rgb('#E8A33A'), rgb('#F3F6FA'), rgb('#22D3EE'), rgb('#A08CFF')]
    W, H = 800 * S, 480 * S
    im = Image.new('RGB', (W, H), bg)

    def box(x0, y0, x1, y1):
        return [v * S for v in (x0, y0, x1, y1)]

    # Lichthof hinter der Karte
    glow = Image.new('RGB', (W, H), bg)
    ImageDraw.Draw(glow).rounded_rectangle(box(236, 64, 564, 296), radius=28 * S, fill=(10, 70, 84))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(26 * S)), 0.9)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(box(240, 68, 560, 292), radius=20 * S, fill=surface, outline=accent, width=2 * S)

    # Drucker als Linienzeichnung
    fx0, fy0, fx1, fy1 = 300, 96, 500, 268
    d.rounded_rectangle(box(fx0, fy0, fx1, fy1), radius=10 * S, outline=text3, width=int(2.5 * S))
    d.line(box(fx0, fy0 + 24, fx1, fy0 + 24), fill=line, width=2 * S)
    d.line(box(fx0 + 14, fy0 + 56, fx1 - 14, fy0 + 56), fill=text3, width=3 * S)
    hx = 378
    d.rounded_rectangle(box(hx - 18, fy0 + 44, hx + 18, fy0 + 76), radius=6 * S, fill=line,
                        outline=accent, width=2 * S)
    d.polygon([(v * S) for v in (hx - 6, fy0 + 76, hx + 6, fy0 + 76, hx, fy0 + 87)], fill=accent)
    by = fy1 - 30
    d.line(box(fx0 + 22, by, fx1 - 22, by), fill=text3, width=3 * S)
    # Druckteil aus vier Farbschichten, oberste halb fertig unter der Düse
    for i, col in enumerate(spools):
        y1 = by - 3 - i * 11
        w = 70 if i < 3 else 34
        d.rounded_rectangle(box(344, y1 - 9, 344 + w, y1), radius=3 * S, fill=col)

    # Schrift
    f1, f2, f3 = font('Barlow-Bold.ttf', 46), font('Barlow-SemiBold.ttf', 18), font('Barlow-Medium.ttf', 15)

    def center(y, txt, f, fill, spacing=0):
        if spacing:
            ws = [d.textlength(ch, font=f) for ch in txt]
            x = (W - sum(ws) - spacing * S * (len(txt) - 1)) / 2
            for ch, w in zip(txt, ws):
                d.text((x, y * S), ch, font=f, fill=fill)
                x += w + spacing * S
        else:
            d.text(((W - d.textlength(txt, font=f)) / 2, y * S), txt, font=f, fill=fill)

    center(316, 'PLUS4', f1, text, spacing=6)
    center(378, 'QIDI BOX  ·  4 SLOTS', f2, accent, spacing=2)
    # Spulen-Punkte wie in der Slot-Übersicht
    for i, col in enumerate(spools):
        cx, cy = 370 + i * 20, 418
        d.ellipse(box(cx - 6, cy - 6, cx + 6, cy + 6), fill=col)
        d.ellipse(box(cx - 2, cy - 2, cx + 2, cy + 2), fill=bg)
    center(444, 'STARTET …'.replace('…', '...'), f3, text3, spacing=2)
    im.resize((800, 480), Image.LANCZOS).save(OUT)
    print('geschrieben:', OUT)


if __name__ == '__main__':
    main()
