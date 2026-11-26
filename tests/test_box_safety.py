# qbdisplay – Tests: warme Box und Filament am Druckkopf
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.

import unittest

from tests import helpers  # noqa: F401


class BoxSafetyTest(unittest.TestCase):
    def setUp(self):
        from tools import scenarios
        from qbdisplay.canvas import ListSink
        self.t = scenarios.NOW
        self.app = scenarios.make_app(ListSink())
        self.app.clock = lambda: self.t
        self.sent = []
        self.app.gcode = lambda cmd, *a, **k: self.sent.append(cmd)
        # A = PLA eingelegt, nichts geladen, Box kalt
        self.set({'mmu': {'gate_status': [1, 1, 0, 0], 'gate': -1, 'filament_pos': 0,
                          'action': 'Idle', 'gate_material': ['PLA', 'PETG', '', ''],
                          'gate_filament_name': ['', '', '', '']},
                  'temperature_sensor unit0_Env': {'temperature': 22.0, 'humidity': 40.0},
                  'heater_generic unit0_heater': {'temperature': 22.0, 'target': 0.0},
                  'hall_filament_width_sensor': {'Diameter': -0.2}})

    def set(self, d):
        self.app.st.update(d)
        self.app._status_changed()
        self.app._cache.clear()

    def test_cold_box_loads_directly(self):
        self.app.load_slot(0)
        self.assertEqual(len(self.sent), 1)
        self.assertIsNone(self.app.dialog)

    def test_warm_box_asks_for_pla(self):
        self.set({'temperature_sensor unit0_Env': {'temperature': 41.0}})
        self.app.load_slot(0)
        self.assertEqual(self.sent, [])
        self.assertIn('41', self.app.dialog.text)
        self.app.dialog._ok()
        self.assertEqual(len(self.sent), 1)

    def test_warm_box_ok_for_petg(self):
        self.set({'temperature_sensor unit0_Env': {'temperature': 41.0}})
        self.app.load_slot(1)
        self.assertEqual(len(self.sent), 1)

    def test_recent_heating_counts(self):
        self.set({'heater_generic unit0_heater': {'target': 45.0}})
        self.app.tick()
        self.set({'heater_generic unit0_heater': {'target': 0.0}})
        self.t += 10 * 60
        self.app._cache.clear()
        self.assertIn('10 min', self.app.warm_box(0))
        self.t += 25 * 60
        self.app._cache.clear()
        self.assertIsNone(self.app.warm_box(0))

    def test_stray_filament_at_head(self):
        self.set({'hall_filament_width_sensor': {'Diameter': 1.85}})
        self.assertEqual(self.app.head_mismatch(), 'stray')
        self.app.load_slot(1)
        self.assertEqual(self.sent, [])
        self.assertIn('Rest im Schlauch', self.app.dialog.text)

    def test_loaded_but_nothing_at_head(self):
        self.set({'mmu': {'gate': 1, 'filament_pos': 10}})
        self.assertEqual(self.app.head_mismatch(), 'missing')
        self.set({'hall_filament_width_sensor': {'Diameter': 1.75}})
        self.assertIsNone(self.app.head_mismatch())

    def test_no_sensor_no_check(self):
        self.app.st.objs.pop('hall_filament_width_sensor', None) if hasattr(self.app.st, 'objs') \
            else None
        self.set({'hall_filament_width_sensor': {'Diameter': None}})
        self.assertIsNone(self.app.head_mismatch())


if __name__ == '__main__':
    unittest.main()
