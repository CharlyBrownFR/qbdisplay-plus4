# qbdisplay – Tests: Vorschaubild-Stufe (System > Anzeige)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.

import json
import os
import tempfile
import unittest

from tests import helpers  # noqa: F401
from qbdisplay import thumbs


def picture(w, h, colourful):
    """Kreis auf transparentem Grund; bunt = jedes Pixel eine andere Farbe."""
    px = []
    for y in range(h):
        row = []
        for x in range(w):
            inside = (x - w // 2) ** 2 + (y - h // 2) ** 2 < (w // 2 - 4) ** 2
            if not inside:
                row.append((0, 0, 0, 0))
            elif colourful:
                row.append(((x * 37) % 256, (y * 53) % 256, ((x + y) * 29) % 256, 255))
            else:
                row.append((20, 20, 200, 255))
        px.append(row)
    return px


class ChooseTest(unittest.TestCase):
    def test_norm_mode(self):
        self.assertEqual(thumbs.norm_mode('auto'), 'auto')
        self.assertEqual(thumbs.norm_mode(' AUTO '), 'auto')
        self.assertEqual(thumbs.norm_mode('4'), '4')
        self.assertEqual(thumbs.norm_mode(6), '6')
        self.assertEqual(thumbs.norm_mode('1'), '2')
        self.assertEqual(thumbs.norm_mode('99'), '12')
        self.assertEqual(thumbs.norm_mode('quatsch'), 'auto')
        self.assertEqual(thumbs.norm_mode(None), 'auto')

    def test_fixed_modes_use_their_block(self):
        px = picture(160, 160, False)
        for mode, n in (('6', 164 // 6), ('4', 164 // 4), ('3', 164 // 3)):
            self.assertEqual(len(thumbs.choose(px, 160, 160, 164, mode)), n)

    def test_auto_fine_for_plain_coarse_for_colourful(self):
        plain = thumbs.choose(picture(160, 160, False), 160, 160, 164, 'auto')
        self.assertEqual(len(plain), 164 // 3)
        self.assertLessEqual(thumbs.seconds(plain), thumbs.AUTO_BUDGET)
        busy = thumbs.choose(picture(160, 160, True), 160, 160, 164, 'auto')
        self.assertEqual(len(busy), 164 // 6)

    def test_fills_counts_runs(self):
        self.assertEqual(thumbs.fills([['#A', '#A', None, '#B'], [None, None, None, None]]), 2)
        self.assertEqual(thumbs.fills([['#A', '#B', '#A']]), 3)


class SettingTest(unittest.TestCase):
    def setUp(self):
        from tools import scenarios
        from qbdisplay.canvas import ListSink
        fd, self.state = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        os.remove(self.state)
        self.app = scenarios.make_app(ListSink())
        self.app.state_file = self.state
        self.app.go('system', sys_sub='lang')
        self.app.render()

    def tearDown(self):
        if os.path.exists(self.state):
            os.remove(self.state)

    def tap_tid(self, tid):
        t = [t for t in self.app.frame.targets if t.tid == tid][0]
        self.app.tap(t.rect.cx, t.rect.cy)
        self.app.render()

    def test_tap_switches_and_persists(self):
        self.assertEqual(self.app.thumb_mode, '6')
        self.tap_tid('r.thumb.4')
        self.assertEqual(self.app.thumb_mode, '4')
        with open(self.state, encoding='utf-8') as f:
            self.assertEqual(json.load(f)['thumb_mode'], '4')
        # Beispielbild in der neuen Stufe (aus dem vorbereiteten Zwischenspeicher)
        self.assertEqual(len(self.app.thumb('front.gcode', 164)), 164 // 4)

    def test_switch_redraws_only_selector_text_and_image(self):
        from qbdisplay.canvas import ListSink
        from tools import scenarios
        sink = ListSink()
        app = scenarios.make_app(sink)
        app.state_file = self.state
        app.go('system', sys_sub='lang')
        app.render()
        full = len(sink.commands)
        del sink.commands[:]
        t = [t for t in app.frame.targets if t.tid == 'r.thumb.auto'][0]
        app.tap(t.rect.cx, t.rect.cy)
        app.render()
        app.render()
        self.assertLess(len(sink.commands), full // 2)
        texts = ' '.join(str(c) for c in sink.commands)
        self.assertNotIn('Netzwerk', texts)          # Menü links bleibt stehen
        self.assertNotIn('front.gcode', texts)       # Dateiname in der Kachel auch

    def test_saved_choice_wins_over_config(self):
        from tools import scenarios
        from qbdisplay.app import App
        from qbdisplay.canvas import ListSink
        from qbdisplay import model

        def start(cfg_value):
            cfg = scenarios.make_config()
            cfg.cp.set('state', 'file', self.state)
            cfg.cp.set('display', 'thumb_block', cfg_value)
            return App(cfg, ListSink(), rpc=scenarios.FakeRpc(), clock=lambda: scenarios.NOW)

        self.assertEqual(start('4').thumb_mode, '4')          # nichts gespeichert: Konfiguration
        self.assertEqual(start('quatsch').thumb_mode, 'auto')
        model.write_state(self.state, 'thumb_mode', '3')
        self.assertEqual(start('4').thumb_mode, '3')


if __name__ == '__main__':
    unittest.main()
