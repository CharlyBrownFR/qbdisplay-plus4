# qbdisplay – Treiber für TJC/Nextion-Displays
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""TJC-Protokoll (Nextion-kompatibel).

Host -> Display: ASCII-Befehle, jeweils mit 0xFF 0xFF 0xFF abgeschlossen.
Display -> Host: Rückmeldungen mit Code-Byte, Nutzdaten und 0xFF 0xFF 0xFF.

Wichtige Rückmeldungen (Nextion Instruction Set, "Return Codes"):
  0x00 ungültiger Befehl ... 0x24 Puffer übergelaufen (ohne Nutzdaten)
  0x01 Befehl ausgeführt (bei bkcmd=1/3)
  0x00 0x00 0x00 FF FF FF  Display gestartet
  0x88 bereit, 0x86 eingeschlafen, 0x87 aufgewacht
  0x65 Seite, Komponente, Ereignis       (Komponenten-Touch)
  0x66 Seite                             (Antwort auf sendme)
  0x67 xH xL yH yL Ereignis              (Touch-Koordinate, bei sendxy=1)
  0x68 xH xL yH yL Ereignis              (Touch-Koordinate im Schlafmodus)
  0x70 Text, 0x71 Zahl (4 Byte little-endian)
Ereignis: 0x01 = gedrückt, 0x00 = losgelassen.

Flusskontrolle: Mit ``bkcmd=3`` quittiert das Display jeden Befehl (0x01 oder
Fehlercode). Der Sender hält höchstens ``window`` Befehle gleichzeitig offen,
damit der Eingangspuffer des Displays (laut Nextion 1 KB) nicht überläuft.
Bleiben Quittungen aus, wird nach einer Zeitschranke weitergesendet und auf
reine Ratenbegrenzung (Bytes pro Sekunde aus der Baudrate) umgeschaltet.
"""

import collections
import logging
import os
import struct
import threading
import time

log = logging.getLogger(__name__)

TERM = b'\xff\xff\xff'

# Codes ohne Nutzdaten
SIMPLE_CODES = {
    0x00: 'invalid_instruction', 0x01: 'ok', 0x02: 'invalid_component',
    0x03: 'invalid_page', 0x04: 'invalid_picture', 0x05: 'invalid_font',
    0x06: 'invalid_file_operation', 0x09: 'invalid_crc', 0x11: 'invalid_baud',
    0x12: 'invalid_waveform', 0x1A: 'invalid_variable', 0x1B: 'invalid_operation',
    0x1C: 'assignment_failed', 0x1D: 'eeprom_failed', 0x1E: 'invalid_param_count',
    0x1F: 'io_failed', 0x20: 'invalid_escape', 0x23: 'name_too_long',
    0x24: 'buffer_overflow', 0x86: 'sleep', 0x87: 'wake', 0x88: 'ready',
    0x89: 'sd_upgrade', 0xFD: 'transparent_done', 0xFE: 'transparent_ready',
}
# Codes mit fester Nutzdatenlänge
FIXED_CODES = {0x65: 3, 0x66: 1, 0x67: 5, 0x68: 5, 0x71: 4}
# Quittungen (zählen für die Flusskontrolle)
ACK_CODES = set(c for c in SIMPLE_CODES if c < 0x80)

MAX_STRING = 1024


# ---------------------------------------------------------------------------
# Ereignisse
# ---------------------------------------------------------------------------
TouchEvent = collections.namedtuple('TouchEvent', 'x y pressed asleep')
ComponentEvent = collections.namedtuple('ComponentEvent', 'page component pressed')
PageEvent = collections.namedtuple('PageEvent', 'page')
NumberEvent = collections.namedtuple('NumberEvent', 'value')
StringEvent = collections.namedtuple('StringEvent', 'text')
AckEvent = collections.namedtuple('AckEvent', 'code name')
SystemEvent = collections.namedtuple('SystemEvent', 'name')   # startup, ready, sleep, wake, ...


def encode_command(cmd, encoding='iso-8859-1'):
    """Befehl -> Bytes inkl. Abschluss. Unbekannte Zeichen werden '?'."""
    if isinstance(cmd, bytes):
        return cmd + TERM
    return cmd.encode(encoding, 'replace') + TERM


def quote(text):
    """Text für TJC-Stringliterale (keine Anführungszeichen/Backslashes)."""
    return '"%s"' % str(text).replace('\\', '/').replace('"', "'")


class EventParser(object):
    """Zerlegt den Bytestrom des Displays in Ereignisse.

    Robust gegen Fragmente (Daten kommen stückweise) und Störbytes: Passt ein
    Rahmen nicht, wird ein Byte verworfen und neu synchronisiert.
    """

    def __init__(self, encoding='iso-8859-1'):
        self.buf = bytearray()
        self.encoding = encoding
        self.dropped = 0

    def feed(self, data):
        self.buf.extend(data)
        events = []
        while self.buf:
            ev, used = self._parse_one()
            if used == 0:
                break          # unvollständig, auf mehr Daten warten
            del self.buf[:used]
            if ev is not None:
                events.append(ev)
        return events

    def _drop(self):
        self.dropped += 1
        return None, 1

    def _parse_one(self):
        buf = self.buf
        code = buf[0]
        # Startmeldung 00 00 00 FF FF FF
        if code == 0x00 and len(buf) >= 2 and buf[1] == 0x00:
            if len(buf) < 6:
                return (None, 0) if bytes(buf) == b'\x00\x00\x00\xff\xff\xff'[:len(buf)] \
                    else self._drop()
            if bytes(buf[:6]) == b'\x00\x00\x00\xff\xff\xff':
                return SystemEvent('startup'), 6
            return self._drop()
        if code in FIXED_CODES:
            n = 1 + FIXED_CODES[code] + 3
            if len(buf) < n:
                return None, 0
            if bytes(buf[n - 3:n]) != TERM:
                return self._drop()
            p = bytes(buf[1:n - 3])
            if code == 0x65:
                return ComponentEvent(p[0], p[1], p[2] == 1), n
            if code == 0x66:
                return PageEvent(p[0]), n
            if code in (0x67, 0x68):
                x, y = struct.unpack('>HH', p[:4])
                return TouchEvent(x, y, p[4] == 1, code == 0x68), n
            if code == 0x71:
                return NumberEvent(struct.unpack('<i', p)[0]), n
        if code == 0x70:
            idx = bytes(buf).find(TERM, 1)
            if idx < 0:
                if len(buf) > MAX_STRING:
                    return self._drop()
                return None, 0
            return StringEvent(bytes(buf[1:idx]).decode(self.encoding, 'replace')), idx + 3
        if code in SIMPLE_CODES:
            if len(buf) < 4:
                return (None, 0) if TERM.startswith(bytes(buf[1:])) else self._drop()
            if bytes(buf[1:4]) != TERM:
                return self._drop()
            name = SIMPLE_CODES[code]
            if code in ACK_CODES:
                return AckEvent(code, name), 4
            return SystemEvent(name), 4
        return self._drop()


# ---------------------------------------------------------------------------
# Serielle Schnittstelle (pyserial, sonst termios)
# ---------------------------------------------------------------------------
class _PySerialPort(object):
    def __init__(self, port, baud):
        import serial   # noqa: pyserial ist optional
        self.ser = serial.Serial(port, baud, timeout=0.05, write_timeout=2)

    def read(self, n=256):
        return self.ser.read(n)

    def write(self, data):
        self.ser.write(data)

    def set_baud(self, baud):
        self.ser.baudrate = baud

    def flush_input(self):
        self.ser.reset_input_buffer()

    def close(self):
        self.ser.close()


class _PosixSerialPort(object):
    """Minimaler Ersatz für pyserial über os.open/termios (nur Linux)."""

    def __init__(self, port, baud):
        import termios
        self.termios = termios
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.set_baud(baud)

    def set_baud(self, baud):
        termios = self.termios
        speed = getattr(termios, 'B%d' % baud, None)
        if speed is None:
            raise ValueError('Baudrate %d wird von termios nicht unterstützt' % baud)
        attrs = termios.tcgetattr(self.fd)
        # cfmakeraw nachgebaut
        attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP
                      | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON
                      | termios.IXOFF)
        attrs[1] &= ~termios.OPOST
        attrs[2] &= ~(termios.CSIZE | termios.PARENB | termios.CSTOPB | termios.CRTSCTS)
        attrs[2] |= termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG
                      | termios.IEXTEN)
        attrs[4] = speed
        attrs[5] = speed
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)

    def read(self, n=256):
        import select
        r, _, _ = select.select([self.fd], [], [], 0.05)
        if not r:
            return b''
        try:
            return os.read(self.fd, n)
        except BlockingIOError:
            return b''

    def write(self, data):
        import select
        view = memoryview(data)
        while view:
            try:
                n = os.write(self.fd, view)
                view = view[n:]
            except BlockingIOError:
                select.select([], [self.fd], [], 0.1)

    def flush_input(self):
        self.termios.tcflush(self.fd, self.termios.TCIFLUSH)

    def close(self):
        os.close(self.fd)


def open_serial(port, baud):
    try:
        import serial  # noqa: F401
        return _PySerialPort(port, baud)
    except ImportError:
        log.info('pyserial nicht vorhanden – nutze termios')
        return _PosixSerialPort(port, baud)


# ---------------------------------------------------------------------------
# Display-Treiber
# ---------------------------------------------------------------------------
class TjcDisplay(object):
    """Sendet Befehle mit Flusskontrolle und meldet Ereignisse per Callback.

    ``on_event(ev)`` wird im Lese-Thread aufgerufen – der Empfänger muss das
    Ereignis an seine Hauptschleife weiterreichen (Queue).
    """

    PROBE_BAUDS = (115200, 9600, 921600, 512000, 256000, 230400, 57600, 38400, 19200)

    def __init__(self, port, baud=115200, on_event=None, encoding='iso-8859-1',
                 window=6, ack_timeout=0.4, port_factory=open_serial):
        self.port_name = port
        self.baud = baud
        self.on_event = on_event or (lambda ev: None)
        self.encoding = encoding
        self.window = window
        self.ack_timeout = ack_timeout
        self.port_factory = port_factory
        self.port = None
        self.parser = EventParser(encoding)
        self._queue = collections.deque()
        self._cond = threading.Condition()
        self._outstanding = 0
        self._last_send = 0.0
        self._ack_mode = True
        self._missed_acks = 0
        self._any_frame = threading.Event()
        self._stop = False
        self._threads = []
        self.bytes_sent = 0

    # -- Lebenszyklus ----------------------------------------------------
    def open(self):
        self.port = self.port_factory(self.port_name, self.baud)
        for target in (self._reader, self._writer):
            t = threading.Thread(target=target, name='tjc-' + target.__name__.strip('_'))
            t.daemon = True
            t.start()
            self._threads.append(t)

    def close(self):
        self._stop = True
        with self._cond:
            self._cond.notify_all()
        if self.port is not None:
            self.port.close()

    def detect_baud(self, candidates=None):
        """Sucht die Baudrate, auf der das Display antwortet (``sendme``)."""
        cands = [self.baud] + [b for b in (candidates or self.PROBE_BAUDS) if b != self.baud]
        for baud in cands:
            if self._probe(baud):
                log.info('Display antwortet mit %d Baud', baud)
                return baud
        return None

    def _probe(self, baud):
        self.port.set_baud(baud)
        self.baud = baud
        time.sleep(0.05)
        self.port.flush_input()
        self._any_frame.clear()
        self.port.write(TERM + encode_command('sendme', self.encoding))
        return self._any_frame.wait(0.35)

    def change_baud(self, new_baud, persist=False):
        """Baudrate umstellen (``baud=`` flüchtig, ``bauds=`` dauerhaft)."""
        self.flush(2.0)
        cmd = ('bauds=%d' if persist else 'baud=%d') % new_baud
        self.port.write(encode_command(cmd, self.encoding))
        time.sleep(0.15)
        self.port.set_baud(new_baud)
        self.baud = new_baud
        time.sleep(0.05)
        return self._probe(new_baud)

    def init_display(self, sleep_after=0):
        """Grundeinstellungen nach Start/Reset des Displays."""
        for cmd in ('bkcmd=3', 'sendxy=1', 'thup=1', 'thsp=%d' % int(sleep_after), 'page 0'):
            self.send(cmd)

    # -- Senden ------------------------------------------------------------
    def send(self, cmd):
        data = encode_command(cmd, self.encoding)
        with self._cond:
            self._queue.append(data)
            self._cond.notify_all()

    def send_now(self, cmd):
        """Ohne Warteschlange (z. B. ``sleep=0``)."""
        self.port.write(encode_command(cmd, self.encoding))

    def discard_pending(self):
        """Verwirft nicht gesendete Befehle (z. B. vor einer Vollneuzeichnung)."""
        with self._cond:
            self._queue.clear()

    def pending(self):
        with self._cond:
            return len(self._queue)

    def flush(self, timeout=5.0):
        end = time.time() + timeout
        with self._cond:
            while (self._queue or self._outstanding) and time.time() < end:
                self._cond.wait(0.05)

    def _writer(self):
        while not self._stop:
            with self._cond:
                while not self._queue and not self._stop:
                    self._cond.wait(0.5)
                if self._stop:
                    return
                if self._ack_mode:
                    deadline = time.time() + self.ack_timeout
                    while self._outstanding >= self.window and not self._stop:
                        rest = deadline - time.time()
                        if rest <= 0:
                            self._missed_acks += 1
                            log.debug('Quittung fehlt (%d offen)', self._outstanding)
                            self._outstanding = 0
                            if self._missed_acks >= 5:
                                log.warning('Display quittiert nicht – nur Ratenbegrenzung')
                                self._ack_mode = False
                            break
                        self._cond.wait(rest)
                data = self._queue.popleft()
                if self._ack_mode:
                    self._outstanding += 1
            if not self._ack_mode:
                # 10 Bit pro Byte, 80 % der Leitung, plus Ausführungszeit
                pause = len(data) * 10.0 / self.baud / 0.8 + 0.002
                wait = self._last_send + pause - time.time()
                if wait > 0:
                    time.sleep(wait)
            try:
                self.port.write(data)
                self.bytes_sent += len(data)
            except Exception:
                log.exception('Schreiben auf %s fehlgeschlagen', self.port_name)
                time.sleep(0.5)
            self._last_send = time.time()

    # -- Empfangen ---------------------------------------------------------
    def _reader(self):
        while not self._stop:
            try:
                data = self.port.read(256)
            except Exception:
                if self._stop:
                    return
                log.exception('Lesen von %s fehlgeschlagen', self.port_name)
                time.sleep(0.5)
                continue
            if not data:
                continue
            for ev in self.parser.feed(data):
                self._any_frame.set()
                self._handle(ev)

    def _handle(self, ev):
        if isinstance(ev, AckEvent):
            with self._cond:
                if self._outstanding > 0:
                    self._outstanding -= 1
                self._missed_acks = 0
                self._cond.notify_all()
            if ev.code != 0x01:
                log.debug('Display meldet %s', ev.name)
                if ev.code == 0x24:
                    self.on_event(SystemEvent('buffer_overflow'))
            return
        if isinstance(ev, SystemEvent) and ev.name in ('startup', 'ready'):
            with self._cond:
                self._outstanding = 0
                self._cond.notify_all()
        self.on_event(ev)
