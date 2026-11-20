#!/usr/bin/env python3
# qbdisplay – erzeugt qbdisplay/fontmetrics.py aus den TTF-Dateien
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Zeichenbreiten (ISO-8859-1, Zeichen 32..255) je Font-ID berechnen.

Läuft am PC (Pillow). Nach einem Wechsel der Schriftdatei oder der Höhen in
qbdisplay/fonts.py erneut ausführen:

    python tools/make_fontmetrics.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from qbdisplay import fonts  # noqa: E402
from qbdisplay.sim import load_pil_font  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'qbdisplay', 'fontmetrics.py')

HEADER = '''# qbdisplay – Zeichenbreiten der TJC-Schriften (ERZEUGT, nicht von Hand ändern)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Erzeugt von tools/make_fontmetrics.py. WIDTHS[font_id][ord(c) - 32]."""

WIDTHS = {
'''


def main():
    lines = [HEADER]
    for spec in fonts.FONTS:
        font = load_pil_font(spec)
        widths = []
        for code in range(32, 256):
            ch = chr(code)
            try:
                w = int(round(font.getlength(ch))) + fonts.TRACKING.get(spec.fid, 0)
            except Exception:
                w = spec.height // 2
            widths.append(max(0, w))
        lines.append('    %d: [  # %s, Höhe %d\n' % (spec.fid, spec.ttf, spec.height))
        for i in range(0, len(widths), 16):
            lines.append('        ' + ', '.join('%d' % w for w in widths[i:i + 16]) + ',\n')
        lines.append('    ],\n')
    lines.append('}\n')
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(''.join(lines))
    print('geschrieben:', OUT)


if __name__ == '__main__':
    main()
