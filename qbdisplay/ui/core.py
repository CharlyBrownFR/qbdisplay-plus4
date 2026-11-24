# qbdisplay – Regionen, Touch-Ziele und Renderer mit Dirty-Rects
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Retained-Mode in klein.

Eine Seite beschreibt bei jedem Durchlauf ihre *Regionen* (Rechteck +
Schlüssel + Zeichenfunktion) und *Touch-Ziele*. Der Renderer vergleicht die
Schlüssel mit dem letzten Durchlauf und zeichnet nur Regionen neu, deren
Schlüssel sich geändert hat (plus deren Kinder). Weggefallene Regionen werden
mit ihrer Hintergrundfarbe gelöscht. So bleibt die serielle Leitung frei –
bei 115200 Baud kostet ein voller Bildschirm etwa 0,5–1 s.
"""

from ..canvas import Rect


class Region(object):
    __slots__ = ('rid', 'rect', 'key', 'paint', 'clear', 'parent', 'opaque', 'gaps')

    def __init__(self, rid, rect, key, paint, clear='bg', parent=None, opaque=False,
                 gaps=False):
        self.rid = rid
        self.rect = rect
        self.key = key
        self.paint = paint
        self.clear = clear
        self.parent = parent
        self.opaque = opaque
        self.gaps = gaps


class Target(object):
    __slots__ = ('tid', 'rect', 'action', 'enabled')

    def __init__(self, tid, rect, action, enabled=True):
        self.tid = tid
        self.rect = rect
        self.action = action
        self.enabled = enabled


class Frame(object):
    """Sammelt Regionen und Ziele eines Durchlaufs."""

    def __init__(self):
        self.regions = []
        self.targets = []
        self._ids = set()

    def region(self, rid, rect, key, paint, clear='bg', parent=None, opaque=False, gaps=False):
        """``gaps``: nicht vorher löschen, sondern zeichnen und danach nur die
        unbedeckten Stellen mit ``clear`` füllen. Für wechselnde Werte (Text,
        Icons, Flächen): die Anzeige springt direkt um, ohne leeres Zwischenbild."""
        if rid in self._ids:
            raise ValueError('Region doppelt: %s' % rid)
        self._ids.add(rid)
        self.regions.append(Region(rid, rect, key, paint, clear, parent, opaque, gaps))

    def target(self, tid, rect, action, enabled=True):
        self.targets.append(Target(tid, rect, action, enabled))

    def hit(self, x, y):
        """Oberstes aktives Ziel an (x, y). Kleine Toleranz (6 px) für Finger."""
        for t in reversed(self.targets):
            if t.enabled and t.rect.contains(x, y):
                return t
        best, best_d = None, None
        for t in reversed(self.targets):
            if not t.enabled:
                continue
            r = t.rect
            dx = max(r.x - x, 0, x - (r.x + r.w - 1))
            dy = max(r.y - y, 0, y - (r.y + r.h - 1))
            d = max(dx, dy)
            if d <= 6 and (best_d is None or d < best_d):
                best, best_d = t, d
        return best


def _overlap(a, b):
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def _contains(outer, inner):
    return (outer.x <= inner.x and outer.y <= inner.y
            and inner.x + inner.w <= outer.x + outer.w and inner.y + inner.h <= outer.y + outer.h)


class Renderer(object):
    def __init__(self, canvas):
        self.canvas = canvas
        self.prev = {}      # rid -> (key, rect, clear)
        self.layer = None   # Kennung der aktuellen Ebene (Seite/Dialog)
        # schwebender Dialog über der stehenden Seite: (seiten_layer, seiten_prev, fläche)
        self.overlay = None

    def invalidate(self):
        self.prev = {}
        self.layer = None
        self.overlay = None

    def render_overlay(self, page_frame, page_layer, frame, layer, area, full_bg='bg'):
        """Dialog über der Seite, ohne sie abzudunkeln: die Seite bleibt stehen, nur
        der Dialog (Fläche ``area``) wird gezeichnet. Beim Schließen stellt
        :meth:`render` nur die Seite unter ``area`` wieder her."""
        if self.layer == layer and self.overlay is not None:
            return self.render(frame, layer)
        if self.overlay is not None and self.overlay[0] == page_layer:
            # anderer Dialog auf derselben Seite: erst die Seite unter dem alten herstellen
            self.render(page_frame, page_layer, full_bg)
        elif self.layer != page_layer:
            self.render(page_frame, page_layer, full_bg)
        self.overlay = (page_layer, self.prev, area)
        self.prev = {}
        self.layer = layer
        return self.render(frame, layer)

    def render(self, frame, layer, full_bg='bg', dim_frame=None, dim=0.84):
        """Zeichnet ``frame``. Wechselt ``layer`` (Seite oder Dialog), wird alles
        neu gezeichnet; mit ``dim_frame`` zuerst die abgedunkelte Seite darunter.
        Gibt die Anzahl neu gezeichneter Regionen zurück."""
        c = self.canvas
        if self.overlay is not None and layer != self.layer:
            page_layer, page_prev, area = self.overlay
            self.overlay = None
            if layer == page_layer:
                # Dialog geschlossen: nur die Fläche darunter neu (Seite stand still)
                self.prev = dict((rid, v) for rid, v in page_prev.items()
                                 if not _overlap(v[1], area))
                self.layer = layer
                c.fill_rect(area, full_bg)
        full = layer != self.layer
        if full:
            self.prev = {}
            self.layer = layer
            if dim_frame is not None:
                c.dim = dim
                c.fill(0, 0, c.WIDTH, c.HEIGHT, full_bg)
                for r in dim_frame.regions:
                    self._paint(r)
                c.dim = 0.0
            else:
                c.fill(0, 0, c.WIDTH, c.HEIGHT, full_bg)
        current = dict((r.rid, r) for r in frame.regions)
        forced = set()
        # 1) weggefallene Regionen löschen, Überlappungen neu zeichnen
        for rid, (key, rect, clear) in list(self.prev.items()):
            if rid not in current:
                c.fill_rect(rect, clear)
                del self.prev[rid]
                for r in frame.regions:
                    if _overlap(r.rect, rect):
                        forced.add(r.rid)
        # 2) geänderte Regionen (und deren Kinder) zeichnen
        # Eine neu gezeichnete Region übermalt alles, was später in der Liste
        # liegt und sie überlappt (Kinder, Toast) -> diese ebenfalls zeichnen.
        drawn = []
        count = 0
        for r in frame.regions:
            old = self.prev.get(r.rid)
            dirty = (full or r.rid in forced or old is None
                     or old[0] != r.key or old[1] != r.rect
                     or any(_overlap(r.rect, d) for d in drawn))
            if not dirty:
                continue
            if (old is not None and old[1] != r.rect and not full
                    and not any(_contains(d, old[1]) for d in drawn)):
                # Liegt die alte Fläche in einer Region, die in diesem Durchlauf
                # schon neu gezeichnet wurde (z. B. der Pillentext in der Pille),
                # ist sie dort bereits richtig gemalt. Mit der alten Löschfarbe
                # gefüllt bliebe sonst ein Rest stehen, wenn die Region kleiner
                # wird ("Druckt · 100 %" -> "9 %").
                c.fill_rect(old[1], old[2])
            self._paint(r)
            self.prev[r.rid] = (r.key, r.rect, r.clear)
            drawn.append(r.rect)
            count += 1
        return count

    def _paint(self, r):
        c = self.canvas
        if r.gaps:
            # 1) aufzeichnen, 2) alles, was nichts deckend übermalt, mit ``clear``
            # füllen, 3) die Befehle senden, ohne Flächen, die ein späterer Befehl
            # ohnehin übermalt (Canvas.play). Text, Flächen und Kreise werden so
            # direkt überschrieben, ohne leeres Feld oder Zwischenfarbe.
            c.record_start()
            try:
                r.paint(c, r.rect)
            finally:
                ops = c.record_stop()
            c.play(r.rect, ops, r.clear)
            return
        if not r.opaque:
            c.fill_rect(r.rect, r.clear)
        r.paint(c, r.rect)
