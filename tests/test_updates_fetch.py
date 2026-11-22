# qbdisplay – Tests: Release laden, prüfen und entpacken (Selbst-Update, Baustein 1)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import unittest
from unittest import mock

from tests import helpers  # noqa: F401
from qbdisplay import updates


def make_pkg(version='0.4.0', extra=None, top='qbdisplay-plus4-0.4.0', skip=()):
    """Kleines Paket wie make_release.py es baut -> bytes."""
    files = {
        'install.sh': b'#!/bin/bash\n',
        'qbdisplay.tft': b'TFT',
        'qbdisplay/__init__.py': ('__version__ = "%s"\n' % version).encode(),
    }
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        for name, data in files.items():
            if name in skip:
                continue
            ti = tarfile.TarInfo('%s/%s' % (top, name))
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        for ti, data in (extra or []):
            tf.addfile(ti, io.BytesIO(data) if data is not None else None)
    return buf.getvalue()


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def release(data, version=(0, 4, 0), sha=None):
    return {'version': version, 'tag': 'v0.4.0', 'name': 'qbdisplay-plus4-0.4.0.tar.gz',
            'url': 'https://example.invalid/pkg.tar.gz',
            'sha256': sha or hashlib.sha256(data).hexdigest(), 'size': len(data)}


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def fetch(self, data, rel):
        with mock.patch('urllib.request.urlopen', lambda *a, **k: FakeResp(data)):
            return updates.fetch_release(rel, self.dir)

    def assertClean(self):
        # keine halben Downloads oder Arbeitsordner zurücklassen
        left = [n for n in os.listdir(self.dir) if not n.startswith('qbdisplay-plus4-')]
        self.assertEqual(left, [])

    def test_ok(self):
        data = make_pkg()
        path = self.fetch(data, release(data))
        self.assertTrue(os.path.isfile(os.path.join(path, 'install.sh')))
        self.assertEqual(os.path.basename(path), 'qbdisplay-plus4-0.4.0')
        self.assertClean()

    def test_wrong_checksum(self):
        data = make_pkg()
        with self.assertRaises(updates.UpdateError):
            self.fetch(data, release(data, sha='0' * 64))
        self.assertEqual(os.listdir(self.dir), [])

    def test_version_mismatch(self):
        data = make_pkg(version='0.3.9')
        with self.assertRaises(updates.UpdateError):
            self.fetch(data, release(data))
        self.assertClean()

    def test_missing_tft(self):
        data = make_pkg(skip=('qbdisplay.tft',))
        with self.assertRaises(updates.UpdateError):
            self.fetch(data, release(data))

    def test_path_traversal(self):
        ti = tarfile.TarInfo('qbdisplay-plus4-0.4.0/../../evil')
        ti.size = 1
        data = make_pkg(extra=[(ti, b'x')])
        with self.assertRaises(updates.UpdateError):
            self.fetch(data, release(data))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.dir), 'evil')))

    def test_symlink_rejected(self):
        ti = tarfile.TarInfo('qbdisplay-plus4-0.4.0/link')
        ti.type = tarfile.SYMTYPE
        ti.linkname = '/etc/passwd'
        data = make_pkg(extra=[(ti, None)])
        with self.assertRaises(updates.UpdateError):
            self.fetch(data, release(data))

    def test_real_release_package(self):
        pkg = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dist',
                           'qbdisplay-plus4-0.3.0.tar.gz')
        if not os.path.exists(pkg):
            self.skipTest('dist/ fehlt')
        with open(pkg, 'rb') as f:
            data = f.read()
        path = self.fetch(data, release(data, version=(0, 3, 0)))
        self.assertTrue(os.path.isfile(os.path.join(path, 'qbdisplay.tft')))


class InstallReleaseTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        data = make_pkg()
        self.rel = release(data)
        p = [mock.patch.object(updates, 'latest_release', lambda repo, pre=False: self.rel),
             mock.patch('urllib.request.urlopen', lambda *a, **k: FakeResp(data))]
        for x in p:
            x.start()
            self.addCleanup(x.stop)

    def test_started(self):
        with mock.patch.object(updates, 'helper', lambda *a, **k: (True, '')):
            self.assertEqual(updates.install_release('x/y', self.dir), ('started', (0, 4, 0)))

    def test_manual(self):
        out = 'manual: neues Hilfsskript - bitte ./install.sh von Hand ausführen'
        with mock.patch.object(updates, 'helper', lambda *a, **k: (False, out)):
            state, text = updates.install_release('x/y', self.dir)
        self.assertEqual(state, 'manual')
        self.assertTrue(text.startswith('neues Hilfsskript'))

    def test_bad_checksum_never_calls_helper(self):
        self.rel['sha256'] = '0' * 64
        called = []
        with mock.patch.object(updates, 'helper', lambda *a, **k: called.append(a)):
            state, _t = updates.install_release('x/y', self.dir)
        self.assertEqual((state, called), ('error', []))

    def test_status_file(self):
        path = os.path.join(self.dir, 'update-status')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('state=failed\nfrom=0.4.0\nto=0.5.0\ntime=1\nmessage=x = y\n')
        st = updates.read_status(path)
        self.assertEqual((st['state'], st['message']), ('failed', 'x = y'))
        updates.clear_status(path)
        self.assertEqual(updates.read_status(path), {})


class LatestReleaseTest(unittest.TestCase):
    def test_parse_github(self):
        api = {'tag_name': 'v0.3.0', 'assets': [
            {'name': 'notes.txt', 'digest': 'sha256:aa'},
            {'name': 'qbdisplay-plus4-0.3.0.tar.gz', 'size': 431332,
             'digest': 'sha256:8974767C6CA1EBA4A6DFA981253AB68C321C29F9F201DFEDF7F2ED13683C7E2B',
             'browser_download_url': 'https://github.com/x/y/releases/download/v0.3.0/p.tar.gz'}]}
        with mock.patch.object(updates, '_get', lambda url, *a: json.dumps(api)):
            rel = updates.latest_release('x/y')
        self.assertEqual(rel['version'], (0, 3, 0))
        self.assertEqual(rel['sha256'][:8], '8974767c')
        self.assertEqual(rel['size'], 431332)

    def _api(self, url, *a):
        if url.endswith('/releases/latest'):
            return json.dumps(self.rels[1])
        return json.dumps(self.rels)

    def _rels(self):
        asset = lambda v: {'name': 'qbdisplay-plus4-%s.tar.gz' % v, 'size': 1,
                           'digest': 'sha256:' + 'a' * 64,
                           'browser_download_url': 'https://example.invalid/%s' % v}
        self.rels = [
            {'tag_name': 'v0.4.1', 'prerelease': True, 'assets': [asset('0.4.1')]},
            {'tag_name': 'v0.4.0', 'prerelease': False, 'assets': [asset('0.4.0')]},
            {'tag_name': 'v0.5.0', 'draft': True, 'assets': [asset('0.5.0')]},
        ]

    def test_prerelease_only_when_enabled(self):
        self._rels()
        with mock.patch.object(updates, '_get', self._api):
            self.assertEqual(updates.latest_release('x/y')['version'], (0, 4, 0))
            self.assertEqual(updates.latest_release('x/y', True)['version'], (0, 4, 1))
            self.assertEqual(updates.remote_self('x/y'), ((0, 4, 0), False))
            self.assertEqual(updates.remote_self('x/y', True), ((0, 4, 1), True))

    def test_no_digest_no_update(self):
        api = {'tag_name': 'v0.3.0', 'assets': [{'name': 'qbdisplay-plus4-0.3.0.tar.gz'}]}
        with mock.patch.object(updates, '_get', lambda url, *a: json.dumps(api)):
            with self.assertRaises(ValueError):
                updates.latest_release('x/y')


if __name__ == '__main__':
    unittest.main()
