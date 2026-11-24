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
qbdisplay: Releases des eigenen GitHub-Repositorys. Die Prüfung liest nur;
installiert wird erst auf Knopfdruck (install_release). Für Root-Aktionen gibt es genau ein Hilfsskript (``HELPER``), das
install.sh per sudoers-Regel ohne Passwort freigibt.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
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


def helper(*args, timeout=15, data=None):
    """Hilfsskript über sudo -n; liefert (ok, ausgabe). ``data`` geht über stdin."""
    try:
        res = subprocess.run(['sudo', '-n', HELPER] + list(args), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=timeout,
                             input=data.encode('utf-8') if data is not None else None,
                             stdin=subprocess.DEVNULL if data is None else None)
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


def _release_data(repo, prerelease=False):
    """GitHub-Daten des neuesten Releases. Mit ``prerelease`` zählen auch
    Vorabversionen (zum Testen am eigenen Drucker), Entwürfe nie."""
    if not prerelease:
        return json.loads(_get('https://api.github.com/repos/%s/releases/latest' % repo))
    rels = json.loads(_get('https://api.github.com/repos/%s/releases?per_page=20' % repo))
    best = None
    for r in rels if isinstance(rels, list) else []:
        ver = parse_version(r.get('tag_name'))
        if r.get('draft') or not ver:
            continue
        if best is None or ver > parse_version(best.get('tag_name')):
            best = r
    if best is None:
        raise ValueError('keine Releases gefunden')
    return best


def remote_self(repo, prerelease=False):
    """(version, ist_vorabversion) des neuesten qbdisplay-Releases oder (None, False)."""
    if not repo:
        return None, False
    try:
        data = _release_data(repo, prerelease)
        return parse_version(data.get('tag_name')), bool(data.get('prerelease'))
    except Exception as e:   # noqa: kein Netz
        log.info('qbdisplay-Releases auf GitHub: %s', e)
        return None, False


def latest_release(repo, prerelease=False):
    """Neuestes Release mit Paket: {'version', 'tag', 'name', 'url', 'sha256', 'size'}.

    Die Prüfsumme liefert GitHub selbst (Feld ``digest`` des Assets)."""
    data = _release_data(repo, prerelease)
    ver = parse_version(data.get('tag_name'))
    for a in data.get('assets') or []:
        name = a.get('name') or ''
        digest = a.get('digest') or ''
        if (name.startswith('qbdisplay-plus4-') and name.endswith('.tar.gz')
                and digest.startswith('sha256:')):
            return {'version': ver, 'tag': data.get('tag_name'), 'name': name,
                    'url': a.get('browser_download_url'), 'sha256': digest[7:].lower(),
                    'size': int(a.get('size') or 0)}
    raise ValueError('Release %s ohne geprüftes Paket' % data.get('tag_name'))


class UpdateError(Exception):
    pass


def _download(url, path, size_limit=50 * 1024 * 1024):
    req = urllib.request.Request(url, headers={'User-Agent': 'qbdisplay'})
    h = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(path, 'wb') as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > size_limit:
                raise UpdateError('Paket zu groß')
            h.update(chunk)
            f.write(chunk)
    return h.hexdigest(), total


def _safe_extract(tar_path, dest):
    """Entpackt nur normale Dateien/Ordner unterhalb von ``dest`` (keine Links,
    keine absoluten Pfade, kein '..'). -> Name des obersten Ordners."""
    top = None
    with tarfile.open(tar_path, 'r:gz') as tf:
        members = tf.getmembers()
        for m in members:
            parts = m.name.replace('\\', '/').split('/')
            if m.name.startswith('/') or '..' in parts:
                raise UpdateError('unsicherer Pfad im Paket: %s' % m.name)
            if not (m.isfile() or m.isdir()):
                raise UpdateError('Link/Sonderdatei im Paket: %s' % m.name)
            if top is None:
                top = parts[0]
            elif parts[0] != top:
                raise UpdateError('Paket hat mehrere Hauptordner')
        # neuere Python-Versionen prüfen zusätzlich selbst (am Drucker läuft 3.7)
        opts = {'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}
        for m in members:
            tf.extract(m, dest, **opts)
    return top


def fetch_release(rel, workdir):
    """Paket laden, Prüfsumme/Größe prüfen, entpacken, Inhalt prüfen.

    -> Pfad des entpackten Ordners (``workdir/qbdisplay-plus4-X.Y.Z``).
    Bei jedem Fehler UpdateError; halbe Downloads werden entfernt."""
    os.makedirs(workdir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix='.tar.gz', dir=workdir)
    os.close(fd)
    stage = tempfile.mkdtemp(prefix='stage-', dir=workdir)
    try:
        digest, size = _download(rel['url'], tmp)
        if digest != rel['sha256']:
            raise UpdateError('Prüfsumme falsch')
        if rel.get('size') and size != rel['size']:
            raise UpdateError('Größe falsch')
        top = _safe_extract(tmp, stage)
        src = os.path.join(stage, top)
        for need in ('install.sh', 'qbdisplay.tft', os.path.join('qbdisplay', '__init__.py')):
            if not os.path.isfile(os.path.join(src, need)):
                raise UpdateError('%s fehlt im Paket' % need)
        with open(os.path.join(src, 'qbdisplay', '__init__.py'), encoding='utf-8') as f:
            m = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)', f.read())
        if not m or parse_version(m.group(1)) != rel['version']:
            raise UpdateError('Version im Paket passt nicht zum Release')
        final = os.path.join(workdir, top)
        if os.path.exists(final):
            shutil.rmtree(final)
        os.rename(src, final)
        return final
    except UpdateError:
        raise
    except Exception as e:
        raise UpdateError(str(e))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if os.path.exists(tmp):
            os.remove(tmp)


UPDATE_DIR = os.path.expanduser('~/qbdisplay-updates')
STATUS_FILE = os.path.expanduser('~/qbdisplay-backup/update-status')


def install_release(repo, workdir=UPDATE_DIR, prerelease=False):
    """Neuestes Release laden, prüfen und die Installation über das Hilfsskript starten.

    -> ('started', version) | ('manual', text) | ('error', text).
    Bei 'started' beendet das Hilfsskript qbdisplay gleich selbst; das Ergebnis steht
    danach in STATUS_FILE (siehe read_status)."""
    try:
        rel = latest_release(repo, prerelease)
        path = fetch_release(rel, workdir)
    except Exception as e:   # noqa: Netz, Prüfsumme, Paket
        log.warning('Update laden: %s', e)
        return 'error', str(e)
    ok, out = helper('update', path, timeout=60)
    out = out.strip()
    if ok:
        return 'started', rel['version']
    if out.startswith('manual'):
        return 'manual', out.split(':', 1)[-1].strip()
    log.warning('Update starten: %s', out)
    return 'error', out or 'Hilfsskript fehlgeschlagen'


def read_status(path=STATUS_FILE):
    """Ergebnis des letzten Updates: {'state', 'from', 'to', 'time', 'message'} oder {}."""
    try:
        with open(path, encoding='utf-8') as f:
            return dict(line.split('=', 1) for line in f.read().splitlines() if '=' in line)
    except OSError:
        return {}


def clear_status(path=STATUS_FILE):
    try:
        os.remove(path)
    except OSError:
        pass


def check(repo, own_version, prerelease=False):
    """Komplette Prüfung (läuft in einem eigenen Thread). -> dict für die Anzeige."""
    local = local_qidi()
    lver = parse_version(local.get('soc'))
    rver, source = remote_qidi()
    sver, spre = remote_self(repo, prerelease)
    own = parse_version(own_version)
    return {
        'qidi_local': lver, 'qidi_remote': rver, 'qidi_source': source,
        'qidi_newer': newer(rver, lver),
        'self_local': own, 'self_remote': sver, 'self_newer': newer(sver, own),
        'self_prerelease': spre,
        'helper': bool(local),
    }


def switch_to_qidi():
    """Wechsel zur QIDI-Oberfläche anstoßen. -> (ok, meldung)"""
    return helper('to-qidi', timeout=20)
