#!/usr/bin/env python3
# qbdisplay – Icon-Liste pflegen und PNGs für den TJC-Editor erzeugen
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""1. Zeichnet alle Beispielseiten (auch mit jedem Ziel "gedrückt") und
   sammelt, welche Icon-Kombinationen (Name, Größe, Farbe, Hintergrund) die
   Oberfläche braucht.
2. Hängt neue Kombinationen HINTEN an qbdisplay/icons_manifest.py an
   (vorhandene Bild-IDs bleiben gleich).
3. Rendert alle Einträge nach tjc-projekt/icons/NNN_....png.

    python tools/make_icons.py            # sammeln + rendern
    python tools/make_icons.py --rebuild  # Liste neu sortiert aufbauen (IDs ändern sich!)
"""

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from qbdisplay import colors, icons  # noqa: E402
from qbdisplay.canvas import ListSink  # noqa: E402
import scenarios  # noqa: E402
from icon_svg import ICONS, render_icon  # noqa: E402

MANIFEST_PY = os.path.join(ROOT, 'qbdisplay', 'icons_manifest.py')
ICON_DIR = os.path.join(ROOT, 'tjc-projekt', 'icons')

HEADER = '''# qbdisplay – Icon-Liste der TJC-Datei (ERZEUGT von tools/make_icons.py)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Bild-ID = Position in MANIFEST. Neue Einträge nur hinten anhängen!"""

MANIFEST = [
'''


def collect():
    needed = []

    def cb(key):
        if key not in needed:
            needed.append(key)
    for name, fn in scenarios.SCENARIOS:
        sink = ListSink()
        app = scenarios.make_app(sink)
        app.canvas.missing_icon_cb = cb
        fn(app)
        app.render()
        # jedes Ziel einmal "gedrückt" zeichnen (andere Hintergründe)
        for t in list(app.frame.targets):
            app.pressed = t.tid
            app.mark_dirty()
            app.render()
        app.pressed = None
    return needed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rebuild', action='store_true')
    args = ap.parse_args()
    existing = [] if args.rebuild else [tuple(e) for e in icons.MANIFEST]
    icons.set_manifest(existing)
    needed = collect()
    for key in needed:
        if key[0] not in ICONS:
            raise SystemExit('Icon %r hat keine Vorlage in icon_svg.py' % (key[0],))
    entries = list(existing)
    for key in (sorted(needed) if args.rebuild else needed):
        if key not in entries:
            entries.append(key)
    with open(MANIFEST_PY, 'w', encoding='utf-8', newline='\n') as f:
        f.write(HEADER)
        for pid, (name, size, fg, bg) in enumerate(entries):
            f.write('    (%r, %d, %r, %r),  # %d\n' % (name, size, fg, bg, pid))
        f.write(']\n')
    icons.set_manifest(entries)
    if os.path.isdir(ICON_DIR):
        for fn in os.listdir(ICON_DIR):
            if fn.endswith('.png'):
                os.remove(os.path.join(ICON_DIR, fn))
    else:
        os.makedirs(ICON_DIR)
    for pid, (name, size, fg, bg) in enumerate(entries):
        img = render_icon(name, size, colors.hex_to_rgb(colors.resolve(fg)),
                          colors.hex_to_rgb(colors.resolve(bg)))
        img.save(os.path.join(ICON_DIR, icons.filename(pid)))
    print('%d Icons (%d neu) -> %s' % (len(entries), len(entries) - len(existing), ICON_DIR))


if __name__ == '__main__':
    main()
