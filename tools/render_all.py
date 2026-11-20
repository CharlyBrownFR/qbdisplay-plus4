#!/usr/bin/env python3
# qbdisplay – alle Seiten mit Beispieldaten über den Simulator rendern
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Schreibt display/preview/*.png und zeigt je Seite Befehlszahl, Bytes und
die geschätzte Übertragungszeit bei 115200 und 921600 Baud.

    python tools/render_all.py [--only 03] [--en] [--lang en]

``--en`` rendert alle Szenarien zusätzlich auf Englisch nach preview/en/,
``--lang en`` nur Englisch. Texte, die die Oberfläche mit '...' kürzen musste,
werden je Szenario aufgelistet (Dateinamen sind erwartbar lang).
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from qbdisplay import fonts, i18n  # noqa: E402
from qbdisplay.sim import Simulator  # noqa: E402
import scenarios  # noqa: E402

OUT = os.path.join(ROOT, 'preview')

_truncated = []
_orig_ellipsize = fonts.ellipsize


def _ellipsize_logged(text, fid, max_width):
    out = _orig_ellipsize(text, fid, max_width)
    if out != fonts.sanitize(text):
        _truncated.append((fonts.sanitize(text), out))
    return out


def render(lang, only, missing):
    out_dir = OUT if lang == 'de' else os.path.join(OUT, lang)
    os.makedirs(out_dir, exist_ok=True)
    print('== Sprache %s -> %s' % (lang, os.path.relpath(out_dir, ROOT)))
    total = 0
    for name, fn in scenarios.SCENARIOS:
        if only and not name.startswith(only):
            continue
        sim = Simulator()
        app = scenarios.make_app(sim)
        app.set_language(lang, persist=False)
        app.canvas.missing_icon_cb = missing.add
        fn(app)
        sim.reset_stats()
        del _truncated[:]
        app.render()
        sim.save(os.path.join(out_dir, name + '.png'))
        print('%-32s %4d Befehle %6d Bytes  %.2f s @115200  %.2f s @921600' % (
            name, sim.commands, sim.bytes, sim.transfer_seconds(115200),
            sim.transfer_seconds(921600)))
        seen = set()
        for full, short in _truncated:
            if full in seen:
                continue
            seen.add(full)
            total += 1
            print('   gekürzt: %r -> %r' % (full, short))
        if sim.unknown:
            print('   unbekannte Befehle:', sim.unknown[:3])
        if sim.missing_pics:
            print('   fehlende Bilder:', sorted(sim.missing_pics))
    print('== %s: %d gekürzte Texte' % (lang, total))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', help='nur Szenarien, deren Name so beginnt')
    ap.add_argument('--en', action='store_true',
                    help='zusätzlich englische Vorschauen nach preview/en/')
    ap.add_argument('--lang', choices=[c for c, _n in i18n.LANGUAGES],
                    help='nur diese Sprache rendern (Vorgabe: de)')
    args = ap.parse_args()
    langs = [args.lang] if args.lang else ['de'] + (['en'] if args.en else [])
    fonts.ellipsize = _ellipsize_logged
    missing = set()
    try:
        for lang in langs:
            render(lang, args.only, missing)
    finally:
        fonts.ellipsize = _orig_ellipsize
        i18n.set_language(i18n.DEFAULT)
    if missing:
        print('FEHLENDE ICONS (tools/make_icons.py ausführen):', sorted(missing))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
