# qbdisplay – Bausteine (Kachel, Button, Chip, Toggle, Spule, ...)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Zeichenfunktionen für die Komponenten des Designsystems
(docs/display-design-review.md, Abschnitt "Komponenten").

Konvention: ``under`` ist die Farbe *unter* dem Baustein (für Ecken,
Text-Hintergrund und eingefärbte Icons).
"""

import re

from .. import colors
from .. import fonts as F
from ..canvas import Rect

R_TILE = 14
R_BTN = 12

# Glow-Rahmen: Mischanteile der Lichthof-Stufen (außen -> innen). Liegen
# INNERHALB des Rechtecks, damit Dirty-Rects keine Reste hinterlassen.
GLOW_STEPS = {1: (0.34,), 2: (0.14, 0.38), 3: (0.08, 0.20, 0.40)}


def caps(text):
    """Großbuchstaben für Labels (ß -> SS, Umlaute bleiben im Zeichensatz)."""
    return F.sanitize(text).upper()


def glow_box(c, rect, r, fill, color='accent', under='bg', halo=2, bw=2, inner=True):
    """Leuchtender Rahmen ("Neon"): Lichthof nach außen in ``halo`` Stufen,
    Rahmen ``bw`` px in ``color``, innen ein 1-px-Schimmer und die Füllung.
    Alles innerhalb von ``rect``. -> Innenrechteck (Füllfläche)."""
    k = 0
    for t in GLOW_STEPS.get(halo, ()):
        c.rr(rect.inset(k), max(0, r - k), colors.mix(under, color, t))
        k += 1
    c.rr(rect.inset(k), max(0, r - k), color)
    k += bw
    if fill is None:
        fill = under
    if inner:
        c.rr(rect.inset(k), max(0, r - k), colors.mix(fill, color, 0.24))
        k += 1
    c.rr(rect.inset(k), max(0, r - k), fill)
    return rect.inset(k)


def tile(c, rect, fill='surface', border='line', r=R_TILE, bw=1, glow=None, under='bg'):
    """Kachel. ``glow``: Farbe für einen leuchtenden Rahmen (aktive Kachel)."""
    if glow:
        glow_box(c, rect, r, fill, glow, under, halo=2, bw=1, inner=True)
        return
    c.box(rect, r, fill, border, bw)


def tile_accent_left(c, rect, color, fill='surface', border='line'):
    """Kachel mit 4-px-Farbkante links (Farbwechsel-Panel, LAN-Karte)."""
    c.box(rect, R_TILE, fill, border, 1)
    c.fill(rect.x + 1, rect.y + 12, 3, rect.h - 24, color)
    c.fill(rect.x + 4, rect.y + 16, 1, rect.h - 32, colors.mix(fill, color, 0.4))


def caption(c, x, y, text, under='bg', fg='text3', tick='accent', w=None):
    """Abschnittsüberschrift: kleiner Akzentstrich + Großbuchstaben."""
    if tick:
        c.fill(x, y + 4, 3, 11, tick)
        x += 10
    if w is not None:
        c.text(x, y, w - (10 if tick else 0), 18, caps(text), F.CAP, fg, under)
        return x + w
    return c.label(x, y, caps(text), F.CAP, fg, under, h=18)


def header(c, rect, icon, text, under='surface', icon_fg='accent', fg='text2', x=None, y=None,
           isize=20, max_w=None):
    """Kachelkopf: Linien-Icon (Akzent) + Großbuchstaben-Label. -> rechte Kante."""
    x = rect.x + 16 if x is None else x
    y = rect.y + 14 if y is None else y
    if icon:
        c.icon(icon, x, y + (22 - isize) // 2, isize, icon_fg, under)
        x += isize + 9
    return c.label(x, y + 2, caps(text), F.LBL, fg, under, h=18, max_w=max_w)


def icon_text(c, x, y, h, icon, text, fg, under, fid=F.LBL, isize=22, gap=8,
              icon_fg=None, max_w=None):
    """Icon + Text, vertikal zentriert in Höhe h. Gibt rechte Kante zurück."""
    if icon:
        c.icon(icon, x, y + (h - isize) // 2, isize, icon_fg or fg, under)
        x += isize + gap
    return c.label(x, y + (h - F.height(fid)) // 2, text, fid, fg, under, max_w=max_w)


BTN_STYLES = {
    # kind: (fill, border, bw, text)
    'primary': ('accent', None, 0, 'on_accent'),
    'secondary': ('surface2', 'line', 1, 'text'),
    'danger': (None, 'err', 2, 'err'),
    'disabled': ('surface', None, 0, 'text3'),
    'selected': ('tint', 'accent', 2, 'text'),
    'ghost': (None, None, 0, 'text2'),
}


def button(c, rect, label='', kind='secondary', icon=None, under='bg', fid=F.BTN,
           pressed=False, stack=False, sub=None, isize=24, label_fg=None, sub_fid=F.CAP,
           icon_fg=None):
    """Button nach Designsystem. ``stack``: Icon über Text (Leiste unten im
    Druckbildschirm); ``sub``: zweite, kleine Zeile (Profil-Kacheln).

    primary  = Cyan-Fläche mit Lichthof
    selected = getönte Fläche mit leuchtendem Cyan-Rahmen
    """
    fill, border, bw, fg = BTN_STYLES[kind]
    if label_fg:
        fg = label_fg
    face = fill if fill is not None else under
    if kind == 'disabled':
        c.dashed_box(rect, R_BTN, 'line', bw=1, dash=6, gap=4, fill='surface')
    elif kind == 'primary':
        k = 0
        for t in GLOW_STEPS[2]:
            c.rr(rect.inset(k), R_BTN - k, colors.mix(under, 'accent', t))
            k += 1
        if pressed:
            c.rr(rect.inset(k), R_BTN - k, 'white')
            k += 2
        c.rr(rect.inset(k), R_BTN - k, 'accent')
    elif kind == 'selected':
        glow_box(c, rect, R_BTN, face, 'white' if pressed else 'accent', under, halo=2, bw=2)
    elif pressed:
        c.box(rect, R_BTN, face, 'accent', 2)
    elif border:
        c.box(rect, R_BTN, face, border, bw)
    elif fill is not None:
        c.rr(rect, R_BTN, fill)
    ifg = icon_fg or fg
    if stack:
        th = F.height(fid)
        total = (isize + 6 if icon else 0) + th
        y = rect.y + (rect.h - total) // 2
        if icon:
            c.icon(icon, rect.cx - isize // 2, y, isize, ifg, face)
            y += isize + 6
        c.text(rect.x + 4, y, rect.w - 8, th, label, fid, fg, face, 'center')
        return
    if sub is not None:
        th, sh = F.height(fid), F.height(sub_fid)
        y = rect.y + (rect.h - th - sh) // 2
        c.text(rect.x + 6, y, rect.w - 12, th, label, fid, fg, face, 'center')
        c.text(rect.x + 6, y + th, rect.w - 12, sh, sub, sub_fid,
               'accent' if kind == 'selected' else 'text3', face, 'center')
        return
    tw = min(F.measure(label, fid), rect.w - 16 - (isize + 10 if icon else 0)) if label else 0
    total = tw + ((isize + (10 if label else 0)) if icon else 0)
    x = rect.cx - total // 2
    if icon:
        c.icon(icon, x, rect.cy - isize // 2, isize, ifg, face)
        x += isize + 10
    if label:
        th = F.height(fid)
        c.text(x, rect.cy - th // 2, tw + 2, th, label, fid, fg, face, 'left')


CHIP_STYLES = {
    # kind: (fill, border, text, dashed)
    'loaded': ('accent', None, 'on_accent', False),
    'ready': ('ok_bg', None, 'ok', False),
    'empty': (None, 'text3', 'text3', True),
    'loading': ('info', None, 'on_info', False),
    'off': ('surface3', None, 'text2', False),
    'warn': ('warn_bg', None, 'warn', False),
    'err': ('err_bg', None, 'err', False),
    'okfill': ('ok_bg', None, 'ok', False),
    'heat': ('heat_bg', None, 'heat', False),
}


def chip_width(text, icon=None, fid=F.CAP):
    return F.measure(caps(text), fid) + 22 + (20 if icon else 0)


def chip(c, x, y, text, kind, under, icon=None, fid=F.CAP, h=26, right=False):
    """Zustandschip (Pille, Großbuchstaben). ``right``: x ist die rechte Kante. -> Rect."""
    text = caps(text)
    w = chip_width(text, icon, fid)
    if right:
        x = x - w
    rect = Rect(x, y, w, h)
    fill, border, fg, dashed = CHIP_STYLES[kind]
    face = fill if fill is not None else under
    if dashed:
        c.dashed_box(rect, h // 2, border, bw=1, dash=4, gap=3, fill=under)
    elif border:
        c.box(rect, h // 2, face, border, 2)
    else:
        c.rr(rect, h // 2, fill)
    tx = x + 11
    if icon:
        c.icon(icon, tx, y + (h - 16) // 2, 16, fg, face)
        tx += 20
    c.text(tx, y + (h - F.height(fid)) // 2, w - (tx - x) - 8, F.height(fid), text, fid, fg,
           face, 'left', ellipsis=False)
    return rect


PILL_COLORS = {'ok': ('ok_bg', 'ok'), 'run': ('run_bg', 'accent'), 'err': ('err_bg', 'err'),
               'warn': ('warn_bg', 'warn'), 'info': ('info_bg', 'info')}


def pill_width(text):
    """Breite der Zustandspille. Ziffern zählen alle so breit wie die breiteste,
    damit die Pille bei "14 %" -> "15 %" nicht die Form wechselt: dann wird nur
    ihr Text neu geschrieben (siehe :func:`pill_text_rect`)."""
    widest = max('0123456789', key=lambda d: F.measure(d, F.CAP))
    return F.measure(re.sub('[0-9]', widest, caps(text)), F.CAP) + 36


def pill_shape(c, x, y, w, kind):
    """Zustandspille ohne Text: Fläche und leuchtender Punkt."""
    bg, fg = PILL_COLORS[kind]
    c.rr(Rect(x, y, w, 26), 13, bg)
    c.disc(x + 14, y + 13, 6, colors.mix(bg, fg, 0.35))
    c.disc(x + 14, y + 13, 4, fg)


def pill_text_rect(x, y, w):
    return Rect(x + 25, y + 13 - F.height(F.CAP) // 2, w - 30, F.height(F.CAP))


def pill_text(c, x, y, w, text, kind):
    bg, fg = PILL_COLORS[kind]
    r = pill_text_rect(x, y, w)
    c.text(r.x, r.y, r.w, r.h, caps(text), F.CAP, fg, bg, ellipsis=False)


def pill_state(c, x, y, text, kind, under='bar'):
    """Zustandspille der Statusleiste (leuchtender Punkt + Großbuchstaben)."""
    w = pill_width(text)
    pill_shape(c, x, y, w, kind)
    pill_text(c, x, y, w, text, kind)
    return w


def toggle(c, x, y, on, under):
    """Schalter 72 × 40: an = dunkle Spur mit Cyan-Rahmen und leuchtendem Knopf."""
    rect = Rect(x, y, 72, 40)
    if on:
        c.box(rect, 20, 'tint', 'accent', 2)
        c.disc(x + 51, y + 20, 15, colors.mix('tint', 'accent', 0.4))
        c.disc(x + 51, y + 20, 12, 'accent')
    else:
        c.box(rect, 20, 'surface3', 'line', 1)
        c.disc(x + 21, y + 20, 12, 'text3')


def bar(c, rect, frac, color='accent', track='surface3', knob=False, under='surface'):
    """Fortschrittsbalken; ``knob``: leuchtender Punkt am Ende (Live-Fortschritt)."""
    r = rect.h // 2
    c.rr(rect, r, track)
    frac = max(0.0, min(1.0, frac or 0.0))
    w = int(round(rect.w * frac))
    if w > 0:
        c.rr(Rect(rect.x, rect.y, max(w, rect.h), rect.h), r, color)
    if knob and w > 0:
        kx = rect.x + max(w, rect.h) - r - 1
        c.disc(kx, rect.cy, r + 4, colors.mix(under, color, 0.3))
        c.disc(kx, rect.cy, r + 2, color)
        c.disc(kx, rect.cy, max(1, r - 2), 'white')


def color_dot(c, cx, cy, r, color, under, ring=True):
    """Farbpunkt mit hellem Ring (damit Schwarz auf Dunkel sichtbar bleibt)."""
    if ring:
        c.disc(cx, cy, r + 2, colors.ring_on(under))
    c.disc(cx, cy, r, color or 'surface3')


def spool(c, cx, cy, r, color, state, under, accent_ring=False, plus=False):
    """Spule: Flansch (heller Ring), Wicklung in Filamentfarbe, Nabe.
    ``accent_ring``: Spule steckt in der Düse -> leuchtender Cyan-Ring.
    Leer = gestrichelter Kreis."""
    if state in ('empty', 'unknown') or not color:
        c.dashed_circle(cx, cy, r, 'text3', width=2, dashes=16)
        if plus:
            c.fill(cx - 12, cy - 1, 24, 3, 'text3')
            c.fill(cx - 1, cy - 12, 3, 24, 'text3')
        else:
            c.ring(cx, cy, int(r * 0.33), 2, 'text3', under)
        return
    if accent_ring:
        c.disc(cx, cy, r + 4, colors.mix(under, 'accent', 0.2))
        c.disc(cx, cy, r + 2, colors.mix(under, 'accent', 0.5))
        c.disc(cx, cy, r, 'accent')
        c.disc(cx, cy, r - 3, color)
    else:
        c.disc(cx, cy, r, colors.ring_on(under))
        c.disc(cx, cy, r - 3, color)
    # Wicklungslinien, leicht abgesetzt
    bright = colors.luminance(color) > 0.08
    shade = colors.mix(color, '#000000', 0.22) if bright else colors.mix(color, '#FFFFFF', 0.14)
    c.circle(cx, cy, int(r * 0.80), shade)
    c.circle(cx, cy, int(r * 0.62), shade)
    c.disc(cx, cy, int(r * 0.36) + 2, colors.ring_on(under))
    c.disc(cx, cy, int(r * 0.36), 'surface3')
    c.disc(cx, cy, max(2, int(r * 0.15)), 'bg')


def seg(c, rect, items, selected, fid=F.BTN, under='bg'):
    """Segmentschalter: Auswahl als getöntes Feld mit Cyan-Rahmen.
    -> Liste der Teil-Rechtecke (für Touch-Ziele)."""
    c.box(rect, R_BTN, 'surface', 'line', 1)
    n = len(items)
    inner = rect.inset(4)
    gap = 4
    w = (inner.w - gap * (n - 1)) / float(n)
    rects = []
    for i, label in enumerate(items):
        x0 = int(round(inner.x + i * (w + gap)))
        x1 = int(round(inner.x + i * (w + gap) + w))
        rr = Rect(x0, inner.y, x1 - x0, inner.h)
        rects.append(rr)
        on = i == selected
        face = 'tint' if on else 'surface'
        if on:
            c.box(rr, 9, 'tint', 'accent', 2)
        elif i > 0 and i - 1 != selected:
            c.fill(rr.x - gap // 2 - 1, rr.y + 12, 1, rr.h - 24, 'line')
        c.text(rr.x + 2, rr.cy - F.height(fid) // 2, rr.w - 4, F.height(fid), label, fid,
               'accent' if on else 'text2', face, 'center')
    return rects


def plus_minus(c, rect, sign, under, pressed=False, enabled=True):
    """Taste mit Plus/Minus aus Füllflächen (scharf, unabhängig vom Font)."""
    button(c, rect, '', 'secondary' if enabled else 'disabled', under=under, pressed=pressed)
    fg = 'accent' if enabled else 'text3'
    c.fill(rect.cx - 11, rect.cy - 1, 22, 3, fg)
    if sign == '+':
        c.fill(rect.cx - 1, rect.cy - 11, 3, 22, fg)


def text_lines(c, x, y, w, lines_or_text, fid, fg, under, line_h=None, max_lines=None):
    """Mehrzeiliger Text (Wortumbruch auf dem Host). -> y nach dem Text."""
    if isinstance(lines_or_text, (list, tuple)):
        lines = lines_or_text
    else:
        lines = F.wrap(lines_or_text, fid, w, max_lines)
    lh = line_h or (F.height(fid) + 3)
    for ln in lines:
        c.text(x, y, w, F.height(fid), ln, fid, fg, under)
        y += lh
    return y


def value_unit(c, x, y, h, value, unit, vfid, ufid, fg, under, unit_fg='text3', gap=2):
    """Messwert + kleinere, hellere Einheit auf gemeinsamer Grundlinie (ca.)."""
    vh, uh = F.height(vfid), F.height(ufid)
    x2 = c.label(x, y, value, vfid, fg, under, h=vh)
    # Einheit: an der Unterkante der Ziffern ausrichten
    base_off = int(vh * 0.80) - int(uh * 0.80)
    c.label(x2 + gap, y + base_off, unit, ufid, unit_fg, under, h=uh)
    return x2 + gap + F.measure(unit, ufid)
