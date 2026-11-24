# qbdisplay – Tests: Übersetzungen und Sprachumschaltung
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
import shutil
import tempfile
import unittest

from tests import helpers
from qbdisplay import colors, errors, fonts, i18n, model
from qbdisplay.canvas import ListSink
from qbdisplay.ui import dialogs
import scenarios

PKG = os.path.join(helpers.ROOT, 'qbdisplay')
I18N = os.path.join(PKG, 'i18n.py')


def collect_literals():
    """Alle Literale in _('...') und N_('...') im Paket -> {text: 'datei:zeile'}."""
    found = {}
    for base, dirs, fns in os.walk(PKG):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in sorted(fns):
            if not fn.endswith('.py'):
                continue
            path = os.path.join(base, fn)
            with open(path, encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=path)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in ('_', 'N_') and node.args):
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        found.setdefault(arg.value, '%s:%d' % (os.path.relpath(path, PKG),
                                                               node.lineno))
    return found


def table_keys_in_source():
    """Schlüssel der EN-Tabelle wie im Quelltext (findet doppelte Einträge)."""
    with open(I18N, encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'EN' for t in node.targets):
            return [k.value for k in node.value.keys]
    raise AssertionError('EN-Tabelle nicht gefunden')


class TranslationTableTest(unittest.TestCase):
    def test_every_literal_translated(self):
        lits = collect_literals()
        self.assertGreater(len(lits), 200)
        missing = sorted('%s (%s)' % (k, v) for k, v in lits.items() if k not in i18n.EN)
        self.assertEqual(missing, [], 'Englisch fehlt für:\n' + '\n'.join(missing))

    def test_no_orphans_or_duplicates(self):
        lits = collect_literals()
        orphans = sorted(k for k in i18n.EN if k not in lits)
        self.assertEqual(orphans, [], 'verwaiste Einträge')
        keys = table_keys_in_source()
        dups = sorted(set(k for k in keys if keys.count(k) > 1))
        self.assertEqual(dups, [], 'doppelte Einträge')

    def test_placeholders_match(self):
        pat = re.compile(r'%(?:\([a-z]+\))?[-+ 0-9.]*[sdfgx%]|%[a-zA-Z]')
        for de, en in i18n.EN.items():
            self.assertEqual(sorted(pat.findall(de)), sorted(pat.findall(en)), de)

    def test_english_is_latin1_and_display_safe(self):
        for de, en in i18n.EN.items():
            self.assertTrue(all(ord(ch) < 256 for ch in en), en)
            self.assertNotIn('"', en)            # TJC-Strings stehen in "..."
            self.assertEqual(fonts.sanitize(en), en.replace('\\', '/'), en)


class SwitchTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language('de')

    def tearDown(self):
        i18n.set_language('de')

    def test_basic(self):
        self.assertEqual(i18n._('Bereit'), 'Bereit')
        i18n.set_language('en')
        self.assertEqual(i18n.get_language(), 'en')
        self.assertEqual(i18n._('Bereit'), 'Ready')
        self.assertEqual(i18n._('Slot %s wird geladen ...') % 'B', 'Loading slot B ...')
        self.assertEqual(i18n.decimal('0.1'), '0.1')
        i18n.set_language('de')
        self.assertEqual(i18n.decimal('0.1'), '0,1')

    def test_normalize_and_unknown(self):
        self.assertEqual(i18n.set_language('EN'), 'en')
        self.assertEqual(i18n.set_language('en_US'), 'en')
        self.assertEqual(i18n.set_language('English'), 'en')
        self.assertEqual(i18n.set_language('fr'), 'de')
        self.assertEqual(i18n.set_language(''), 'de')

    def test_missing_translation_falls_back_once(self):
        i18n.set_language('en')
        with self.assertLogs('qbdisplay.i18n', level='WARNING') as cm:
            self.assertEqual(i18n._('Gibt es nicht'), 'Gibt es nicht')
            self.assertEqual(i18n._('Gibt es nicht'), 'Gibt es nicht')
        self.assertEqual(len(cm.output), 1)

    def test_model_and_errors_follow_language(self):
        i18n.set_language('en')
        self.assertEqual(model.humidity_rating(45, ['PLA', 'PETG'])[1], 'too humid for PETG')
        self.assertEqual(colors.color_name('#141414'), 'Black')
        e = errors.classify('QDE_004_006: Failed to load filament to extruder')
        self.assertEqual(e.title, 'Filament does not reach the extruder')
        nodes, _links = errors.filament_path({}, 0)
        self.assertEqual(nodes[2].label, 'Tube')
        now = scenarios.NOW
        self.assertTrue(model.fmt_clock(now + 86400, now).startswith('tomorrow '))
        i18n.set_language('de')
        self.assertEqual(colors.color_name('#141414'), 'Schwarz')


def texts(sink):
    """Alle mit xstr gezeichneten Texte."""
    out = []
    for cmd in sink.commands:
        if cmd.startswith('xstr '):
            out.append(cmd[cmd.index('"') + 1:-1])
    return out


class AppLanguageTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language('de')
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, 'state.json')

    def tearDown(self):
        i18n.set_language('de')
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, scenario, state=None, lang_cfg=None):
        sink = ListSink()
        cfg = scenarios.make_config()
        cfg.cp.set('state', 'file', state or '')
        if lang_cfg:
            cfg.cp.set('display', 'language', lang_cfg)
        from qbdisplay.app import App
        app = scenarios.make_app(sink)
        # make_app baut die App ohne Zustandsdatei; hier mit eigener Konfiguration neu
        app2 = App(cfg, sink, rpc=scenarios.FakeRpc(), clock=lambda: scenarios.NOW)
        app2.st, app2.connected, app2.net = app.st, True, app.net
        app2.drying_tracker.path = state or None
        scenario(app2)
        app2.render()
        return app2, sink

    def tap(self, app, tid):
        for t in app.frame.targets:
            if t.tid == tid:
                app.tap(t.rect.cx, t.rect.cy)
                app.render()
                return
        raise AssertionError('Ziel %s fehlt' % tid)

    def test_switch_in_ui_redraws_and_persists(self):
        app, sink = self.make(lambda a: a.go('system', sys_sub='lang'), self.state)
        self.assertIn('Anzeige', texts(sink))
        # Trocknungsdaten in derselben Datei dürfen erhalten bleiben
        model.write_state(self.state, 'drying', {'start': 1, 'minutes': 60, 'temp': 50,
                                                 'profile': 'PLA', 'hum_start': None})
        del sink.commands[:]
        self.tap(app, 'r.lang.en')
        self.assertEqual(i18n.get_language(), 'en')
        drawn = texts(sink)
        self.assertIn('Display', drawn)             # Menü links neu gezeichnet
        self.assertIn('HOME', drawn)                # Navigation neu gezeichnet
        self.assertNotIn('Anzeige', drawn)
        with open(self.state, encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data['language'], 'en')
        self.assertEqual(data['drying']['profile'], 'PLA')
        # Neustart: gespeicherte Auswahl gewinnt gegen die Konfiguration
        i18n.set_language('de')
        app2, sink2 = self.make(lambda a: a.go('home'), self.state, lang_cfg='de')
        self.assertEqual(i18n.get_language(), 'en')
        self.assertIn('NOZZLE', texts(sink2))
        # zurück auf Deutsch
        app2.go('system', sys_sub='lang')
        app2.render()
        self.tap(app2, 'r.lang.de')
        self.assertEqual(i18n.get_language(), 'de')
        with open(self.state, encoding='utf-8') as f:
            self.assertEqual(json.load(f)['language'], 'de')

    def test_config_is_default(self):
        self.make(lambda a: a.go('home'), None, lang_cfg='en')
        self.assertEqual(i18n.get_language(), 'en')

    def test_error_dialog_in_english(self):
        i18n.set_language('de')
        app, sink = self.make(scenarios.s_error, None, lang_cfg='en')
        self.assertIsInstance(app.dialog, dialogs.ErrorDialog)
        drawn = texts(sink)
        self.assertIn('Filament does not reach the extruder', drawn)
        self.assertIn('Retry', drawn)

    def test_all_scenarios_render_in_english(self):
        i18n.set_language('en')
        for name, fn in scenarios.SCENARIOS:
            app = scenarios.make_app(ListSink())
            app.set_language('en', persist=False)
            with self.assertRaises(AssertionError):
                # keine fehlende Übersetzung (sonst gäbe es eine Log-Warnung)
                with self.assertLogs('qbdisplay.i18n', level='WARNING'):
                    fn(app)
                    app.render()


if __name__ == '__main__':
    unittest.main()
