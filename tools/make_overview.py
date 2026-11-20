# qbdisplay – Übersichtsbild aus mehreren Vorschauen
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
prev, out = sys.argv[1], sys.argv[2]
shots = [('BOOT', 'Startbild beim Einschalten'), ('02_start_druck_farbwechsel', 'Druck mit Farbwechsel'), ('03_filament_box', 'QIDI Box: 4 Slots'),
         ('09_trocknung_laeuft', 'Box-Trocknung'), ('04_slot_bearbeiten', 'Filament zuordnen'),
         ('05_bewegen', 'Bewegen'), ('10_dateien', 'Dateien'),
         ('12_filament_laedt', 'Filament lädt'), ('01_start_leerlauf', 'Start'), ('06_fehler_dialog', 'Fehler mit Lösung'), ('08_trocknung_auswahl', 'Trocknung einstellen'), ('17_system_box', 'Box-Einstellungen')]
W, H = 800, 480
BOOT = r'C:\kunden\qidi-box-re\display\tjc-projekt\boot.png'
cols, gap, pad, head = 3, 56, 90, 230
cw = cols * W + (cols - 1) * gap + 2 * pad
ch = head + 4 * (H + gap + 40) + pad - gap + 60
bg = (8, 11, 16)
img = Image.new('RGB', (cw, ch), bg)
glow = Image.new('RGB', (cw, ch), bg); gd = ImageDraw.Draw(glow)
d = ImageDraw.Draw(img)
F = lambda n, s: ImageFont.truetype(os.path.join(r'C:\kunden\qidi-box-re\display\tjc-projekt\fonts', n), s)
for i, (name, label) in enumerate(shots):
    x = pad + (i % cols) * (W + gap)
    y = head + (i // cols) * (H + gap + 40)
    gd.rounded_rectangle((x - 10, y - 10, x + W + 10, y + H + 10), radius=26, fill=(14, 70, 84))
glow = glow.filter(ImageFilter.GaussianBlur(22))
img = Image.blend(img, glow, 0.85); d = ImageDraw.Draw(img)
d.text((pad, 62), 'QIDI PLUS4', font=F('Barlow-Bold.ttf', 84), fill=(243, 245, 248))
tw = d.textlength('QIDI PLUS4', font=F('Barlow-Bold.ttf', 84))
d.text((pad + tw + 30, 84), 'EIGENE DISPLAY-OBERFLÄCHE', font=F('Barlow-SemiBold.ttf', 48), fill=(34, 211, 238))
d.text((pad, 160), 'Selbst gebaut für das Original-Display · QIDI-Firmware bleibt · Box-Steuerung und Trocknung direkt am Drucker',
       font=F('Barlow-Medium.ttf', 32), fill=(160, 172, 188))
for i, (name, label) in enumerate(shots):
    x = pad + (i % cols) * (W + gap)
    y = head + (i // cols) * (H + gap + 40)
    d.rounded_rectangle((x - 10, y - 10, x + W + 10, y + H + 10), radius=24, fill=(20, 24, 30), outline=(34, 211, 238), width=2)
    shot = Image.open(BOOT if name == 'BOOT' else os.path.join(prev, name + '.png')).convert('RGB')
    m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, W - 1, H - 1), radius=16, fill=255)
    img.paste(shot, (x, y), m)
    d.text((x + 4, y + H + 18), label.upper(), font=F('Barlow-SemiBold.ttf', 30), fill=(183, 192, 205))
img.convert('RGB').save(os.path.join(out, 'qbdisplay-uebersicht.jpg'), quality=92)
for name, label in shots:
    s = Image.open(BOOT if name == 'BOOT' else os.path.join(prev, name + '.png')).convert('RGB').resize((1600, 960), Image.LANCZOS)
    s.save(os.path.join(out, ('00_startbild' if name == 'BOOT' else name) + '.png'))
print(img.size)

