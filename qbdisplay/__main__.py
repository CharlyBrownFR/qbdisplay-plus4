# qbdisplay – Startpunkt: python3 -m qbdisplay [-c qbdisplay.cfg]
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Startet Display-Treiber, Moonraker-Client und Hauptschleife."""

import argparse
import logging
import sys

from . import __version__
from . import fonts
from .app import App, subscribe_objects
from .config import Config
from .moonraker import make_client
from .tjc import TjcDisplay

log = logging.getLogger('qbdisplay')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='qbdisplay', description='Display-Software für QIDI Plus4')
    ap.add_argument('-c', '--config', default=None, help='Pfad zu qbdisplay.cfg')
    ap.add_argument('--port', help='serielle Schnittstelle (Vorgabe aus der Konfiguration)')
    ap.add_argument('--baud', type=int, help='Start-Baudrate')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    cfg = Config(args.config)
    fonts.set_monospace(cfg.getbool('display', 'monospace_fonts'))
    port = args.port or cfg.get('display', 'port')
    baud = args.baud or cfg.getint('display', 'baud')
    log.info('qbdisplay %s, Display %s @ %d', __version__, port, baud)

    disp = TjcDisplay(port, baud, encoding=cfg.get('display', 'encoding'),
                      window=cfg.getint('display', 'window'))
    app = App(cfg, disp, rpc=None, display=disp)
    disp.on_event = app.on_display_event
    disp.open()
    found = disp.detect_baud()
    if found is None:
        log.error('Display antwortet nicht (Kabel, Port, TJC-Datei?) - sende trotzdem mit %d', baud)
        disp.port.set_baud(baud)
        disp.baud = baud
    target = cfg.getint('display', 'target_baud')
    if found is not None and target and target != disp.baud:
        if disp.change_baud(target):
            log.info('Baudrate auf %d umgestellt', target)
        else:
            log.warning('Umstellung auf %d fehlgeschlagen', target)
    disp.init_display(cfg.getint('display', 'sleep_after'))
    disp.send('dim=%d' % max(10, min(100, cfg.getint('display', 'brightness'))))
    app.versions['display'] = 'TJC @ %d Baud' % disp.baud

    rpc = make_client(cfg, app.on_rpc_event, subscribe_objects(cfg), version=__version__)
    app.rpc = rpc
    app.connected = False
    rpc.start()
    try:
        app.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        rpc.stop()
        disp.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
