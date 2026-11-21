# qbdisplay – Versionen und Update-Prüfung
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Installierte QIDI-Firmware lesen und nach neueren Versionen suchen.

QIDI-Firmware: zuerst wie QIDIs Display-Programm über die Versionsdatei auf QIDIs
Download-Server, sonst über die Releases von QIDITECH/QIDI_PLUS4 auf GitHub.
qbdisplay: Releases des eigenen GitHub-Repositorys. Nur lesende HTTP-GETs; installiert
wird nichts. Für Root-Aktionen gibt es genau ein Hilfsskript (``HELPER``), das
install.sh per sudoers-Regel ohne Passwort freigibt.
"""

import json
import logging
import re
import subprocess
import urllib.request

log = logging.getLogger(__name__)

HELPER = '/usr/local/sbin/qbdisplay-helper'
QIDI_VERSION_URLS = (
    'https://download_aws.qidi3dprinter.com/QD_Plus4/version',
    'https://download_aliyun.qidi3dprinter.com/QD_Plus4/version',
)
QIDI_GITHUB = 'QIDITECH/QIDI_PLUS4'
TIMEOUT = 8

_VER = re.compile(r'(\d+)\.(\d+)\.(\d+)')


def parse_version(text):
    """'V2.1.1', 'Plus4_v2.1.1', 'v0.2.0' -> (2, 1, 1); sonst None."""
    m = _VER.search(str(text or ''))
    return tuple(int(x) for x in m.groups()) if m else None


def fmt(ver):
    return '.'.join(str(x) for x in ver) if ver else '–'


def newer(remote, local):
    return bool(remote and local and remote > local)


def parse_ini(text):
    """[version]-Abschnitt von /root/xindi/version -> {'soc': 'V2.1.1', ...}"""
    out = {}
    for line in str(text or '').splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            out[k.strip().lower()] = v.strip()
    return out


def helper(*args, timeout=15):
    """Hilfsskript über sudo -n; liefert (ok, ausgabe)."""
    try:
        res = subprocess.run(['sudo', '-n', HELPER] + list(args), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return res.returncode == 0, res.stdout.decode('utf-8', 'replace')


def local_qidi():
    """{'soc': 'V2.1.1', 'ui': 'V211', 'mcu': ...} oder {} ohne Rechte/Datei."""
    ok, out = helper('version')
    return parse_ini(out) if ok else {}


def _get(url, accept='application/json'):
    req = urllib.request.Request(url, headers={'Accept': accept, 'User-Agent': 'qbdisplay',
                                               'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode('utf-8', 'replace')


def remote_qidi():
    """(version, quelle) der neuesten QIDI-Firmware oder (None, fehlertext)."""
    for url in QIDI_VERSION_URLS:
        try:
            text = _get(url, 'text/plain')
        except Exception as e:   # noqa: Server oft nicht erreichbar
            log.info('QIDI-Versionsserver %s: %s', url, e)
            continue
        ini = parse_ini(text)
        ver = parse_version(ini.get('soc') or text)
        if ver:
            return ver, 'QIDI'
    try:
        data = json.loads(_get('https://api.github.com/repos/%s/releases/latest' % QIDI_GITHUB))
        ver = parse_version(data.get('tag_name'))
        if ver:
            return ver, 'GitHub'
    except Exception as e:   # noqa: kein Netz
        log.info('QIDI-Releases auf GitHub: %s', e)
        return None, str(e)
    return None, 'keine Version gefunden'


def remote_self(repo):
    """Neueste qbdisplay-Version aus den GitHub-Releases von ``repo`` oder None."""
    if not repo:
        return None
    try:
        data = json.loads(_get('https://api.github.com/repos/%s/releases/latest' % repo))
        return parse_version(data.get('tag_name'))
    except Exception as e:   # noqa: kein Netz
        log.info('qbdisplay-Releases auf GitHub: %s', e)
        return None


def check(repo, own_version):
    """Komplette Prüfung (läuft in einem eigenen Thread). -> dict für die Anzeige."""
    local = local_qidi()
    lver = parse_version(local.get('soc'))
    rver, source = remote_qidi()
    sver = remote_self(repo)
    own = parse_version(own_version)
    return {
        'qidi_local': lver, 'qidi_remote': rver, 'qidi_source': source,
        'qidi_newer': newer(rver, lver),
        'self_local': own, 'self_remote': sver, 'self_newer': newer(sver, own),
        'helper': bool(local),
    }


def switch_to_qidi():
    """Wechsel zur QIDI-Oberfläche anstoßen. -> (ok, meldung)"""
    return helper('to-qidi', timeout=20)
