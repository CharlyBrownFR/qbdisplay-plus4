# qbdisplay – Schriften (Font-IDs der TJC-Datei) und Textmessung
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Font-Tabelle.

Die TJC-Datei enthält die Schriften als vorgerenderte Bitmaps. Die Reihenfolge
beim Import im TJC-Editor bestimmt die Font-ID – sie muss exakt dieser Tabelle
entsprechen (siehe tjc-projekt/ANLEITUNG.md).

``height`` ist die Zeichenhöhe im TJC-Fontgenerator (Zellhöhe). Bei Barlow
entspricht das etwa ``height / 1,2`` px Schriftgröße im Sinne von CSS.

Breiten stammen aus ``fontmetrics.py`` (erzeugt von tools/make_fontmetrics.py
aus denselben TTF-Dateien). Damit kann der Host Texte vor dem Senden kürzen
("…") und umbrechen, ohne das Display zu fragen.
"""

from collections import namedtuple

FontSpec = namedtuple('FontSpec', 'fid height ttf role charset')

# Zeichensatz-Kürzel für die Anleitung
CHARSET_FULL = 'iso-8859-1 (komplett)'
CHARSET_DIGITS = '0123456789 .,:-/%°Ch'

FONTS = [
    FontSpec(0, 16, 'Barlow-Medium.ttf', 'Nebeninfo, Navigation (≈14 px)', CHARSET_FULL),
    FontSpec(1, 18, 'Barlow-SemiBold.ttf', 'Labels, Statusleiste, Chips (≈15 px)', CHARSET_FULL),
    FontSpec(2, 20, 'Barlow-Medium.ttf', 'Fließtext, Anweisungen (≈17 px)', CHARSET_FULL),
    FontSpec(3, 24, 'Barlow-Bold.ttf', 'Buttons, Kartentitel (≈20 px)', CHARSET_FULL),
    FontSpec(4, 32, 'BarlowSemiCondensed-Bold.ttf', 'Werte, Dateiname (≈26 px)', CHARSET_FULL),
    FontSpec(5, 40, 'BarlowSemiCondensed-Bold.ttf', 'große Werte, IP, Restzeit (≈33 px)', CHARSET_FULL),
    FontSpec(6, 64, 'BarlowSemiCondensed-Bold.ttf', 'Messwerte (≈54 px), nur Ziffern', CHARSET_DIGITS),
    FontSpec(7, 28, 'Barlow-Bold.ttf', 'Dialog-/Kartentitel (≈23 px)', CHARSET_FULL),
]

# Zusätzlicher Zeichenabstand in Pixeln, in die Vorschubbreite der Glyphen eingebaut
# (tools/build_tjc_project.py) und in fontmetrics.py enthalten. Am Display wirkte Barlow
# ohne Zugabe zu gedrängt (Test am Plus4, 2026-11-20).
TRACKING = {0: 0, 1: 1, 2: 1, 3: 0, 4: 1, 5: 1, 6: 2, 7: 1}   # 0/3: Navigation und Slotnamen passen sonst nicht

CAP, LBL, TEXT, BTN, VAL, BIG, HUGE, TITLE = range(8)

try:
    from . import fontmetrics as _fm
    _WIDTHS = _fm.WIDTHS
except ImportError:   # pragma: no cover - nur bevor die Metriken erzeugt wurden
    _WIDTHS = {}

_monospace = False


def set_monospace(flag):
    """True, falls die TJC-Schriften festbreit erzeugt wurden (ASCII = halbe Höhe)."""
    global _monospace
    _monospace = bool(flag)


def height(fid):
    return FONTS[fid].height


# Zeichen außerhalb von ISO-8859-1 durch darstellbare ersetzen
_REPLACE = {
    '–': '-', '—': '-', '−': '-', '…': '...',
    '→': '>', '←': '<', '„': '»', '“': '«',
    '”': '«', '"': "'", '\\': '/', ' ': ' ', ' ': ' ',
    '℃': '°C', '✕': 'x', '✓': 'v',
    '›': '>', '‹': '<', '’': "'", '‘': "'", '‚': ',',
}


def sanitize(text):
    """Text in den Zeichensatz der TJC-Fonts bringen (ISO-8859-1, ohne '"')."""
    out = []
    for ch in str(text):
        ch = _REPLACE.get(ch, ch)
        out.append(ch if all(ord(c) < 256 for c in ch) else '?')
    return ''.join(out)


def char_width(ch, fid):
    h = FONTS[fid].height
    o = ord(ch)
    if _monospace:
        return h // 2
    widths = _WIDTHS.get(fid)
    if widths and 32 <= o < 256:
        return widths[o - 32]
    return int(h * 0.5)


def measure(text, fid):
    """Breite in Pixeln (sanitisierter Text)."""
    return sum(char_width(ch, fid) for ch in sanitize(text))


def ellipsize(text, fid, max_width):
    """Kürzt auf max_width und hängt '...' an (nie hart abschneiden)."""
    text = sanitize(text)
    if measure(text, fid) <= max_width:
        return text
    dots = '...'
    budget = max_width - measure(dots, fid)
    out = ''
    for ch in text:
        if measure(out + ch, fid) > budget:
            break
        out += ch
    return out.rstrip() + dots


def wrap(text, fid, max_width, max_lines=None):
    """Wortumbruch. Liefert Liste von Zeilen; letzte ggf. mit '...'."""
    words = sanitize(text).split()
    lines, cur = [], ''
    for w in words:
        trial = (cur + ' ' + w) if cur else w
        if measure(trial, fid) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w if measure(w, fid) <= max_width else ellipsize(w, fid, max_width)
    if cur:
        lines.append(cur)
    if max_lines is not None and len(lines) > max_lines:
        rest = ' '.join(lines[max_lines - 1:])
        lines = lines[:max_lines - 1] + [ellipsize(rest, fid, max_width)]
    return lines
