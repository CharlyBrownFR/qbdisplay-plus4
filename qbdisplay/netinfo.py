# qbdisplay – Netzwerk- und Cloud-Status
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Liest IP, Verbindungsart und WLAN-Qualität aus /sys und /proc und prüft,
ob Cloud-Teile laufen (Prozesse ``frpc``, ``xindi``, ``udp_server``;
Moonraker-Komponenten ``mqtt``/``frp_manager``). "Nur LAN" gilt, wenn nichts
davon aktiv ist (siehe docs/findings.md, Abschnitt Cloud/Netzwerk)."""

import os
import socket

from .i18n import N_

CLOUD_PROCS = ('frpc', 'xindi', 'udp_server')


def primary_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))      # sendet nichts, wählt nur die Route
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _read(path):
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except OSError:
        return ''


def iface_kind(sys_net='/sys/class/net'):
    try:
        names = sorted(os.listdir(sys_net))
    except OSError:
        return None, None
    for name in names:
        if name == 'lo':
            continue
        if _read(os.path.join(sys_net, name, 'operstate')) != 'up':
            continue
        if os.path.isdir(os.path.join(sys_net, name, 'wireless')) or name.startswith('wl'):
            return 'wifi', name
    for name in names:
        if name != 'lo' and _read(os.path.join(sys_net, name, 'operstate')) == 'up':
            return 'ethernet', name
    return None, None


def wifi_quality(iface, proc='/proc/net/wireless'):
    """-> 'gut' | 'mittel' | 'schwach' | None (Link-Qualität x/70; deutsch, die
    Oberfläche übersetzt beim Anzeigen)."""
    for line in _read(proc).splitlines():
        if line.strip().startswith(iface + ':'):
            parts = line.split()
            try:
                q = float(parts[2].rstrip('.'))
            except (IndexError, ValueError):
                return None
            return N_('gut') if q >= 45 else (N_('mittel') if q >= 25 else N_('schwach'))
    return None


def running_processes(names, proc='/proc'):
    found = set()
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return found
    for pid in pids:
        comm = _read(os.path.join(proc, pid, 'comm'))
        if comm in names:
            found.add(comm)
    return found


def gather(components=()):
    kind, iface = iface_kind()
    procs = running_processes(CLOUD_PROCS)
    comps = set(components or ())
    cloud = bool('xindi' in procs or 'mqtt' in comps)
    tunnel = bool('frpc' in procs or 'frp_manager' in comps)
    return {
        'ip': primary_ip(),
        'iface_kind': kind,
        'iface': iface,
        'quality': wifi_quality(iface) if kind == 'wifi' else None,
        'lan_only': not (cloud or tunnel),
        'services': (
            ('cloudoff', N_('QIDI-Cloud / App'), N_('läuft') if cloud else N_('blockiert')),
            ('link', N_('Fernzugriff (QIDI Link)'), N_('läuft') if tunnel else N_('blockiert')),
            ('monitor', N_('Slicer & Browser im LAN'), N_('aktiv')),
        ),
    }
