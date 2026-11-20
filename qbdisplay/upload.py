# qbdisplay – .tft-Datei über die serielle Leitung auf das Display laden
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Upload-Protokoll ``whmi-wri`` (TJC/Nextion):

1. Verbindung prüfen: ``connect`` -> Display antwortet ``comok ...``
   (enthält das Modell, z. B. TJC8048X250_011C).
2. ``whmi-wri <dateigröße>,<upload-baud>,0`` -> Display stellt auf die
   Upload-Baudrate um und meldet 0x05.
3. Datei in Blöcken zu 4096 Byte senden, nach jedem Block auf 0x05 warten.
4. Nach dem letzten Block startet das Display mit der neuen Oberfläche neu.

Vorher MUSS die Display-Software gestoppt sein (``sudo systemctl stop
qbdisplay`` bzw. ``makerbase-client``), sonst stören sich beide Programme.

    python3 -m qbdisplay.upload qbdisplay.tft [--port /dev/ttyS1] [--baud 115200]
                                [--upload-baud 921600]
"""

import argparse
import os
import sys
import time

from .tjc import TERM, open_serial

CHUNK = 4096


def _read_until(port, pred, timeout):
    buf = b''
    end = time.time() + timeout
    while time.time() < end:
        data = port.read(256)
        if data:
            buf += data
            if pred(buf):
                return buf
    return buf


def connect(port, bauds):
    """-> (baud, comok-Text) oder (None, None)."""
    for baud in bauds:
        port.set_baud(baud)
        time.sleep(0.05)
        port.flush_input()
        port.write(b'DRAKJHSUYDGBNCJHGJKSHBDN' + TERM)
        port.write(b'connect' + TERM)
        resp = _read_until(port, lambda b: b'comok' in b and b.rstrip().endswith(TERM), 0.6)
        if b'comok' in resp:
            text = resp[resp.index(b'comok'):].split(TERM)[0].decode('latin-1', 'replace')
            return baud, text
    return None, None


def upload(path, port_name='/dev/ttyS1', bauds=(115200, 9600, 921600, 256000, 512000),
           upload_baud=921600, port_factory=open_serial, log=print):
    size = os.path.getsize(path)
    port = port_factory(port_name, bauds[0])
    try:
        baud, info = connect(port, bauds)
        if baud is None:
            raise RuntimeError('Display antwortet nicht auf "connect"')
        log('Display gefunden (%d Baud): %s' % (baud, info))
        port.write(('whmi-wri %d,%d,0' % (size, upload_baud)).encode('ascii') + TERM)
        time.sleep(0.1)
        port.set_baud(upload_baud)
        resp = _read_until(port, lambda b: b'\x05' in b, 3.0)
        if b'\x05' not in resp:
            raise RuntimeError('Display bestätigt den Upload nicht (Antwort %r)' % resp)
        sent = 0
        t0 = time.time()
        with open(path, 'rb') as f:
            while True:
                block = f.read(CHUNK)
                if not block:
                    break
                port.write(block)
                sent += len(block)
                resp = _read_until(port, lambda b: b'\x05' in b, 5.0)
                if b'\x05' not in resp:
                    raise RuntimeError('Keine Quittung nach %d Bytes' % sent)
                if sent % (CHUNK * 64) == 0 or sent == size:
                    rate = sent / max(0.1, time.time() - t0)
                    log('%5.1f %%  (%d KB/s)' % (100.0 * sent / size, rate / 1024))
        log('Fertig - Display startet neu.')
    finally:
        port.close()


def main(argv=None):
    ap = argparse.ArgumentParser(prog='qbdisplay.upload')
    ap.add_argument('tft')
    ap.add_argument('--port', default='/dev/ttyS1')
    ap.add_argument('--baud', type=int, default=115200, help='aktuelle Baudrate (wird sonst gesucht)')
    ap.add_argument('--upload-baud', type=int, default=921600)
    args = ap.parse_args(argv)
    bauds = [args.baud] + [b for b in (115200, 9600, 921600, 256000, 512000) if b != args.baud]
    try:
        upload(args.tft, args.port, bauds, args.upload_baud)
    except Exception as e:   # noqa
        print('FEHLER:', e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
