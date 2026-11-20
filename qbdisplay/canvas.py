# qbdisplay – Zeichenfläche: Primitive -> TJC-Befehle
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Abstrakte Zeichenfläche.

Alle Zeichenoperationen werden in TJC-Befehle übersetzt (``fill``, ``cirs``,
``cir``, ``line``, ``xstr``, ``pic``) und an eine *Senke* übergeben – entweder
den echten Display-Treiber (:class:`qbdisplay.tjc.TjcDisplay`) oder den
Simulator (:class:`qbdisplay.sim.Simulator`). Beide sehen exakt dieselben
Befehle.

Abgerundete Rechtecke gibt es auf TJC nicht; sie entstehen aus zwei ``fill``
und vier ``cirs`` an den Ecken. Rahmen = äußere Fläche in Rahmenfarbe +
innere Fläche in Füllfarbe.
"""

import logging
import math

from . import colors
from . import fonts
from . import icons

log = logging.getLogger(__name__)

ALIGN = {'left': 0, 'center': 1, 'right': 2}
VALIGN = {'top': 0, 'center': 1, 'bottom': 2}


class Rect(object):
    __slots__ = ('x', 'y', 'w', 'h')

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)

    @property
    def x2(self):
        return self.x + self.w

    @property
    def y2(self):
        return self.y + self.h

    @property
    def cx(self):
        return self.x + self.w // 2

    @property
    def cy(self):
        return self.y + self.h // 2

    def contains(self, px, py):
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def inset(self, dx, dy=None):
        dy = dx if dy is None else dy
        return Rect(self.x + dx, self.y + dy, self.w - 2 * dx, self.h - 2 * dy)

    def tup(self):
        return (self.x, self.y, self.w, self.h)

    def __eq__(self, other):
        return isinstance(other, Rect) and self.tup() == other.tup()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.tup())

    def __repr__(self):
        return 'Rect(%d, %d, %d, %d)' % self.tup()


class ListSink(object):
    """Sammelt Befehle (für Tests und zum Zählen)."""

    def __init__(self):
        self.commands = []

    def send(self, cmd):
        self.commands.append(cmd)


class Canvas(object):
    """Zeichenprimitive. ``dim`` > 0 mischt alle Farben mit dem Scrim
    (Hintergrund hinter Dialogen) und lässt Bilder weg."""

    WIDTH = 800
    HEIGHT = 480

    def __init__(self, sink, missing_icon_cb=None):
        self.sink = sink
        self.dim = 0.0
        self.missing_icon_cb = missing_icon_cb
        self._warned = set()
        self.count = 0

    # -- Ausgabe -----------------------------------------------------------
    def _c(self, color):
        c = colors.resolve(color)
        if self.dim:
            c = colors.mix(c, 'scrim', self.dim)
        return colors.rgb565(c)

    def raw(self, cmd):
        self.count += 1
        self.sink.send(cmd)

    # -- Grundformen -------------------------------------------------------
    def clear(self, color):
        self.raw('cls %d' % self._c(color))

    def fill(self, x, y, w, h, color):
        x, y, w, h = int(x), int(y), int(w), int(h)
        if w <= 0 or h <= 0:
            return
        self.raw('fill %d,%d,%d,%d,%d' % (x, y, w, h, self._c(color)))

    def fill_rect(self, r, color):
        self.fill(r.x, r.y, r.w, r.h, color)

    def line(self, x0, y0, x1, y1, color):
        self.raw('line %d,%d,%d,%d,%d' % (int(round(x0)), int(round(y0)),
                                          int(round(x1)), int(round(y1)), self._c(color)))

    def thick_line(self, x0, y0, x1, y1, width, color):
        """Linie mit Breite > 1 (parallel versetzte Einzellinien)."""
        if width <= 1:
            self.line(x0, y0, x1, y1, color)
            return
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        for i in range(int(width)):
            off = i - (width - 1) / 2.0
            self.line(x0 + nx * off, y0 + ny * off, x1 + nx * off, y1 + ny * off, color)

    def disc(self, cx, cy, r, color):
        if r <= 0:
            return
        self.raw('cirs %d,%d,%d,%d' % (int(cx), int(cy), int(r), self._c(color)))

    def circle(self, cx, cy, r, color):
        if r <= 0:
            return
        self.raw('cir %d,%d,%d,%d' % (int(cx), int(cy), int(r), self._c(color)))

    def ring(self, cx, cy, r, width, color, inner):
        """Kreisring: Scheibe in Ringfarbe, innen Scheibe in Füllfarbe."""
        self.disc(cx, cy, r, color)
        if inner is not None:
            self.disc(cx, cy, r - width, inner)

    def round_rect(self, x, y, w, h, r, color):
        x, y, w, h = int(x), int(y), int(w), int(h)
        r = int(min(r, w // 2, h // 2))
        if w <= 0 or h <= 0:
            return
        if r <= 1:
            self.fill(x, y, w, h, color)
            return
        self.fill(x, y + r, w, h - 2 * r, color)
        self.fill(x + r, y, w - 2 * r, r, color)
        self.fill(x + r, y + h - r, w - 2 * r, r, color)
        for cx, cy in ((x + r, y + r), (x + w - 1 - r, y + r),
                       (x + r, y + h - 1 - r), (x + w - 1 - r, y + h - 1 - r)):
            self.disc(cx, cy, r, color)

    def rr(self, rect, r, color):
        self.round_rect(rect.x, rect.y, rect.w, rect.h, r, color)

    def box(self, rect, r, fill, border=None, bw=1):
        """Abgerundete Fläche mit optionalem Rahmen."""
        if border is None or bw <= 0:
            self.rr(rect, r, fill)
            return
        self.rr(rect, r, border)
        inner = rect.inset(bw)
        if fill is not None:
            self.rr(inner, max(0, r - bw), fill)

    def arc_lines(self, cx, cy, r, a0, a1, color, width=1, segments=None):
        """Bogen als Polylinie (Winkel in Grad, 0 = rechts, im Uhrzeigersinn)."""
        span = abs(a1 - a0)
        if segments is None:
            segments = max(2, int(span * r / 400.0) + 2)
        for wi in range(int(width)):
            rr_ = r - wi
            pts = []
            for i in range(segments + 1):
                a = math.radians(a0 + (a1 - a0) * i / float(segments))
                pts.append((cx + rr_ * math.cos(a), cy + rr_ * math.sin(a)))
            for p, q in zip(pts, pts[1:]):
                self.line(p[0], p[1], q[0], q[1], color)

    def dashed_box(self, rect, r, color, bw=2, dash=8, gap=6, fill=None):
        """Gestrichelter, abgerundeter Rahmen (für leere Slots/Ziele)."""
        if fill is not None:
            self.rr(rect, r, fill)
        x, y, w, h = rect.tup()
        r = int(min(r, w // 2, h // 2))
        # gerade Kanten: kurze Füllflächen
        def hdash(x0, x1, yy):
            pos = x0
            while pos < x1:
                end = min(pos + dash, x1)
                self.fill(pos, yy, end - pos, bw, color)
                pos = end + gap

        def vdash(y0, y1, xx):
            pos = y0
            while pos < y1:
                end = min(pos + dash, y1)
                self.fill(xx, pos, bw, end - pos, color)
                pos = end + gap
        hdash(x + r + gap // 2, x + w - r - gap // 2, y)
        hdash(x + r + gap // 2, x + w - r - gap // 2, y + h - bw)
        vdash(y + r + gap // 2, y + h - r - gap // 2, x)
        vdash(y + r + gap // 2, y + h - r - gap // 2, x + w - bw)
        # Ecken als kurze Bögen
        if r > 2:
            for cx, cy, a0 in ((x + r, y + r, 180), (x + w - 1 - r, y + r, 270),
                               (x + w - 1 - r, y + h - 1 - r, 0), (x + r, y + h - 1 - r, 90)):
                self.arc_lines(cx, cy, r, a0 + 15, a0 + 75, color, width=bw, segments=3)

    def dashed_circle(self, cx, cy, r, color, width=2, dashes=12):
        step = 360.0 / dashes
        for i in range(dashes):
            a0 = i * step
            self.arc_lines(cx, cy, r, a0, a0 + step * 0.55, color, width=width, segments=2)

    def arc_progress(self, cx, cy, r, width, frac, color, track, inner):
        """Fortschrittsring (Start oben, im Uhrzeigersinn). Spur als Ring,
        Fortschritt als dicht gesetzte Scheiben (runde Enden wie im Entwurf)."""
        self.ring(cx, cy, r, width, track, inner)
        frac = max(0.0, min(1.0, frac))
        if frac <= 0:
            return
        mid = r - width / 2.0
        rad = int(width // 2)
        span = 360.0 * frac
        steps = max(2, int(math.radians(span) * mid / 3.0))
        for i in range(steps + 1):
            a = math.radians(-90 + span * i / float(steps))
            self.disc(cx + mid * math.cos(a), cy + mid * math.sin(a), rad, color)

    # -- Text --------------------------------------------------------------
    def text(self, x, y, w, h, text, fid, fg, bg, align='left', valign='center',
             ellipsis=True):
        """Text in eine Box (xstr mit Vollfarb-Hintergrund ``bg``, damit die
        Kantenglättung der Schrift korrekt gemischt wird)."""
        if w <= 0 or h <= 0:
            return
        s = fonts.ellipsize(text, fid, w) if ellipsis else fonts.sanitize(text)
        self.raw('xstr %d,%d,%d,%d,%d,%d,%d,%d,%d,1,"%s"' % (
            int(x), int(y), int(w), int(h), fid, self._c(fg), self._c(bg),
            ALIGN[align], VALIGN[valign], s))
        return fonts.measure(s, fid)

    def text_in(self, rect, text, fid, fg, bg, align='left', valign='center'):
        return self.text(rect.x, rect.y, rect.w, rect.h, text, fid, fg, bg, align, valign)

    def label(self, x, y, text, fid, fg, bg, h=None, max_w=None):
        """Text ab (x, y) genau so breit wie nötig – gibt rechte Kante zurück."""
        s = fonts.sanitize(text)
        if max_w is not None:
            s = fonts.ellipsize(s, fid, max_w)
        w = fonts.measure(s, fid) + 2
        h = h or fonts.height(fid)
        self.text(x, y, w, h, s, fid, fg, bg, 'left', 'center', ellipsis=False)
        return x + w

    def label_right(self, x2, y, text, fid, fg, bg, h=None):
        """Rechtsbündig bis x2 – gibt linke Kante zurück."""
        s = fonts.sanitize(text)
        w = fonts.measure(s, fid) + 2
        h = h or fonts.height(fid)
        self.text(x2 - w, y, w, h, s, fid, fg, bg, 'right', 'center', ellipsis=False)
        return x2 - w

    # -- Bilder ------------------------------------------------------------
    def icon(self, name, x, y, size, fg, bg):
        """Icon aus der TJC-Bildliste (fest eingefärbt auf Hintergrund ``bg``)."""
        if self.dim:
            return  # Bilder lassen sich nicht abdunkeln -> hinter Dialogen weglassen
        pid = icons.lookup(name, size, fg, bg)
        if pid is None:
            key = (name, size, fg, bg)
            if self.missing_icon_cb is not None:
                self.missing_icon_cb(key)
            pid = icons.lookup_fallback(name, size, fg, bg)
            if key not in self._warned:
                self._warned.add(key)
                log.warning('Icon fehlt in der TJC-Datei: %s', key)
            if pid is None:
                return
        self.raw('pic %d,%d,%d' % (int(x), int(y), pid))
