# qbdisplay – Icon-Vorlagen (SVG-Pfade) und Rasterung mit Pillow
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Eigene Icons im Stil der Entwürfe (docs/display-redesign.html):
24 × 24-Raster, Linienstärke 2,2, runde Enden. Hier als kleine SVG-Teilmenge
beschrieben und mit 8-fachem Supersampling gerastert.

Elemente:  ('p', 'd-Pfad')  ('c', cx, cy, r[, dash])  ('r', x, y, w, h, rx)
"""

import math
import re

from PIL import Image, ImageDraw

ICONS = {
    'home': [('p', 'M3 11l9-7 9 7'), ('p', 'M5 9.5V20h14V9.5'), ('p', 'M10 20v-5h4v5')],
    'spool': [('c', 12, 12, 9), ('c', 12, 12, 5.5, (2, 2.4)), ('c', 12, 12, 2)],
    'move': [('p', 'M12 3v18M3 12h18'), ('p', 'M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3')],
    'folder': [('p', 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z')],
    'sliders': [('p', 'M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1'), ('c', 15, 6, 2),
                ('c', 9, 12, 2), ('c', 17, 18, 2)],
    'nozzle': [('p', 'M7 3h10v6H7z'), ('p', 'M8.5 9l1.5 6h4l1.5-6'), ('p', 'M11 15l1 3 1-3'),
               ('p', 'M12 20.5v.5')],
    'bed': [('p', 'M3 15h18'), ('p', 'M5 19h14'),
            ('p', 'M8 4c-1.2 2 1.2 3.5 0 6M12 4c-1.2 2 1.2 3.5 0 6M16 4c-1.2 2 1.2 3.5 0 6')],
    'chamber': [('r', 4, 3, 16, 18, 2), ('p', 'M4 8h16'), ('p', 'M12 11v5'), ('c', 12, 17, 1.6)],
    'fan': [('c', 12, 12, 1.8),
            ('p', 'M12 10.2C11 6 12 3 15 3c2 0 2.6 2 1.6 3.5-1 1.3-2.6 2.5-4.6 3.7z'
                  'M13.8 12c4.2-1 7.2 0 7.2 3 0 2-2 2.6-3.5 1.6-1.3-1-2.5-2.6-3.7-4.6z'
                  'M12 13.8c1 4.2 0 7.2-3 7.2-2 0-2.6-2-1.6-3.5 1-1.3 2.6-2.5 4.6-3.7z'
                  'M10.2 12C6 13 3 12 3 9c0-2 2-2.6 3.5-1.6 1.3 1 2.5 2.6 3.7 4.6z')],
    'light': [('p', 'M9 18h6M10 21h4'),
              ('p', 'M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z')],
    'pause': [('p', 'M9 5v14M15 5v14')],
    'play': [('p', 'M7 4.5v15l12-7.5z')],
    'stop': [('r', 6, 6, 12, 12, 1.5)],
    'check': [('p', 'M5 12.5l4.5 4.5L19 7')],
    'x': [('p', 'M6 6l12 12M18 6L6 18')],
    'alert': [('p', 'M12 3.5l9.5 16.5h-19z'), ('p', 'M12 10v4.5'), ('p', 'M12 17.5v.01')],
    'drop': [('p', 'M12 3s6.5 7 6.5 11.5a6.5 6.5 0 0 1-13 0C5.5 10 12 3 12 3z')],
    'therm': [('p', 'M10 4.5a2 2 0 0 1 4 0V14a4 4 0 1 1-4 0z'), ('p', 'M12 9v8')],
    'edit': [('p', 'M4 20h4L19 9l-4-4L4 16z'), ('p', 'M13 7l4 4')],
    'eject': [('p', 'M5 14h14L12 5z'), ('p', 'M5 19h14')],
    'down': [('p', 'M12 4v15M6 13l6 6 6-6')],
    'up': [('p', 'M12 20V5M6 11l6-6 6 6')],
    'left': [('p', 'M20 12H5M11 6l-6 6 6 6')],
    'right': [('p', 'M4 12h15M13 6l6 6-6 6')],
    'chev': [('p', 'M9 6l6 6-6 6')],
    'chevup': [('p', 'M6 15l6-6 6 6')],
    'chevdown': [('p', 'M6 9l6 6 6-6')],
    'clock': [('c', 12, 12, 9), ('p', 'M12 7v5l3 2')],
    'layers': [('p', 'M12 3l9 5-9 5-9-5z'), ('p', 'M3 13l9 5 9-5')],
    'retry': [('p', 'M20 12a8 8 0 1 1-2.3-5.7'), ('p', 'M20 4v5h-5')],
    'swap': [('p', 'M4 8h14l-3-3M20 16H6l3 3')],
    'shield': [('p', 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z'), ('p', 'M8.5 12l2.5 2.5 4.5-5')],
    'cloudoff': [('p', 'M7 18h10a4 4 0 0 0 .7-7.9A6 6 0 0 0 6.3 9 4.5 4.5 0 0 0 7 18z'),
                 ('p', 'M3 3l18 18')],
    'wifi': [('p', 'M2 9a15 15 0 0 1 20 0'), ('p', 'M5 12.5a10 10 0 0 1 14 0'),
             ('p', 'M8.5 16a5 5 0 0 1 7 0'), ('p', 'M12 19.5v.01')],
    'wifioff': [('p', 'M2 9a15 15 0 0 1 20 0'), ('p', 'M5 12.5a10 10 0 0 1 14 0'),
                ('p', 'M8.5 16a5 5 0 0 1 7 0'), ('p', 'M12 19.5v.01'), ('p', 'M3 3l18 18')],
    'ethernet': [('r', 4, 4, 16, 12, 2), ('p', 'M8 16v4h8v-4'), ('p', 'M8 8v3M11 8v3M14 8v3M17 8v3')],
    'link': [('p', 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1'),
             ('p', 'M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1')],
    'monitor': [('r', 3, 4, 18, 12, 2), ('p', 'M8 20h8M12 16v4')],
    'power': [('p', 'M12 3v8'), ('p', 'M6.3 7a8 8 0 1 0 11.4 0')],
    'sun': [('c', 12, 12, 4),
            ('p', 'M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4'
                  'M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4')],
    'box': [('r', 3, 7, 18, 13, 2), ('p', 'M3 11h18'), ('p', 'M7 7V4h10v3')],
    'target': [('c', 12, 12, 8), ('c', 12, 12, 3)],
    'globe': [('c', 12, 12, 9), ('p', 'M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18')],
    'info': [('c', 12, 12, 9), ('p', 'M12 11v6M12 7.5v.01')],
    'tube': [('p', 'M4 18c4 0 4-12 8-12s4 12 8 12')],
    'rfid': [('r', 3, 6, 18, 12, 2), ('p', 'M7 10.5a3 3 0 0 1 0 3M10 9a5.5 5.5 0 0 1 0 6')],
}

_TOKEN = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?')


def _arc_points(x0, y0, rx, ry, phi, large, sweep, x1, y1, n=24):
    """SVG-Bogen (Endpunkt-Form) -> Punkte. SVG 1.1, Anhang F.6.5."""
    if rx == 0 or ry == 0:
        return [(x1, y1)]
    phi = math.radians(phi)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cp * dx + sp * dy
    y1p = -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        rx *= math.sqrt(lam)
        ry *= math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x0 + x1) / 2.0
    cy = sp * cxp + cp * cyp + (y0 + y1) / 2.0

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    pts = []
    for i in range(1, n + 1):
        t = t1 + dt * i / float(n)
        pts.append((cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp,
                    cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp))
    return pts


def parse_path(d):
    """SVG-Pfad -> Liste (punkte, geschlossen)."""
    toks = _TOKEN.findall(d)
    i = 0
    subpaths = []
    pts = []
    closed = False
    x = y = sx = sy = 0.0
    cmd = None
    last_ctrl = None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    def flush():
        nonlocal pts, closed
        if len(pts) >= 1:
            subpaths.append((pts, closed))
        pts, closed = [], False

    while i < len(toks):
        t = toks[i]
        if re.match(r'[A-Za-z]', t):
            cmd = t
            i += 1
            if cmd in 'Zz':
                closed = True
                if pts:
                    pts.append(pts[0])
                x, y = sx, sy
                flush()
                continue
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if c == 'M':
            flush()
            x, y = num() + ox, num() + oy
            sx, sy = x, y
            pts = [(x, y)]
            cmd = 'l' if rel else 'L'
        elif c == 'L':
            x, y = num() + ox, num() + oy
            pts.append((x, y))
        elif c == 'H':
            x = num() + (x if rel else 0.0)
            pts.append((x, y))
        elif c == 'V':
            y = num() + (y if rel else 0.0)
            pts.append((x, y))
        elif c in 'CS':
            if c == 'C':
                x1, y1 = num() + ox, num() + oy
            else:
                if last_ctrl is not None:
                    x1, y1 = 2 * x - last_ctrl[0], 2 * y - last_ctrl[1]
                else:
                    x1, y1 = x, y
            x2, y2 = num() + ox, num() + oy
            x3, y3 = num() + ox, num() + oy
            for k in range(1, 13):
                tt = k / 12.0
                mt = 1 - tt
                pts.append((mt ** 3 * x + 3 * mt ** 2 * tt * x1 + 3 * mt * tt ** 2 * x2 + tt ** 3 * x3,
                            mt ** 3 * y + 3 * mt ** 2 * tt * y1 + 3 * mt * tt ** 2 * y2 + tt ** 3 * y3))
            last_ctrl = (x2, y2)
            x, y = x3, y3
            continue
        elif c == 'A':
            rx, ry, phi = num(), num(), num()
            large, sweep = int(num()), int(num())
            x1, y1 = num() + ox, num() + oy
            pts.extend(_arc_points(x, y, rx, ry, phi, large, sweep, x1, y1))
            x, y = x1, y1
        else:
            raise ValueError('Pfadbefehl %s nicht unterstützt' % cmd)
        last_ctrl = None
    flush()
    return subpaths


def render_icon(name, size, fg, bg, ss=8):
    """Icon als RGB-Bild (fg auf bg, kantengeglättet)."""
    elems = ICONS[name]
    big = size * ss
    scale = big / 24.0
    sw_units = 2.6 if size <= 20 else 2.2
    sw = max(1, int(round(sw_units * scale)))
    mask = Image.new('L', (big, big), 0)
    d = ImageDraw.Draw(mask)

    def P(px, py):
        return (px * scale, py * scale)

    for el in elems:
        kind = el[0]
        if kind == 'p':
            for pts, closed in parse_path(el[1]):
                sp = [P(*p) for p in pts]
                if len(sp) == 1 or (len(sp) == 2 and sp[0] == sp[1]):
                    x, y = sp[0]
                    d.ellipse([x - sw / 2, y - sw / 2, x + sw / 2, y + sw / 2], fill=255)
                    continue
                d.line(sp, fill=255, width=sw, joint='curve')
                # runde Enden und runde Ecken
                for (x, y) in sp:
                    d.ellipse([x - sw / 2, y - sw / 2, x + sw / 2, y + sw / 2], fill=255)
        elif kind == 'c':
            cx, cy, r = el[1], el[2], el[3]
            dash = el[4] if len(el) > 4 else None
            cx, cy = P(cx, cy)
            rr = r * scale
            box = [cx - rr - sw / 2, cy - rr - sw / 2, cx + rr + sw / 2, cy + rr + sw / 2]
            if dash:
                circ = 2 * math.pi * r
                on, off = dash
                a = 0.0
                while a < 360:
                    a_on = on / circ * 360
                    d.arc(box, a, a + a_on, fill=255, width=sw)
                    a += (on + off) / circ * 360
            else:
                d.ellipse(box, outline=255, width=sw)
        elif kind == 'r':
            x, y, w, h, rx = el[1:]
            x0, y0 = P(x, y)
            x1, y1 = P(x + w, y + h)
            d.rounded_rectangle([x0 - sw / 2, y0 - sw / 2, x1 + sw / 2, y1 + sw / 2],
                                radius=rx * scale + sw / 2, outline=255, width=sw)
    small = mask.resize((size, size), Image.LANCZOS)
    out = Image.new('RGB', (size, size), bg)
    out.paste(Image.new('RGB', (size, size), fg), (0, 0), small)
    return out
