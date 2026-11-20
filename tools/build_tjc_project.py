# qbdisplay â€“ TJC-Projekt (.HMI) ohne Editor-Klickarbeit erzeugen
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Baut das Projekt aus tjc-projekt/ANLEITUNG.md automatisch: eine leere Seite ``page0``,
die Schriften aus ``qbdisplay.fonts.FONTS`` (aus den Barlow-TTFs gerastert) und alle Icons
aus ``tjc-projekt/icons`` in Dateinamen-Reihenfolge (= Bild-ID).

Gerätekopf und Speicher-Layouts übernimmt das Skript aus QIDIs Display-Projekt im
portablen Format (hmi-builder ``unpack --portable``), damit Modell, Ausrichtung und
Zeichenkodierung (UTF-8) zum Display im Plus4 passen. Diese Datei liegt nur lokal
(``printer-config/qidi-upstream/portable``) und wird nicht weitergegeben.

  python tools/build_tjc_project.py --qidi-portable DIR --hmi-builder TOOLS --out OUT.HMI

Danach im TJC-Editor: Datei -> Produktionsdatei ausgeben (.tft). qbdisplay braucht dann
``encoding: utf-8`` in ``[display]``.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from qbdisplay import colors, fonts  # noqa: E402

TJC = os.path.join(ROOT, 'tjc-projekt')


LATIN1 = ''.join(chr(c) for c in range(0x20, 0x100) if not 0x7f <= c < 0xa0 and c != 0xad)


def charset(spec, hmi_font=None):
    """Zeichen einer Schrift. ``fonts.CHARSET_FULL`` ist nur eine Beschreibung für den
    Fontgenerator des Editors (ISO-8859-1 komplett) und wird hier ausgeschrieben.
    Zeichen, die bei dieser Höhe nicht in die Zelle passen, lässt ``hmi_font`` weg."""
    chars = ''.join(sorted(set(LATIN1 if spec.charset == fonts.CHARSET_FULL else spec.charset)))
    if hmi_font is None:
        return chars
    from PIL import Image, ImageDraw, ImageFont
    font, _size = hmi_font._fit_size(os.path.join(TJC, 'fonts', spec.ttf), 0, spec.height, ImageFont)
    keep, dropped = [], []
    for ch in chars:
        try:
            hmi_font._rasterize_char(ch, font, spec.height, 3, Image, ImageDraw)
            keep.append(ch)
        except ValueError:
            dropped.append(ch)
    if dropped:
        print('Schrift %d (%d px): ohne %s' % (spec.fid, spec.height, ' '.join(dropped)))
    return ''.join(keep)


def encode_font(spec, chars, hmi_font):
    """.zi mit derselben Pixelgröße wie Simulator und fontmetrics.py (sim.load_pil_font)
    und dem Zeichenabstand aus fonts.TRACKING (in die Vorschubbreite eingebaut)."""
    from PIL import ImageFont
    from qbdisplay.sim import load_pil_font
    size = load_pil_font(spec).size
    extra = fonts.TRACKING.get(spec.fid, 0)
    orig = ImageFont.FreeTypeFont.getlength
    ImageFont.FreeTypeFont.getlength = lambda self, text, *a, **k: orig(self, text, *a, **k) + extra
    try:
        return hmi_font.encode_ttf(os.path.join(TJC, 'fonts', spec.ttf), height=spec.height,
                                   chars=chars, size=size, layout='bmp', bpp=3,
                                   name='qb_%d' % spec.fid)
    finally:
        ImageFont.FreeTypeFont.getlength = orig


def page0(qidi_portable):
    """Seitenobjekt nach dem Muster einer QIDI-Seite (vollständige Attributliste),
    einfarbiger Hintergrund, keine Bauteile."""
    tpl = json.load(open(os.path.join(qidi_portable, 'pages', 'logo.json'), encoding='utf-8'))
    attrs = dict(tpl['root']['attributes'])
    # Startbild als Hintergrund: sichtbar ab dem Einschalten, bis qbdisplay zeichnet (cls)
    attrs.update({'sta': 2, 'bco': colors.rgb565('bg'), 'pic': {'$ref': 'picture:boot'}})
    return {
        'name': 'page0',
        'header': tpl['header'],
        'root': {
            'attributes': attrs,
            'events': {'codesload': ['sendxy=1', 'bkcmd=3'], 'codesloadend': [],
                       'codesdown': [], 'codesup': [], 'codesunload': []},
        },
        'objects': [],
    }


PROGRAM = '\n'.join([
    '// qbdisplay: einmal beim Einschalten',
    'bauds=115200',
    'dim=100',
    'recmod=0',
    'page ${page:page0}',
    '',
])


def build_dir(qidi_portable, work, hmi_font=None):
    qp = json.load(open(os.path.join(qidi_portable, 'project.json'), encoding='utf-8'))
    os.makedirs(os.path.join(work, 'pages'))
    os.makedirs(os.path.join(work, 'pictures'))
    os.makedirs(os.path.join(work, 'fonts'))
    with open(os.path.join(work, 'pages', 'page0.json'), 'w', encoding='utf-8') as f:
        json.dump(page0(qidi_portable), f, ensure_ascii=False, indent=1)
    pictures = []
    for name in sorted(os.listdir(os.path.join(TJC, 'icons'))):
        if not name.lower().endswith('.png'):
            continue
        key = 'icon_' + name[:3]
        shutil.copy(os.path.join(TJC, 'icons', name), os.path.join(work, 'pictures', key + '.png'))
        pictures.append({'key': key, 'source': {'png': 'pictures/%s.png' % key}})
    # hinter den Icons, damit deren Bild-IDs gleich bleiben
    shutil.copy(os.path.join(TJC, 'boot.png'), os.path.join(work, 'pictures', 'boot.png'))
    pictures.append({'key': 'boot', 'source': {'png': 'pictures/boot.png'}})
    font_entries = []
    for spec in fonts.FONTS:
        src = os.path.join(TJC, 'fonts', spec.ttf)
        dst = os.path.join(work, 'fonts', spec.ttf)
        if not os.path.exists(dst):
            shutil.copy(src, dst)
        zi = 'fonts/font_%d.zi' % spec.fid
        with open(os.path.join(work, zi), 'wb') as f:
            f.write(encode_font(spec, charset(spec, hmi_font), hmi_font))
        font_entries.append({'key': 'font_%d' % spec.fid, 'source': {'zi': zi}})
    with open(os.path.join(work, 'Program.s'), 'w', encoding='utf-8') as f:
        f.write(PROGRAM)
    project = {
        'format': qp['format'], 'portable': True, 'project': qp['project'],
        'layouts': qp['layouts'],
        'pages': [{'key': 'page0', 'content': {'mode': 'json', 'path': 'pages/page0.json'}}],
        'pictures': pictures, 'fonts': font_entries, 'animations': [],
        'program': 'Program.s',
    }
    with open(os.path.join(work, 'project.json'), 'w', encoding='utf-8') as f:
        json.dump(project, f, ensure_ascii=False, indent=1)
    return len(pictures), len(font_entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--qidi-portable', required=True)
    ap.add_argument('--hmi-builder', required=True, help='hmi-builder/tools')
    ap.add_argument('--out', required=True)
    ap.add_argument('--keep', help='Projektverzeichnis hier behalten')
    args = ap.parse_args()
    work = args.keep or tempfile.mkdtemp(prefix='qbdisplay-tjc-')
    if args.keep and os.path.exists(work):
        shutil.rmtree(work)
    sys.path.insert(0, args.hmi_builder)
    import hmi_font
    n_pic, n_font = build_dir(args.qidi_portable, work, hmi_font)
    print('%d Icons, %d Schriften -> %s' % (n_pic, n_font, work))
    if os.path.exists(args.out):
        os.remove(args.out)
    subprocess.check_call([sys.executable, os.path.join(args.hmi_builder, 'hmi_project.py'),
                           'pack', work, args.out, '--config', os.path.join(work, 'project.json')])
    print('fertig:', args.out)


if __name__ == '__main__':
    main()
