# qbdisplay – Simulator: führt TJC-Befehle mit Pillow aus
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Simulator für die PC-Vorschau (braucht Pillow, läuft NICHT auf dem Drucker).

Er bekommt exakt die Befehle, die auch an das Display gehen, und zeichnet
sie in ein 800 × 480-Bild. Farben werden über RGB565 zurückgerechnet, damit
man auch die Farbstufen des Displays sieht. Schriften: dieselben TTF-Dateien
wie im TJC-Fontgenerator (tjc-projekt/fonts), Größe so gewählt, dass die
Zellhöhe der TJC-Font-Höhe entspricht.
"""

import os

from PIL import Image, ImageDraw, ImageFont

from . import colors
from . import fonts
from . import icons

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT_DIR = os.path.normpath(os.path.join(HERE, '..', 'tjc-projekt', 'fonts'))
DEFAULT_ICON_DIR = os.path.normpath(os.path.join(HERE, '..', 'tjc-projekt', 'icons'))
FALLBACK_FONTS = ('bahnschrift.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf')

_font_cache = {}


def load_pil_font(spec, font_dir=None):
    """PIL-Schrift für eine FontSpec: Zellhöhe (ascent+descent) = spec.height."""
    font_dir = font_dir or DEFAULT_FONT_DIR
    key = (spec.fid, font_dir)
    if key in _font_cache:
        return _font_cache[key]
    path = os.path.join(font_dir, spec.ttf)
    cands = [path] + list(FALLBACK_FONTS)
    font = None
    for cand in cands:
        try:
            probe = ImageFont.truetype(cand, 100)
            a, d = probe.getmetrics()
            # größte Größe, deren Zelle (ascent+descent) in spec.height passt – genau so
            # rastert tools/build_tjc_project.py die Schriften für das Display
            size = max(4, int(round(100.0 * spec.height / float(a + d))) + 1)
            font = ImageFont.truetype(cand, size)
            while size > 4 and sum(font.getmetrics()) > spec.height:
                size -= 1
                font = ImageFont.truetype(cand, size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def _split_args(rest, n):
    parts = rest.split(',', n - 1)
    return parts


class Simulator(object):
    """Senke für :class:`qbdisplay.canvas.Canvas` – rendert in ein PIL-Bild."""

    def __init__(self, font_dir=None, icon_dir=None, width=800, height=480):
        self.font_dir = font_dir or DEFAULT_FONT_DIR
        self.icon_dir = icon_dir or DEFAULT_ICON_DIR
        self.img = Image.new('RGB', (width, height), (0, 0, 0))
        self.draw = ImageDraw.Draw(self.img)
        self.commands = 0
        self.bytes = 0
        self.unknown = []
        self.missing_pics = set()
        self._pics = {}

    # Statistik: geschätzte Übertragungszeit bei gegebener Baudrate
    def transfer_seconds(self, baud=115200):
        return self.bytes * 10.0 / baud

    def reset_stats(self):
        self.commands = 0
        self.bytes = 0

    def save(self, path):
        self.img.save(path)

    def send(self, cmd):
        self.commands += 1
        self.bytes += len(cmd.encode('latin-1', 'replace')) + 3
        self.execute(cmd)

    # -- Ausführung --------------------------------------------------------
    def execute(self, cmd):
        name, _, rest = cmd.partition(' ')
        fn = getattr(self, '_cmd_' + name, None)
        if fn is None:
            if '=' in name or name in ('page', 'ref_stop', 'ref_star', 'sendme', 'sleep', 'dim'):
                return    # Systembefehle/Zuweisungen: im Simulator ohne Wirkung
            self.unknown.append(cmd)
            return
        fn(rest)

    @staticmethod
    def _rgb(v):
        return colors.rgb565_to_rgb(int(v))

    def _cmd_cls(self, rest):
        self.draw.rectangle([0, 0, self.img.width, self.img.height], fill=self._rgb(rest))

    def _cmd_fill(self, rest):
        x, y, w, h, c = [int(v) for v in rest.split(',')]
        if w > 0 and h > 0:
            self.draw.rectangle([x, y, x + w - 1, y + h - 1], fill=self._rgb(c))

    def _cmd_draw(self, rest):
        x0, y0, x1, y1, c = [int(v) for v in rest.split(',')]
        self.draw.rectangle([x0, y0, x1, y1], outline=self._rgb(c))

    def _cmd_line(self, rest):
        x0, y0, x1, y1, c = [int(v) for v in rest.split(',')]
        self.draw.line([x0, y0, x1, y1], fill=self._rgb(c))

    def _cmd_cirs(self, rest):
        x, y, r, c = [int(v) for v in rest.split(',')]
        self.draw.ellipse([x - r, y - r, x + r, y + r], fill=self._rgb(c))

    def _cmd_cir(self, rest):
        x, y, r, c = [int(v) for v in rest.split(',')]
        self.draw.ellipse([x - r, y - r, x + r, y + r], outline=self._rgb(c))

    def _pic(self, pid):
        if pid in self._pics:
            return self._pics[pid]
        img = None
        if 0 <= pid < len(icons.MANIFEST):
            path = os.path.join(self.icon_dir, icons.filename(pid))
            if os.path.exists(path):
                # wie das Display: auf RGB565 reduzieren
                img = Image.open(path).convert('RGB')
                lut5 = [((v >> 3) << 3) | (v >> 5) for v in range(256)]
                lut6 = [((v >> 2) << 2) | (v >> 6) for v in range(256)]
                img = img.point(lut5 + lut6 + lut5)
        if img is None:
            self.missing_pics.add(pid)
        self._pics[pid] = img
        return img

    def _cmd_pic(self, rest):
        x, y, pid = [int(v) for v in rest.split(',')]
        img = self._pic(pid)
        if img is None:
            # sichtbarer Platzhalter
            self.draw.rectangle([x, y, x + 15, y + 15], outline=(255, 0, 255))
            return
        self.img.paste(img, (x, y))

    def _cmd_xpic(self, rest):
        x, y, w, h, x0, y0, pid = [int(v) for v in rest.split(',')]
        img = self._pic(pid)
        if img is not None:
            self.img.paste(img.crop((x0, y0, x0 + w, y0 + h)), (x, y))

    def _cmd_xstr(self, rest):
        parts = _split_args(rest, 11)
        x, y, w, h, fid, pco, bco, xcen, ycen, sta = [int(v) for v in parts[:10]]
        text = parts[10].strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if sta == 1:
            self.draw.rectangle([x, y, x + w - 1, y + h - 1], fill=self._rgb(bco))
        spec = fonts.FONTS[fid]
        font = load_pil_font(spec, self.font_dir)
        tw = fonts.measure(text, fid)
        if xcen == 0:
            tx = x
        elif xcen == 1:
            tx = x + (w - tw) // 2
        else:
            tx = x + w - tw
        if ycen == 0:
            ty = y
        elif ycen == 1:
            ty = y + (h - spec.height) // 2
        else:
            ty = y + h - spec.height
        # Text in eigenes Bild, dann auf die Box zuschneiden (TJC schneidet ab)
        layer = Image.new('RGB', (w, h), self._rgb(bco))
        d = ImageDraw.Draw(layer)
        ascent = font.getmetrics()[0] if hasattr(font, 'getmetrics') else spec.height
        cx = tx - x
        for ch in text:
            d.text((cx, ty - y + ascent), ch, font=font, fill=self._rgb(pco), anchor='ls')
            cx += fonts.char_width(ch, fid)
        if sta == 1:
            self.img.paste(layer, (x, y))
        else:
            # ohne Hintergrund: nur Textpixel übernehmen
            mask = Image.new('L', (w, h), 0)
            ImageDraw.Draw(mask)
            md = ImageDraw.Draw(mask)
            cx = tx - x
            for ch in text:
                md.text((cx, ty - y + ascent), ch, font=font, fill=255, anchor='ls')
                cx += fonts.char_width(ch, fid)
            self.img.paste(Image.new('RGB', (w, h), self._rgb(pco)), (x, y), mask)
