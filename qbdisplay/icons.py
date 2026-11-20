# qbdisplay – Icon-Verzeichnis (Bild-IDs der TJC-Datei)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Icons sind Bilder in der TJC-Datei. TJC-Bilder haben keine Transparenz,
deshalb gibt es jedes Icon in genau den Kombinationen (Name, Größe,
Vordergrund-Token, Hintergrund-Token), die die Oberfläche benutzt.

Die Liste steht in ``icons_manifest.py`` und wird von tools/make_icons.py
gepflegt (neue Kombinationen werden **hinten angehängt**, damit vorhandene
Bild-IDs stabil bleiben). Bild-ID = Position in der Liste. Die PNG-Dateien
liegen in tjc-projekt/icons/ und heißen ``NNN_name_größe_fg_bg.png``.
"""

try:
    from .icons_manifest import MANIFEST
except ImportError:   # pragma: no cover
    MANIFEST = []

_index = {}
_by_name = {}


def _rebuild():
    _index.clear()
    _by_name.clear()
    for pid, entry in enumerate(MANIFEST):
        key = tuple(entry)
        _index.setdefault(key, pid)
        _by_name.setdefault(key[:3], []).append((key[3], pid))


def set_manifest(entries):
    """Nur für Werkzeuge/Tests: Liste ersetzen."""
    del MANIFEST[:]
    MANIFEST.extend(tuple(e) for e in entries)
    _rebuild()


def lookup(name, size, fg, bg):
    return _index.get((name, int(size), fg, bg))


def lookup_fallback(name, size, fg, bg):
    """Gleiches Icon/Größe/Farbe auf anderem Hintergrund (Notlösung)."""
    cands = _by_name.get((name, int(size), fg))
    return cands[0][1] if cands else None


def filename(pid):
    name, size, fg, bg = MANIFEST[pid]
    return '%03d_%s_%d_%s_%s.png' % (pid, name, size, fg, bg)


_rebuild()
