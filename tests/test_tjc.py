# qbdisplay – Tests: TJC-Protokoll (Befehlsbau, Event-Parser, Flusskontrolle)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import threading
import time
import unittest

from tests import helpers  # noqa: F401
from qbdisplay import tjc


class EncodeTest(unittest.TestCase):
    def test_terminator(self):
        self.assertEqual(tjc.encode_command('page 0'), b'page 0\xff\xff\xff')

    def test_latin1_umlaut(self):
        self.assertEqual(tjc.encode_command('xstr 0,0,1,1,0,0,0,0,0,1,"Düse °C"'),
                         'xstr 0,0,1,1,0,0,0,0,0,1,"Düse °C"'.encode('latin-1') + tjc.TERM)

    def test_unencodable_replaced(self):
        self.assertTrue(tjc.encode_command('a→b').startswith(b'a?b'))

    def test_quote(self):
        self.assertEqual(tjc.quote('a"b\\c'), '"a\'b/c"')


class ParserTest(unittest.TestCase):
    def setUp(self):
        self.p = tjc.EventParser()

    def test_touch_press_release(self):
        evs = self.p.feed(b'\x67\x01\x2c\x00\xf0\x01\xff\xff\xff\x67\x01\x2c\x00\xf0\x00\xff\xff\xff')
        self.assertEqual(evs, [tjc.TouchEvent(300, 240, True, False),
                               tjc.TouchEvent(300, 240, False, False)])

    def test_touch_sleep(self):
        evs = self.p.feed(b'\x68\x00\x0a\x00\x14\x01\xff\xff\xff')
        self.assertEqual(evs, [tjc.TouchEvent(10, 20, True, True)])

    def test_fragmented(self):
        data = b'\x65\x00\x02\x01\xff\xff\xff\x01\xff\xff\xff'
        evs = []
        for b in data:
            evs.extend(self.p.feed(bytes([b])))
        self.assertEqual(evs, [tjc.ComponentEvent(0, 2, True), tjc.AckEvent(1, 'ok')])

    def test_startup_and_ready(self):
        evs = self.p.feed(b'\x00\x00\x00\xff\xff\xff\x88\xff\xff\xff')
        self.assertEqual(evs, [tjc.SystemEvent('startup'), tjc.SystemEvent('ready')])

    def test_invalid_instruction_is_ack(self):
        evs = self.p.feed(b'\x00\xff\xff\xff')
        self.assertEqual(evs, [tjc.AckEvent(0, 'invalid_instruction')])

    def test_garbage_resync(self):
        evs = self.p.feed(b'\x42\x13\x37\x67\x00\x01\x00\x02\x01\xff\xff\xff')
        self.assertEqual(evs, [tjc.TouchEvent(1, 2, True, False)])
        self.assertGreaterEqual(self.p.dropped, 3)

    def test_ff_in_payload(self):
        # x = 255 -> 00 FF, darf den Abschluss nicht verwirren
        evs = self.p.feed(b'\x67\x00\xff\x01\xdf\x00\xff\xff\xff')
        self.assertEqual(evs, [tjc.TouchEvent(255, 479, False, False)])

    def test_number_negative(self):
        evs = self.p.feed(b'\x71\xff\xff\xff\xff\xff\xff\xff')
        self.assertEqual(evs, [tjc.NumberEvent(-1)])

    def test_string(self):
        evs = self.p.feed(b'\x70Gr\xfc\xdfe\xff\xff\xff')
        self.assertEqual(evs, [tjc.StringEvent('Grüße')])

    def test_sleep_wake(self):
        evs = self.p.feed(b'\x86\xff\xff\xff\x87\xff\xff\xff')
        self.assertEqual([e.name for e in evs], ['sleep', 'wake'])

    def test_wait_for_more(self):
        self.assertEqual(self.p.feed(b'\x67\x00\x01'), [])
        self.assertEqual(self.p.feed(b'\x00\x02\x01\xff\xff'), [])
        self.assertEqual(self.p.feed(b'\xff'), [tjc.TouchEvent(1, 2, True, False)])


class FakePort(object):
    """Simuliertes Display: quittiert jeden Befehl mit 0x01."""

    def __init__(self, ack=True):
        self.written = []
        self.ack = ack
        self.rx = b''
        self.lock = threading.Lock()
        self.baud = 115200

    def write(self, data):
        with self.lock:
            self.written.append(bytes(data))
            if self.ack:
                n = bytes(data).count(tjc.TERM)
                self.rx += b'\x01\xff\xff\xff' * n

    def read(self, n=256):
        time.sleep(0.001)
        with self.lock:
            out, self.rx = self.rx[:n], self.rx[n:]
        return out

    def set_baud(self, b):
        self.baud = b

    def flush_input(self):
        pass

    def close(self):
        pass


class DisplayFlowTest(unittest.TestCase):
    def make(self, port, **kw):
        d = tjc.TjcDisplay('fake', 115200, port_factory=lambda name, baud: port, **kw)
        d.open()
        self.addCleanup(d.close)
        return d

    def test_all_commands_sent_with_acks(self):
        port = FakePort(ack=True)
        d = self.make(port, window=3)
        for i in range(50):
            d.send('fill %d,0,1,1,0' % i)
        d.flush(5)
        self.assertEqual(len(port.written), 50)
        self.assertEqual(port.written[0], b'fill 0,0,1,1,0\xff\xff\xff')
        self.assertTrue(d._ack_mode)

    def test_no_acks_falls_back_to_rate_limit(self):
        port = FakePort(ack=False)
        d = self.make(port, window=2, ack_timeout=0.02)
        for i in range(20):
            d.send('cls 0')
        d.flush(5)
        self.assertEqual(len(port.written), 20)
        self.assertFalse(d._ack_mode)

    def test_touch_event_forwarded(self):
        port = FakePort(ack=False)
        got = []
        d = self.make(port)
        d.on_event = got.append
        port.rx = b'\x67\x00\x10\x00\x20\x01\xff\xff\xff'
        for _ in range(100):
            if got:
                break
            time.sleep(0.01)
        self.assertEqual(got, [tjc.TouchEvent(16, 32, True, False)])


if __name__ == '__main__':
    unittest.main()
