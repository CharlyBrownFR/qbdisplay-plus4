# qbdisplay – Tests: Rückfrage vor dem Trocknen (Spulen drehen sich)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.

import unittest

from tests import helpers  # noqa: F401


class DryingConfirmTest(unittest.TestCase):
    def setUp(self):
        from tools import scenarios
        from qbdisplay.sim import Simulator
        self.scenarios = scenarios
        self.app = scenarios.make_app(Simulator())
        self.sent = []
        self.app.gcode = lambda cmd, *a, **k: self.sent.append(cmd)

    def test_start_asks_first(self):
        self.scenarios.s_drying_select(self.app)
        self.app.st.update({'mmu': {'gate_status': [0, 0, 0, 0], 'gate': -1, 'filament_pos': 0}})
        self.app._status_changed()
        self.app._cache.clear()
        self.app.dry_start()
        self.assertEqual(self.sent, [])
        self.assertIsNotNone(self.app.dialog)
        self.app.dialog._ok()
        self.assertEqual(len(self.sent), 1)
        self.assertIsNone(self.app.dialog)

    def test_cancel_sends_nothing(self):
        self.scenarios.s_drying_select(self.app)
        self.app.dry_start()
        self.app.close_dialog()
        self.assertEqual(self.sent, [])

    def test_change_while_running_no_question(self):
        self.scenarios.s_drying_running(self.app)
        self.app.st.update({'mmu': {'gate_material': ['PETG', 'PETG', 'PETG', ''],
                                    'gate_filament_name': ['', '', '', '']}})
        self.app._status_changed()
        self.app._cache.clear()
        self.app.dry_start()
        self.assertEqual(len(self.sent), 1)
        self.assertIsNone(self.app.dialog)


if __name__ == '__main__':
    unittest.main()
