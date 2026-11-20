# qbdisplay – Tests: Farben, Schriften, Canvas-Befehle
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import unittest

from tests import helpers  # noqa: F401
from qbdisplay import colors, fonts, icons
from qbdisplay.canvas import Canvas, ListSink, Rect


class ColorTest(unittest.TestCase):
    def test_rgb565(self):
        self.assertEqual(colors.rgb565('#FFFFFF'), 65535)
        self.assertEqual(colors.rgb565('#000000'), 0)
        self.assertEqual(colors.rgb565('#FF0000'), 63488)
        self.assertEqual(colors.rgb565('#00FF00'), 2016)
        self.assertEqual(colors.rgb565('#0000FF'), 31)

    def test_token(self):
        self.assertEqual(colors.rgb565('bg'), colors.rgb565('#0D1117'))

    def test_roundtrip(self):
        self.assertEqual(colors.rgb565_to_rgb(65535), (255, 255, 255))

    def test_filament_color(self):
        self.assertEqual(colors.parse_filament_color('b87f2b'), '#B87F2B')
        self.assertEqual(colors.parse_filament_color('#151515FF'), '#151515')
        self.assertEqual(colors.parse_filament_color('red'), '#FF0000')
        self.assertIsNone(colors.parse_filament_color(''))

    def test_color_name(self):
        self.assertEqual(colors.color_name('#141414'), 'Schwarz')
        self.assertEqual(colors.color_name('#B87F2B'), 'Holzbraun')


class FontTest(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual(fonts.sanitize('a – b … "c"'), "a - b ... 'c'")
        self.assertEqual(fonts.sanitize('Düse 45 °C'), 'Düse 45 °C')

    def test_ellipsize(self):
        s = fonts.ellipsize('PETG Rapido Hochglanz Spezial', fonts.BTN, 80)
        self.assertTrue(s.endswith('...'))
        self.assertLessEqual(fonts.measure(s, fonts.BTN), 80)

    def test_wrap(self):
        lines = fonts.wrap('eins zwei drei vier fünf sechs sieben', fonts.TEXT, 90)
        self.assertGreater(len(lines), 1)
        for ln in lines:
            self.assertLessEqual(fonts.measure(ln, fonts.TEXT), 90)

    def test_monospace(self):
        fonts.set_monospace(True)
        try:
            self.assertEqual(fonts.measure('abcd', fonts.BTN), 4 * 12)
        finally:
            fonts.set_monospace(False)


class CanvasTest(unittest.TestCase):
    def setUp(self):
        self.sink = ListSink()
        self.c = Canvas(self.sink)

    def test_fill(self):
        self.c.fill(1, 2, 3, 4, '#FFFFFF')
        self.assertEqual(self.sink.commands, ['fill 1,2,3,4,65535'])

    def test_empty_fill_skipped(self):
        self.c.fill(1, 2, 0, 4, 'bg')
        self.assertEqual(self.sink.commands, [])

    def test_round_rect(self):
        self.c.round_rect(10, 10, 100, 50, 12, '#000000')
        cmds = self.sink.commands
        self.assertEqual(sum(1 for x in cmds if x.startswith('fill')), 3)
        self.assertEqual(sum(1 for x in cmds if x.startswith('cirs')), 4)
        self.assertIn('cirs 22,22,12,0', cmds)
        self.assertIn('cirs 97,47,12,0', cmds)

    def test_text(self):
        self.c.text(5, 6, 200, 30, 'Düse', 3, 'text', 'surface', 'center', 'center')
        cmd = self.sink.commands[0]
        self.assertTrue(cmd.startswith('xstr 5,6,200,30,3,'))
        self.assertTrue(cmd.endswith(',1,1,1,"Düse"'))

    def test_dim_changes_colors_and_skips_icons(self):
        self.c.dim = 0.8
        self.c.fill(0, 0, 1, 1, '#FFFFFF')
        self.c.icon('home', 0, 0, 30, 'text3', 'bar')
        self.assertEqual(len(self.sink.commands), 1)
        self.assertNotEqual(self.sink.commands[0], 'fill 0,0,1,1,65535')

    def test_icon_lookup(self):
        old = list(icons.MANIFEST)
        try:
            icons.set_manifest([('home', 30, 'text3', 'bar'), ('home', 30, 'accent', 'surface')])
            self.c.icon('home', 7, 8, 30, 'accent', 'surface')
            self.assertEqual(self.sink.commands, ['pic 7,8,1'])
            missing = []
            self.c.missing_icon_cb = missing.append
            self.c.icon('home', 7, 8, 30, 'text3', 'surface2')   # Fallback auf anderen Grund
            self.assertEqual(self.sink.commands[-1], 'pic 7,8,0')
            self.assertEqual(missing, [('home', 30, 'text3', 'surface2')])
        finally:
            icons.set_manifest(old)

    def test_rect(self):
        r = Rect(10, 20, 30, 40)
        self.assertTrue(r.contains(10, 20))
        self.assertFalse(r.contains(40, 20))
        self.assertEqual(r.inset(5).tup(), (15, 25, 20, 30))


if __name__ == '__main__':
    unittest.main()
