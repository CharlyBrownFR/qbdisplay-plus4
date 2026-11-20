# qbdisplay – Moonraker-Client (JSON-RPC über Unix-Socket, HTTP-Fallback)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Moonraker-Anbindung mit Threads (Python 3.7, nur Standardbibliothek).

Unix-Socket ``~/printer_data/comms/moonraker.sock``: JSON-RPC 2.0, jede
Nachricht endet mit dem Byte 0x03. Ablauf: ``server.connection.identify`` ->
``server.info`` (wartet bis Klippy "ready") -> ``printer.objects.subscribe``.
Danach kommen ``notify_status_update``-Benachrichtigungen.

Fallback (Socket fehlt): JSON-RPC per HTTP-POST an ``/server/jsonrpc`` und
Status-Abfrage im Sekundentakt.

Alle Ereignisse gehen über ``on_event(art, daten)`` an die Hauptschleife;
Rückrufe von Anfragen ebenfalls (art = 'callback'), damit die Oberfläche nur
in einem Thread läuft.
"""

import itertools
import json
import logging
import os
import socket
import threading
import time

log = logging.getLogger(__name__)

ETX = b'\x03'


class RpcError(Exception):
    pass


class _Base(object):
    def __init__(self, on_event, objects):
        self.on_event = on_event
        self.objects = objects
        self._ids = itertools.count(1)
        self._pending = {}
        self._lock = threading.Lock()
        self._stop = False
        self.connected = False
        self.klippy_ready = False

    def _callback(self, cb, result, error):
        if cb is not None:
            self.on_event('callback', (cb, result, error))

    def gcode(self, script, cb=None):
        self.call('printer.gcode.script', {'script': script}, cb)

    def stop(self):
        self._stop = True


class MoonrakerSocketClient(_Base):
    def __init__(self, path, on_event, objects, client_name='qbdisplay', version='0'):
        _Base.__init__(self, on_event, objects)
        self.path = os.path.expanduser(path)
        self.client_name = client_name
        self.version = version
        self.sock = None
        self._send_lock = threading.Lock()

    # -- Öffentlich ---------------------------------------------------------
    def start(self):
        t = threading.Thread(target=self._run, name='moonraker')
        t.daemon = True
        t.start()

    def call(self, method, params=None, cb=None):
        rid = next(self._ids)
        msg = {'jsonrpc': '2.0', 'method': method, 'id': rid}
        if params is not None:
            msg['params'] = params
        with self._lock:
            self._pending[rid] = cb
        if not self._send(msg):
            with self._lock:
                self._pending.pop(rid, None)
            self._callback(cb, None, 'keine Verbindung zu Moonraker')
        return rid

    def call_sync(self, method, params=None, timeout=10.0):
        """Blockierender Aufruf (nur aus dem Verbindungs-Thread benutzen)."""
        ev = threading.Event()
        box = {}

        def done(result, error):
            box['r'], box['e'] = result, error
            ev.set()
        rid = next(self._ids)
        msg = {'jsonrpc': '2.0', 'method': method, 'id': rid}
        if params is not None:
            msg['params'] = params
        with self._lock:
            self._pending[rid] = ('sync', done)
        self._send(msg)
        if not ev.wait(timeout):
            with self._lock:
                self._pending.pop(rid, None)
            raise RpcError('Zeitüberschreitung bei %s' % method)
        if box.get('e'):
            raise RpcError(box['e'])
        return box.get('r')

    # -- Intern ---------------------------------------------------------------
    def _send(self, msg):
        data = json.dumps(msg).encode('utf-8') + ETX
        with self._send_lock:
            if self.sock is None:
                return False
            try:
                self.sock.sendall(data)
                return True
            except OSError:
                log.warning('Senden an Moonraker fehlgeschlagen')
                return False

    def _run(self):
        delay = 1.0
        while not self._stop:
            try:
                self._connect()
                delay = 1.0
                self._session()
            except Exception as e:   # noqa: Verbindungsfehler aller Art
                log.info('Moonraker: %s', e)
            self._disconnect()
            time.sleep(delay)
            delay = min(10.0, delay * 1.5)

    def _connect(self):
        if not hasattr(socket, 'AF_UNIX'):
            raise RpcError('AF_UNIX nicht verfügbar')
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.path)
        self.sock = s
        reader = threading.Thread(target=self._reader, args=(s,), name='moonraker-rx')
        reader.daemon = True
        reader.start()

    def _disconnect(self):
        was = self.connected
        self.connected = False
        self.klippy_ready = False
        with self._send_lock:
            if self.sock is not None:
                try:
                    self.sock.close()
                except OSError:
                    pass
                self.sock = None
        with self._lock:
            pending, self._pending = self._pending, {}
        for cb in pending.values():
            if isinstance(cb, tuple):
                cb[1](None, 'Verbindung getrennt')
            else:
                self._callback(cb, None, 'Verbindung getrennt')
        if was:
            self.on_event('disconnected', None)

    def _session(self):
        self.call_sync('server.connection.identify', {
            'client_name': self.client_name, 'version': self.version,
            'type': 'display', 'url': 'https://github.com/'})
        self.connected = True
        self.on_event('connected', None)
        self._wait_klippy_and_subscribe()
        while not self._stop and self.sock is not None:
            time.sleep(1.0)
            if not self.klippy_ready:
                self._wait_klippy_and_subscribe()

    def _wait_klippy_and_subscribe(self):
        while not self._stop and self.sock is not None:
            info = self.call_sync('server.info')
            state = info.get('klippy_state')
            self.on_event('server_info', info)
            if state == 'ready':
                res = self.call_sync('printer.objects.subscribe', {'objects': self.objects})
                self.klippy_ready = True
                self.on_event('status_full', res.get('status', {}))
                return
            self.on_event('klippy_state', state)
            time.sleep(2.0)

    def _reader(self, s):
        buf = b''
        while True:
            try:
                chunk = s.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while ETX in buf:
                raw, buf = buf.split(ETX, 1)
                if raw:
                    self._dispatch(raw)
        # Lese-Ende -> Sitzung beenden
        with self._send_lock:
            if self.sock is s:
                try:
                    s.close()
                except OSError:
                    pass
                self.sock = None

    def _dispatch(self, raw):
        try:
            msg = json.loads(raw.decode('utf-8'))
        except ValueError:
            log.warning('Moonraker: ungültiges JSON')
            return
        if 'id' in msg and ('result' in msg or 'error' in msg):
            with self._lock:
                cb = self._pending.pop(msg['id'], None)
            err = msg.get('error')
            err_text = (err.get('message') if isinstance(err, dict) else str(err)) if err else None
            if isinstance(cb, tuple):
                cb[1](msg.get('result'), err_text)
            else:
                self._callback(cb, msg.get('result'), err_text)
            return
        handle_notification(self, msg.get('method'), msg.get('params') or [])


def handle_notification(client, method, params):
    if method == 'notify_status_update':
        if params:
            client.on_event('status', params[0])
    elif method == 'notify_gcode_response':
        if params:
            client.on_event('gcode_response', params[0])
    elif method == 'notify_klippy_ready':
        client.klippy_ready = False      # neu abonnieren
    elif method in ('notify_klippy_shutdown', 'notify_klippy_disconnected'):
        client.klippy_ready = False
        client.on_event('klippy_state', 'shutdown' if 'shutdown' in method else 'disconnected')
    elif method == 'notify_filelist_changed':
        client.on_event('files_changed', None)
    elif method == 'notify_history_changed':
        client.on_event('history_changed', None)


class MoonrakerHttpClient(_Base):
    """Notlösung ohne Socket: JSON-RPC über HTTP + Status-Abfrage (1 Hz)."""

    def __init__(self, url, on_event, objects, interval=1.0):
        _Base.__init__(self, on_event, objects)
        self.url = url.rstrip('/')
        self.interval = interval
        self._queue = []
        self._cond = threading.Condition()

    def start(self):
        for target in (self._poller, self._worker):
            t = threading.Thread(target=target, name='moonraker-http')
            t.daemon = True
            t.start()

    def _post(self, method, params=None, timeout=30.0):
        from urllib.request import Request, urlopen
        body = json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params or {},
                           'id': next(self._ids)}).encode('utf-8')
        req = Request(self.url + '/server/jsonrpc', data=body,
                      headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=timeout) as resp:
            msg = json.loads(resp.read().decode('utf-8'))
        if msg.get('error'):
            err = msg['error']
            raise RpcError(err.get('message') if isinstance(err, dict) else str(err))
        return msg.get('result')

    def call(self, method, params=None, cb=None):
        with self._cond:
            self._queue.append((method, params, cb))
            self._cond.notify()

    def _worker(self):
        while not self._stop:
            with self._cond:
                while not self._queue:
                    self._cond.wait(1.0)
                    if self._stop:
                        return
                method, params, cb = self._queue.pop(0)
            try:
                res = self._post(method, params, timeout=3600.0 if 'gcode' in method else 30.0)
                self._callback(cb, res, None)
            except Exception as e:   # noqa
                self._callback(cb, None, str(e))

    def _poller(self):
        while not self._stop:
            try:
                info = self._post('server.info', timeout=5.0)
                if not self.connected:
                    self.connected = True
                    self.on_event('connected', None)
                self.on_event('server_info', info)
                if info.get('klippy_state') == 'ready':
                    res = self._post('printer.objects.query', {'objects': self.objects}, 5.0)
                    first = not self.klippy_ready
                    self.klippy_ready = True
                    self.on_event('status_full' if first else 'status', res.get('status', {}))
                else:
                    self.klippy_ready = False
                    self.on_event('klippy_state', info.get('klippy_state'))
            except Exception as e:   # noqa
                if self.connected:
                    log.info('Moonraker (HTTP): %s', e)
                    self.connected = False
                    self.on_event('disconnected', None)
            time.sleep(self.interval)


def make_client(cfg, on_event, objects, version='0'):
    path = os.path.expanduser(cfg.get('moonraker', 'socket'))
    if path and os.path.exists(path) and hasattr(socket, 'AF_UNIX'):
        return MoonrakerSocketClient(path, on_event, objects, version=version)
    log.warning('Moonraker-Socket %s fehlt – nutze HTTP %s', path, cfg.get('moonraker', 'http'))
    return MoonrakerHttpClient(cfg.get('moonraker', 'http'), on_event, objects)
