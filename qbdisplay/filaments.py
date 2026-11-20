# qbdisplay – Materialliste (Format von QIDIs officiall_filas_list.cfg)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Liest die Materialliste des Druckers. Die QIDI-Datei liegt auf dem Gerät
und wird **nicht** mitgeliefert; für Tests/Vorschau gibt es eine eigene kleine
Beispieldatei im selben Format (samples/filas_sample.cfg).

Format (INI):  [filaN] filament=, type=, min_temp=, max_temp=, box_min_temp=,
box_max_temp=;  [colordict] N = #RRGGBB;  [vendor_list] N = Name.
Die Indizes N sind genau die Werte von filament_slotN/color_slotN/vendor_slotN
in saved_variables (so liest es auch QIDI Studio).
"""

import configparser
import logging
import os
import re

log = logging.getLogger(__name__)


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


class FilamentList(object):
    def __init__(self, path=None):
        self.filaments = {}   # idx -> dict
        self.colors = {}      # idx -> '#RRGGBB'
        self.vendors = {}     # idx -> Name
        if path:
            self.load(path)

    def load(self, path):
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            log.warning('Materialliste %s fehlt', path)
            return
        cp = configparser.RawConfigParser(strict=False)
        cp.read(path, encoding='utf-8')
        for sec in cp.sections():
            if sec.startswith('fila') and sec[4:].isdigit():
                d = dict(cp.items(sec))
                for k in ('min_temp', 'max_temp', 'box_min_temp', 'box_max_temp'):
                    try:
                        d[k] = int(float(d.get(k, 0)))
                    except ValueError:
                        d[k] = 0
                self.filaments[int(sec[4:])] = d
            elif sec == 'colordict':
                for k, v in cp.items(sec):
                    if k.isdigit():
                        self.colors[int(k)] = v.strip().upper()
            elif sec == 'vendor_list':
                for k, v in cp.items(sec):
                    if k.isdigit():
                        self.vendors[int(k)] = v.strip()

    # -- Abfragen ------------------------------------------------------------
    def filament_ids(self):
        return sorted(self.filaments)

    def color_ids(self):
        return sorted(self.colors)

    def vendor_ids(self):
        return sorted(self.vendors)

    def name(self, idx):
        f = self.filaments.get(idx)
        return f.get('filament', '') if f else ''

    def ftype(self, idx):
        f = self.filaments.get(idx)
        return f.get('type', '') if f else ''

    def temp_range(self, idx):
        f = self.filaments.get(idx)
        if not f or not f.get('max_temp'):
            return None
        return (f['min_temp'], f['max_temp'])

    def find(self, name=None, material=None):
        """Index zu HH-Namen/Material (Normalisierung: 'PLA Wood' == 'PLA-Wood')."""
        n = _norm(name)
        if n:
            for idx in self.filament_ids():
                if _norm(self.filaments[idx].get('filament')) == n:
                    return idx
        m = _norm(material)
        if m:
            for idx in self.filament_ids():
                if _norm(self.filaments[idx].get('type')) == m:
                    return idx
        return None

    def find_color(self, color):
        from .colors import hex_to_rgb
        rgb = hex_to_rgb(color)
        if rgb is None:
            return None
        best, best_d = None, None
        for idx, val in self.colors.items():
            o = hex_to_rgb(val)
            if o is None:
                continue
            d = sum((a - b) ** 2 for a, b in zip(rgb, o))
            if best_d is None or d < best_d:
                best, best_d = idx, d
        return best

    def find_vendor(self, vendor):
        v = _norm(vendor)
        for idx, name in self.vendors.items():
            if _norm(name) == v:
                return idx
        return None
