# qbdisplay – Tests: wechselnde Werte ohne Flackern neu zeichnen
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Ändert sich nur ein Messwert, darf keine Kachel erst gelöscht (große
``fill``-Fläche) und dann neu aufgebaut werden – das sah man am Gerät als kurzes
Schwarz-Blinken."""
import re
import unittest

from tests import helpers  # noqa: F401
from qbdisplay.canvas import Rect, ListSink, uncovered

# größte erlaubte Fläche eines einzelnen fill nach einer Wertänderung (px²)
MAX_FILL = 6000


def fills(cmds):
    out = []
    for c in cmds:
        m = re.match(r'fill (\d+),(\d+),(\d+),(\d+),', c)
        if m:
            out.append(tuple(int(v) for v in m.groups()))
    return out


class UncoveredTest(unittest.TestCase):
    def area(self, rects):
        return sum(r.w * r.h for r in rects)

    def test_nothing_covered(self):
        r = Rect(10, 10, 50, 20)
        self.assertEqual([g.tup() for g in uncovered(r, [])], [(10, 10, 50, 20)])

    def test_text_left_rest_filled(self):
        r = Rect(0, 0, 100, 32)
        gaps = uncovered(r, [Rect(0, 0, 40, 32)])
        self.assertEqual([g.tup() for g in gaps], [(40, 0, 60, 32)])

    def test_exact_complement(self):
        r = Rect(0, 0, 100, 40)
        cov = [Rect(0, 0, 40, 32), Rect(42, 8, 20, 18), Rect(90, -5, 30, 10)]
        gaps = uncovered(r, cov)
        self.assertEqual(self.area(gaps) + 40 * 32 + 20 * 18 + 10 * 5, 100 * 40)
        for g in gaps:
            for q in cov:
                self.assertFalse(g.x < q.x2 and q.x < g.x2 and g.y < q.y2 and q.y < g.y2)


class NoFlickerTest(unittest.TestCase):
    def app(self, scenario):
        from tools import scenarios
        sink = ListSink()
        app = scenarios.make_app(sink)
        scenario(app)
        app.render()
        return app, sink

    def change(self, app, sink, status):
        del sink.commands[:]
        app.st.update(status)
        app._status_changed()
        app.render()
        return sink.commands

    def assert_no_big_fill(self, cmds):
        self.assertTrue(cmds, 'nichts neu gezeichnet')
        big = [f for f in fills(cmds) if f[2] * f[3] > MAX_FILL]
        self.assertEqual(big, [])

    def test_box_humidity(self):
        from tools import scenarios
        app, sink = self.app(scenarios.s_filament)
        cmds = self.change(app, sink, {'temperature_sensor unit0_Env':
                                       {'temperature': 23.9, 'humidity': 51.0}})
        self.assert_no_big_fill(cmds)
        self.assertLess(len(cmds), 30)

    def test_print_temps_and_progress(self):
        from tools import scenarios
        app, sink = self.app(scenarios.s_home_print_plain)
        cmds = self.change(app, sink, {'extruder': {'temperature': 236.0},
                                       'heater_bed': {'temperature': 61.0},
                                       'virtual_sdcard': {'progress': 0.731},
                                       'display_status': {'progress': 0.731}})
        self.assert_no_big_fill(cmds)

    def test_idle_temps(self):
        from tools import scenarios
        app, sink = self.app(scenarios.s_home_idle)
        cmds = self.change(app, sink, {'extruder': {'temperature': 47.5}})
        self.assert_no_big_fill(cmds)

    def test_move_position_and_nozzle(self):
        from tools import scenarios
        app, sink = self.app(scenarios.s_move)
        cmds = self.change(app, sink, {'gcode_move': {'gcode_position': [12.3, 45.6, 7.89, 0]},
                                       'extruder': {'temperature': 61.0}})
        self.assert_no_big_fill(cmds)

    def test_drying(self):
        from tools import scenarios
        for sc in (scenarios.s_drying_select, scenarios.s_drying_running):
            app, sink = self.app(sc)
            env = app.st.get('temperature_sensor unit0_Env', 'humidity')
            tmp = app.st.get('temperature_sensor unit0_Env', 'temperature')
            # kleine Änderung (gleiche Bewertung der Feuchte -> gleiche Farbe)
            cmds = self.change(app, sink, {'temperature_sensor unit0_Env':
                                           {'temperature': tmp + 0.7, 'humidity': env - 1}})
            self.assert_no_big_fill(cmds)


class PlayTest(unittest.TestCase):
    """Canvas.play: Flächen unter späteren Befehlen, Kreise in späteren Kreisen."""

    def play(self, paint, rect=Rect(0, 0, 120, 40), clear='surface'):
        from qbdisplay.canvas import Canvas
        sink = ListSink()
        c = Canvas(sink)
        c.record_start()
        paint(c)
        c.play(rect, c.record_stop(), clear)
        return sink.commands

    def test_fill_spares_later_text(self):
        def paint(c):
            c.fill(0, 0, 120, 40, 'tint')
            c.text(10, 10, 60, 20, 'X', 4, 'text', 'tint')
        cmds = self.play(paint)
        text = Rect(10, 10, 60, 20)
        for x, y, w, h in fills(cmds):
            self.assertFalse(x < text.x2 and text.x < x + w and y < text.y2 and text.y < y + h,
                             (x, y, w, h))
        self.assertTrue(cmds[-1].startswith('xstr'))

    def test_same_colour_not_split(self):
        def paint(c):
            c.fill(0, 0, 120, 40, 'tint')
            c.fill(10, 10, 20, 20, 'tint')
        self.assertEqual(len(fills(self.play(paint))), 2)

    def test_disc_inside_later_disc_dropped(self):
        def paint(c):
            c.disc(30, 20, 4, 'surface3')
            c.disc(30, 20, 8, 'accent')
        cmds = [x for x in self.play(paint) if x.startswith('cirs')]
        self.assertEqual(len(cmds), 1)
        self.assertTrue(cmds[0].startswith('cirs 30,20,8,'))

    def test_gap_comes_just_before_its_disc(self):
        def paint(c):
            c.fill(0, 0, 50, 40, 'tint')
            c.text(60, 10, 20, 20, 'X', 4, 'text', 'surface')
            c.disc(100, 20, 10, 'accent')
        cmds = self.play(paint)
        i = next(k for k, x in enumerate(cmds) if x.startswith('cirs'))
        self.assertTrue(cmds[i - 1].startswith('fill '), cmds)


try:
    from PIL import ImageChops
except ImportError:      # Pillow fehlt -> Pixel-Tests überspringen
    ImageChops = None


def _changed(a, b):
    """Maske (Modus '1') der Pixel, in denen sich a und b unterscheiden."""
    r, g, b_ = ImageChops.difference(a, b).split()
    m = ImageChops.lighter(ImageChops.lighter(r, g), b_)
    return m.point(lambda v: 255 if v else 0).convert('1')


def _count(mask):
    return mask.histogram()[-1]


@unittest.skipIf(ImageChops is None, 'Pillow fehlt')
class PixelTest(unittest.TestCase):
    """Wie am Gerät: die Befehle einer Wertänderung einzeln im Simulator
    ausführen. Ein Pixel "blinkt", wenn es zwischendurch eine Farbe zeigt, die
    weder die alte noch die neue ist."""

    def update(self, scenario, status):
        from tools import scenarios
        from qbdisplay.sim import Simulator
        sim = Simulator()
        log = []
        app = scenarios.make_app(sim)
        scenario(app)
        app.render()
        before = sim.img.copy()
        sim.send = log.append
        app.st.update(status)
        app._status_changed()
        app.render()
        after = before.copy()
        sim.img = after
        from PIL import ImageDraw
        sim.draw = ImageDraw.Draw(after)
        for cmd in log:
            sim.execute(cmd)
        cur = before.copy()
        sim.img, sim.draw = cur, ImageDraw.Draw(cur)
        flashing = None
        for cmd in log:
            sim.execute(cmd)
            bad = ImageChops.logical_and(_changed(cur, before), _changed(cur, after))
            flashing = bad if flashing is None else ImageChops.logical_or(flashing, bad)
        # zur Kontrolle: dasselbe Bild wie komplett neu gezeichnet
        full = Simulator()
        app2 = scenarios.make_app(full)
        scenario(app2)
        app2.st.update(status)
        app2._status_changed()
        app2.render()
        self.assertEqual(_count(_changed(after, full.img)), 0, 'Endbild weicht ab')
        return _count(flashing) if flashing is not None else 0

    def test_print_page_values_dont_blink(self):
        from tools import scenarios
        for status in ({'extruder': {'temperature': 241.0}},
                       {'heater_bed': {'temperature': 61.0}},
                       {'print_stats': {'print_duration': 1017.0}},
                       {'print_stats': {'info': {'current_layer': 8, 'total_layer': 51}}}):
            self.assertEqual(self.update(scenarios.s_home_print_plain, status), 0, status)

    def test_status_pill_text_doesnt_blink(self):
        # 14 % -> 15 %: die Pille behält ihre Form, nur der Text wechselt;
        # übrig bleiben nur Ränder von Fortschrittsbalken und Knopf
        from tools import scenarios
        n = self.update(scenarios.s_home_print_plain,
                        {'virtual_sdcard': {'progress': 0.15}, 'display_status': {'progress': 0.15}})
        self.assertLess(n, 300)

    def test_idle_box_move_dont_blink(self):
        from tools import scenarios
        cases = ((scenarios.s_home_idle, {'extruder': {'temperature': 26.0}}),
                 (scenarios.s_filament, {'temperature_sensor unit0_Env':
                                         {'temperature': 23.9, 'humidity': 51.0}}),
                 (scenarios.s_move, {'gcode_move': {'gcode_position': [12.3, 45.6, 7.89, 0]}}))
        for scenario, status in cases:
            self.assertEqual(self.update(scenario, status), 0, scenario.__name__)


if __name__ == '__main__':
    unittest.main()
