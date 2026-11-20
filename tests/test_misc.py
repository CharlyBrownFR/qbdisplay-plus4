# qbdisplay – Tests: Moonraker-Rahmen, PNG/Mosaik, Python-3.7-Syntax
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import ast
import json
import os
import re
import struct
import unittest
import zlib

from tests import helpers
from qbdisplay import moonraker, thumbs


class MoonrakerDispatchTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.c = moonraker.MoonrakerSocketClient('/nicht/da.sock',
                                                 lambda k, d: self.events.append((k, d)), {})

    def test_response_callback(self):
        got = []
        self.c._pending[7] = lambda r, e: got.append((r, e))
        self.c._dispatch(json.dumps({'jsonrpc': '2.0', 'id': 7, 'result': 'ok'}).encode())
        self.assertEqual(self.events[0][0], 'callback')
        cb, res, err = self.events[0][1]
        self.assertEqual((res, err), ('ok', None))

    def test_error_text(self):
        self.c._pending[8] = None
        self.c._pending[9] = lambda r, e: None
        self.c._dispatch(json.dumps({'id': 9, 'error': {'code': 400,
                                                         'message': 'Must home axis first'}}).encode())
        self.assertEqual(self.events[0][1][2], 'Must home axis first')

    def test_notifications(self):
        self.c._dispatch(json.dumps({'method': 'notify_status_update',
                                     'params': [{'extruder': {'temperature': 50}}, 1.0]}).encode())
        self.c._dispatch(json.dumps({'method': 'notify_gcode_response',
                                     'params': ['!! QDE_004_006']}).encode())
        self.c._dispatch(json.dumps({'method': 'notify_klippy_shutdown'}).encode())
        self.assertEqual([e[0] for e in self.events], ['status', 'gcode_response', 'klippy_state'])
        self.assertEqual(self.events[0][1], {'extruder': {'temperature': 50}})

    def test_reader_splits_on_etx(self):
        class FakeSock(object):
            def __init__(self, chunks):
                self.chunks = list(chunks)

            def recv(self, n):
                return self.chunks.pop(0) if self.chunks else b''

            def close(self):
                pass
        a = json.dumps({'method': 'notify_filelist_changed', 'params': []}).encode()
        b = json.dumps({'method': 'notify_history_changed', 'params': []}).encode()
        data = a + b'\x03' + b + b'\x03'
        self.c._reader(FakeSock([data[:5], data[5:len(a) + 3], data[len(a) + 3:]]))
        self.assertEqual([e[0] for e in self.events], ['files_changed', 'history_changed'])


def make_png(w, h, rgba_rows, filt=0):
    raw = b''
    for row in rgba_rows:
        raw += bytes([filt]) + b''.join(bytes(p) for p in row)

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


class ThumbTest(unittest.TestCase):
    def test_decode_and_mosaic(self):
        red, clear = (255, 0, 0, 255), (0, 0, 0, 0)
        rows = [[red, red, clear, clear]] * 2 + [[clear] * 4] * 2
        w, h, px = thumbs.decode_png(make_png(4, 4, rows))
        self.assertEqual((w, h), (4, 4))
        self.assertEqual(px[0][0], red)
        m = thumbs.mosaic(px, w, h, 2)
        self.assertEqual(m[0][0], '#F80000')
        self.assertIsNone(m[1][1])

    def test_sample_thumb(self):
        import scenarios
        path = scenarios.ensure_sample_thumb()
        with open(path, 'rb') as f:
            w, h, px = thumbs.decode_png(f.read())
        self.assertEqual((w, h), (160, 160))

    def test_pick(self):
        meta = {'thumbnails': [{'width': 300, 'relative_path': 'a'},
                               {'width': 32, 'relative_path': 'b'}]}
        self.assertEqual(thumbs.pick_thumbnail(meta, 27)['relative_path'], 'b')
        self.assertEqual(thumbs.pick_thumbnail(meta, 64)['relative_path'], 'a')
        self.assertIsNone(thumbs.pick_thumbnail({}, 10))


# APIs, die es erst ab Python 3.8 gibt (Debian 10 auf dem Drucker hat 3.7.3)
NEWER_APIS = [r'\bmath\.(prod|dist|isqrt|comb|perm)\b', r'cached_property', r'\.removeprefix\(',
              r'\.removesuffix\(', r'shlex\.join', r'\bfrom typing import .*\b(Literal|Final|Protocol|TypedDict)\b',
              r'\bzoneinfo\b', r'\bgraphlib\b', r'asyncio\.to_thread', r'\bstr \| ',
              r'@functools\.cache\b', r'\bmatch \w+:\s*$']


class Python37Test(unittest.TestCase):
    def files(self):
        out = []
        for base, dirs, fns in os.walk(helpers.ROOT):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', 'preview')]
            out.extend(os.path.join(base, f) for f in fns if f.endswith('.py'))
        return out

    def test_syntax_37(self):
        files = self.files()
        self.assertGreater(len(files), 20)
        for path in files:
            with open(path, 'r', encoding='utf-8') as f:
                src = f.read()
            try:
                ast.parse(src, filename=path, feature_version=(3, 7))
            except SyntaxError as e:
                self.fail('%s ist nicht Python-3.7-kompatibel: %s' % (path, e))

    def test_no_newer_apis(self):
        for path in self.files():
            if os.path.basename(path) == 'test_misc.py':
                continue
            with open(path, 'r', encoding='utf-8') as f:
                src = f.read()
            for pat in NEWER_APIS:
                m = re.search(pat, src, re.M)
                self.assertIsNone(m, '%s nutzt %s' % (path, m.group(0) if m else ''))

    def test_device_code_without_pillow(self):
        """Laufzeit-Module dürfen Pillow nicht importieren (gibt es auf dem Drucker nicht)."""
        pkg = os.path.join(helpers.ROOT, 'qbdisplay')
        for base, dirs, fns in os.walk(pkg):
            for fn in fns:
                if not fn.endswith('.py') or fn == 'sim.py':
                    continue
                with open(os.path.join(base, fn), encoding='utf-8') as f:
                    self.assertNotIn('from PIL', f.read(), fn)

    def test_gpl_header(self):
        for path in self.files():
            with open(path, 'r', encoding='utf-8') as f:
                head = f.read(800)
            self.assertTrue('GPL' in head or 'General Public License' in head, path)


if __name__ == '__main__':
    unittest.main()
