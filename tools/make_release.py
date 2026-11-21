#!/usr/bin/env python3
# qbdisplay – Release-Paket für den Drucker bauen
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Packt alles, was auf dem Drucker gebraucht wird, in ``dist/qbdisplay-plus4-<version>.tar.gz``:
Programm, Dienst, Beispielkonfiguration, install.sh/uninstall.sh, Lizenz und die fertige
Display-Datei. Skripte bekommen LF-Zeilenenden und das Ausführungsrecht.

    python tools/make_release.py --tft qbdisplay.tft
"""

import argparse
import hashlib
import io
import os
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from qbdisplay import __version__  # noqa: E402

FILES = ['install.sh', 'uninstall.sh', 'qbdisplay.example.cfg', 'LICENSE', 'systemd/qbdisplay.service',
         'systemd/qbdisplay-helper']
EXEC = {'install.sh', 'uninstall.sh', 'systemd/qbdisplay-helper'}


def add_bytes(tar, name, data, mode=0o644):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    info.mtime = 0
    tar.addfile(info, io.BytesIO(data))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tft', required=True, help='kompilierte Display-Datei')
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    base = 'qbdisplay-plus4-%s' % __version__
    path = os.path.join(args.out, base + '.tar.gz')
    with tarfile.open(path, 'w:gz') as tar:
        for rel in FILES:
            src = os.path.join(ROOT, rel)
            if not os.path.exists(src):
                print('fehlt (übersprungen):', rel)
                continue
            data = open(src, 'rb').read()
            if rel.endswith(('.sh', '.cfg', '.service', '-helper')):
                data = data.replace(b'\r\n', b'\n')
            add_bytes(tar, '%s/%s' % (base, rel), data, 0o755 if rel in EXEC else 0o644)
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, 'qbdisplay')):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for fn in sorted(filenames):
                if fn.endswith('.pyc'):
                    continue
                src = os.path.join(dirpath, fn)
                rel = os.path.relpath(src, ROOT).replace(os.sep, '/')
                add_bytes(tar, '%s/%s' % (base, rel), open(src, 'rb').read().replace(b'\r\n', b'\n'))
        add_bytes(tar, '%s/qbdisplay.tft' % base, open(args.tft, 'rb').read())
    digest = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    print('%s\nsha256 %s' % (path, digest))


if __name__ == '__main__':
    main()
