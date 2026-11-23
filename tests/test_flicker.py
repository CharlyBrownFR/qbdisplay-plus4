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


if __name__ == '__main__':
    unittest.main()
