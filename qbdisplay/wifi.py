# qbdisplay – WLAN einrichten (über das Hilfsskript, das als root läuft)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Netze suchen und verbinden. Die eigentliche Arbeit macht ``qbdisplay-helper
wifi-*`` (wpa_supplicant gehört root). Das Passwort geht nur über stdin an das
Hilfsskript, nie als Argument und nie ins Log."""

import json
import logging

from . import updates

log = logging.getLogger(__name__)

# Gründe aus dem Hilfsskript; 'old_helper': Hilfsskript kennt die Befehle noch nicht
REASONS = ('input', 'auth', 'notfound', 'dhcp', 'busy', 'error', 'old_helper')


def _parse(ok, out):
    """Letzte JSON-Zeile der Ausgabe; None, wenn keine da ist."""
    for line in reversed((out or '').strip().splitlines()):
        line = line.strip()
        if line.startswith('{') or line.startswith('['):
            try:
                return json.loads(line)
            except ValueError:
                break
    return None


def _old_helper(out):
    return 'Aufruf:' in (out or '') and 'wifi' not in (out or '')


def scan():
    """-> (netze, fehler). netze: [{'ssid', 'signal', 'freq', 'kind', 'current'}]"""
    ok, out = updates.helper('wifi-scan', timeout=30)
    res = _parse(ok, out)
    if isinstance(res, list):
        return res, None
    if _old_helper(out):
        return [], 'old_helper'
    log.warning('WLAN-Suche: %s', (out or '').strip()[:200])
    return [], 'error'


def connect(ssid, psk):
    """Netz ausprobieren; bleibt nur bei Erfolg gespeichert (bis ca. 70 s).
    -> {'ok': bool, 'reason': ..., 'ip': ...}"""
    ok, out = updates.helper('wifi-connect', timeout=120, data='%s\n%s\n' % (ssid, psk))
    res = _parse(ok, out)
    if isinstance(res, dict):
        return res
    if _old_helper(out):
        return {'ok': False, 'reason': 'old_helper'}
    # keine Ausgabe ins Log übernehmen, die das Passwort enthalten könnte
    log.warning('WLAN-Verbindung: Hilfsskript ohne Ergebnis (ok=%s)', ok)
    return {'ok': False, 'reason': 'error'}


def signal_bars(level):
    """dBm -> 0..4 Balken"""
    if level is None:
        return 0
    for bars, limit in ((4, -55), (3, -65), (2, -75), (1, -85)):
        if level >= limit:
            return bars
    return 0


def valid_psk(psk):
    """WPA-Passwort: 8..63 druckbare ASCII-Zeichen (oder 64 Hex-Zeichen)."""
    if len(psk) == 64 and all(c in '0123456789abcdefABCDEF' for c in psk):
        return True
    return 8 <= len(psk) <= 63 and all(32 <= ord(c) <= 126 for c in psk)
