# qbdisplay – Tests: WLAN (Python-Teil des Hilfsskripts, Modul wifi, Oberfläche)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Der WLAN-Teil des Hilfsskripts läuft als root. Getestet wird er gegen eine
Attrappe von wpa_supplicant: nur bei Erfolg speichern, sonst altes Netz zurück."""
import hashlib
import io
import json
import os
import re
import unittest
from unittest import mock

from tests import helpers  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, 'systemd', 'qbdisplay-helper')


def load_wifi_py():
    with open(HELPER, encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'# --- WIFI_PY BEGIN ---\n(.*)# --- WIFI_PY END ---', text, re.S)
    ns = {'__name__': 'wifi_helper'}
    exec(compile(m.group(1), 'qbdisplay-helper:WIFI_PY', 'exec'), ns)
    return ns


class FakeWpa(object):
    """Nachbildung der wpa_supplicant-Steuerbefehle, die das Hilfsskript nutzt."""

    def __init__(self, nets=(), connects=True, ip='192.168.1.77', states=None):
        self.nets = {}      # id -> dict(ssid=hex/str, flags, params)
        self.next_id = 0
        for ssid, flags in nets:
            self.nets[str(self.next_id)] = {'ssid': ssid, 'flags': flags, 'p': {}}
            self.next_id += 1
        self.connects = connects
        self.ip = ip
        self.states = states or ['ASSOCIATING', '4WAY_HANDSHAKE']
        self.cur = '0' if self.nets else None
        self.log = []
        self.saved = None
        self.polls = 0
        self.scan_results = ''

    def __call__(self, cmd):
        self.log.append(cmd)
        a = cmd.split(' ')
        if a[0] == 'ADD_NETWORK':
            nid = str(self.next_id)
            self.next_id += 1
            self.nets[nid] = {'ssid': '', 'flags': '[DISABLED]', 'p': {}}
            return nid
        if a[0] == 'SET_NETWORK':
            self.nets[a[1]]['p'][a[2]] = a[3]
            if a[2] == 'ssid':
                self.nets[a[1]]['ssid'] = bytes.fromhex(a[3]).decode()
            return 'OK'
        if a[0] == 'SELECT_NETWORK':
            for k, n in self.nets.items():
                n['flags'] = '' if k == a[1] else '[DISABLED]'
            self.cur = a[1]
            self.polls = 0
            return 'OK'
        if a[0] == 'ENABLE_NETWORK':
            self.nets[a[1]]['flags'] = ''
            return 'OK'
        if a[0] == 'REMOVE_NETWORK':
            del self.nets[a[1]]
            if self.cur == a[1]:
                self.cur = None
            return 'OK'
        if a[0] == 'LIST_NETWORKS':
            lines = ['network id / ssid / bssid / flags']
            for k, n in sorted(self.nets.items()):
                lines.append('%s\t%s\tany\t%s' % (k, n['ssid'], n['flags']))
            return '\n'.join(lines)
        if a[0] == 'STATUS':
            if self.cur is None:
                return 'wpa_state=SCANNING'
            self.polls += 1
            n = self.nets[self.cur]
            if self.connects:
                ip = ('\nip_address=%s' % self.ip) if (self.ip and self.polls > 1) else ''
                return 'wpa_state=COMPLETED\nid=%s\nssid=%s%s' % (self.cur, n['ssid'], ip)
            st = self.states[min(self.polls - 1, len(self.states) - 1)]
            return 'wpa_state=%s' % st
        if a[0] == 'SAVE_CONFIG':
            self.saved = dict((k, dict(v)) for k, v in self.nets.items())
            return 'OK'
        if a[0] == 'SCAN':
            return 'OK'
        if a[0] == 'SCAN_RESULTS':
            return self.scan_results
        if a[0] in ('REASSOCIATE', 'RECONNECT'):
            return 'OK'
        return 'UNKNOWN COMMAND'


class Clock(object):
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class HelperWifiTest(unittest.TestCase):
    def setUp(self):
        self.w = load_wifi_py()

    def connect(self, fake, ssid, psk):
        clk = Clock()
        return self.w['connect'](fake, ssid, psk, sleep=clk.sleep, clock=clk)

    def test_success_saves_and_keeps_old(self):
        fake = FakeWpa(nets=[('Alt', '[CURRENT]')])
        res = self.connect(fake, 'Neu', 'geheim123')
        self.assertTrue(res['ok'])
        self.assertEqual(res['ip'], '192.168.1.77')
        self.assertTrue(res['saved'])
        names = sorted(n['ssid'] for n in fake.saved.values())
        self.assertEqual(names, ['Alt', 'Neu'])
        # altes Netz wieder zugelassen (Rückfall, falls das neue mal weg ist)
        self.assertNotIn('[DISABLED]', [n['flags'] for n in fake.saved.values()
                                        if n['ssid'] == 'Alt'][0])

    def test_password_never_sent_in_clear(self):
        fake = FakeWpa()
        self.connect(fake, 'Neu', 'geheim123')
        self.assertFalse(any('geheim123' in c for c in fake.log))
        psk = [c for c in fake.log if ' psk ' in c][0].split(' ')[-1]
        self.assertEqual(psk, hashlib.pbkdf2_hmac('sha1', b'geheim123', b'Neu', 4096, 32).hex())

    def test_wrong_password_restores_old(self):
        fake = FakeWpa(nets=[('Alt', '[CURRENT]')], connects=False)
        res = self.connect(fake, 'Neu', 'falsch123')
        self.assertFalse(res['ok'])
        self.assertEqual(res['reason'], 'auth')
        self.assertIsNone(fake.saved)
        self.assertEqual([n['ssid'] for n in fake.nets.values()], ['Alt'])
        self.assertEqual(fake.nets['0']['flags'], '')
        self.assertIn('REASSOCIATE', fake.log)

    def test_not_found(self):
        fake = FakeWpa(nets=[('Alt', '')], connects=False, states=['SCANNING'])
        res = self.connect(fake, 'Weg', 'egal12345')
        self.assertEqual(res['reason'], 'notfound')
        self.assertIsNone(fake.saved)

    def test_no_dhcp(self):
        fake = FakeWpa(nets=[('Alt', '')], ip='')
        res = self.connect(fake, 'Neu', 'geheim123')
        self.assertEqual(res['reason'], 'dhcp')
        self.assertIsNone(fake.saved)
        self.assertEqual([n['ssid'] for n in fake.nets.values()], ['Alt'])

    def test_previously_disabled_stays_disabled(self):
        fake = FakeWpa(nets=[('Alt', '[CURRENT]'), ('Aus', '[DISABLED]')], connects=False)
        self.connect(fake, 'Neu', 'falsch123')
        self.assertEqual(fake.nets['1']['flags'], '[DISABLED]')

    def test_same_ssid_replaced(self):
        fake = FakeWpa(nets=[('Heim', '[CURRENT]')])
        res = self.connect(fake, 'Heim', 'neuespw1')
        self.assertTrue(res['ok'])
        self.assertEqual([n['ssid'] for n in fake.saved.values()], ['Heim'])

    def test_open_network(self):
        fake = FakeWpa()
        self.connect(fake, 'Gast', '')
        self.assertIn('key_mgmt NONE', ' '.join(fake.log))

    def test_input_checked(self):
        fake = FakeWpa()
        for ssid, psk in (('', 'geheim123'), ('x' * 33, 'geheim123'), ('a', 'kurz'),
                          ('a', 'x' * 64), ('a', 'ümlaut123')):
            self.assertEqual(self.connect(fake, ssid, psk)['reason'], 'input', (ssid, psk))
        self.assertEqual(fake.log, [])

    def test_special_characters_hex_encoded(self):
        fake = FakeWpa()
        ssid = 'Café "WLAN" \\ 1'
        res = self.connect(fake, ssid, 'a"b\\c d\'e')
        self.assertTrue(res['ok'])
        cmd = [c for c in fake.log if ' ssid ' in c][0]
        self.assertEqual(cmd.split(' ')[-1], ssid.encode('utf-8').hex())

    def test_scan_parses_and_dedups(self):
        fake = FakeWpa(nets=[('Heim', '[CURRENT]')])
        fake.scan_results = '\n'.join([
            'bssid / frequency / signal level / flags / ssid',
            'aa:01\t2437\t-60\t[WPA2-PSK-CCMP][ESS]\tHeim',
            'aa:02\t2412\t-50\t[WPA2-PSK-CCMP][ESS]\tHeim',
            'aa:03\t2462\t-70\t[ESS]\tGast',
            'aa:04\t2462\t-80\t[WPA2-EAP-CCMP][ESS]\tFirma',
            'aa:05\t2462\t-80\t[RSN-SAE-CCMP][ESS]\tNeu3',
            'aa:06\t2462\t-40\t[WPA2-PSK-CCMP][ESS]\t',
            'aa:07\t2462\t-75\t[WPA2-PSK-CCMP][ESS]\tCaf\\xc3\\xa9 \\"x\\"',
        ])
        with mock.patch.object(self.w['time'], 'sleep'):
            nets = self.w['scan'](fake)
        self.assertEqual([n['ssid'] for n in nets], ['Heim', 'Gast', 'Café "x"', 'Firma', 'Neu3'])
        self.assertEqual(nets[0]['signal'], -50)
        self.assertTrue(nets[0]['current'])
        self.assertEqual([n['kind'] for n in nets], ['psk', 'open', 'psk', 'eap', 'sae'])

    def test_main_reads_stdin(self):
        fake = FakeWpa()
        out = io.StringIO()
        with mock.patch.dict(self.w, {'Ctrl': lambda: fake_ctl}), \
                mock.patch('sys.stdout', out):
            fake_ctl = mock.MagicMock(side_effect=fake)
            with mock.patch.dict(self.w, {'connect': lambda c, s, p: {'ok': True, 's': s,
                                                                         'p': p}}):
                rc = self.w['main'](['connect'], stdin=io.StringIO('Mein Netz\npw mit space\n'))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue()), {'ok': True, 's': 'Mein Netz',
                                                      'p': 'pw mit space'})


class WifiModuleTest(unittest.TestCase):
    def test_connect_passes_password_via_stdin(self):
        from qbdisplay import wifi
        with mock.patch('qbdisplay.updates.helper', return_value=(True, '{"ok": true}')) as h:
            self.assertEqual(wifi.connect('Heim', 'geheim123'), {'ok': True})
        args, kw = h.call_args
        self.assertEqual(args, ('wifi-connect',))
        self.assertEqual(kw['data'], 'Heim\ngeheim123\n')

    def test_old_helper_detected(self):
        from qbdisplay import wifi
        usage = 'Aufruf: /usr/local/sbin/qbdisplay-helper version|to-qidi|update <ordner>'
        with mock.patch('qbdisplay.updates.helper', return_value=(False, usage)):
            self.assertEqual(wifi.scan(), ([], 'old_helper'))
            self.assertEqual(wifi.connect('a', 'b' * 8)['reason'], 'old_helper')

    def test_valid_psk(self):
        from qbdisplay import wifi
        self.assertTrue(wifi.valid_psk('12345678'))
        self.assertFalse(wifi.valid_psk('1234567'))
        self.assertFalse(wifi.valid_psk('x' * 64))
        self.assertTrue(wifi.valid_psk('ab' * 32))
        self.assertFalse(wifi.valid_psk('ümlaut12'))


class WifiUiTest(unittest.TestCase):
    def setUp(self):
        from tools import scenarios
        from qbdisplay.canvas import ListSink
        self.sink = ListSink()
        self.app = scenarios.make_app(self.sink)
        scenarios.s_wifi_list(self.app)
        self.app.render()

    def tap_tid(self, tid):
        t = [t for t in self.app.frame.targets if t.tid == tid][0]
        self.app.tap(t.rect.cx, t.rect.cy)
        self.app.render()

    def test_change_button_opens_page_and_scans(self):
        from tools import scenarios
        app = self.app
        scenarios.s_system_network(app)
        app.render()
        with mock.patch('qbdisplay.wifi.scan', return_value=([], None)):
            self.tap_tid('wifi.chg')
            self.assertEqual(app.page_name, 'wifi')
            self.assertEqual(app.wifi['state'], 'scanning')
            kind, data = app.events.get(timeout=5)
            app.handle(kind, data)
        self.assertEqual(app.wifi['state'], 'done')

    def test_type_password_and_connect(self):
        from qbdisplay.ui.wifi import PasswordDialog
        app = self.app
        self.tap_tid('w.n1')                     # FRITZ!Box, mit Passwort
        self.assertIsInstance(app.dialog, PasswordDialog)
        self.assertNotIn('ok', [t.tid for t in app.frame.targets])   # noch zu kurz
        for tid in ('shift', 'k1_0', 'k1_0', 'sym', 'k1_1', 'sym', 'k0_0', 'k0_1', 'k0_2',
                    'k0_3', 'k0_4', 'bs', 'k0_4'):
            self.tap_tid(tid)
        self.assertEqual(app.dialog.text, 'Qq"12345')
        with mock.patch('qbdisplay.wifi.connect',
                        return_value={'ok': True, 'ip': '10.0.0.5', 'saved': True}) as c, \
                mock.patch('qbdisplay.wifi.scan', return_value=([], None)), \
                mock.patch('qbdisplay.netinfo.gather', return_value={}):
            self.tap_tid('ok')
            self.assertIsNone(app.dialog)
            self.assertEqual(app.wifi['connecting'], 'FRITZ!Box 7590 XY')
            kind, data = app.events.get(timeout=5)
            app.handle(kind, data)
        c.assert_called_once_with('FRITZ!Box 7590 XY', 'Qq"12345')
        self.assertIsNone(app.wifi['connecting'])
        self.assertEqual(app.wifi['current'], 'FRITZ!Box 7590 XY')

    def test_failure_shows_info(self):
        from qbdisplay.ui.dialogs import InfoDialog
        app = self.app
        with mock.patch('qbdisplay.wifi.scan', return_value=([], None)), \
                mock.patch('qbdisplay.netinfo.gather', return_value={}):
            app.handle('wifi_connect', {'ok': False, 'reason': 'auth', 'ssid': 'X'})
        self.assertIsInstance(app.dialog, InfoDialog)
        self.assertIn('Passwort', app.dialog.text)

    def test_unsupported_network_not_opened(self):
        app = self.app
        self.tap_tid('w.n3')                     # WPA3
        self.assertIsNone(app.dialog)

    def test_blocked_while_printing(self):
        app = self.app
        app.st.update({'print_stats': {'state': 'printing'}})
        app._status_changed()
        app.render()
        self.tap_tid('w.n1')
        self.assertIsNone(app.dialog)

    def test_key_press_redraws_little(self):
        app = self.app
        self.tap_tid('w.n1')
        del self.sink.commands[:]
        self.tap_tid('k1_0')
        self.assertLess(len(self.sink.commands), 40)
        del self.sink.commands[:]
        self.tap_tid('shift')
        # Umschalten zeichnet die Buchstaben neu, bleibt aber deutlich unter dem Öffnen
        self.assertLess(len(self.sink.commands), 200)


if __name__ == '__main__':
    unittest.main()
