# qbdisplay – Tests: Alle auswerfen vor dem Trocknen
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.

import unittest

from tests import helpers  # noqa: F401


class HoldingRpc(object):
    """Merkt G-Code und Rückruf; der Test entscheidet, wann er fertig ist."""

    def __init__(self):
        self.pending = []
        self.scripts = []

    def call(self, method, params=None, cb=None):
        if cb:
            cb({}, None)

    def gcode(self, script, cb=None):
        self.scripts.append(script)
        self.pending.append(cb)

    def finish(self, err=None):
        cb = self.pending.pop(0)
        cb(None if err else 'ok', err)


class EjectAllTest(unittest.TestCase):
    def setUp(self):
        from tools import scenarios
        from qbdisplay.canvas import ListSink
        self.scenarios = scenarios
        self.t = scenarios.NOW
        self.app = scenarios.make_app(ListSink())
        self.app.clock = lambda: self.t
        self.rpc = self.app.rpc = HoldingRpc()
        # Slot A und C eingelegt, nichts geladen
        self.app.st.update({'mmu': {'gate_status': [1, 0, 1, 0], 'gate': -1,
                                    'filament_pos': 0, 'action': 'Idle',
                                    'gate_material': ['PETG', 'PETG', 'ASA', ''],
                                    'gate_filament_name': ['', '', '', '']}})
        self.app._status_changed()
        self.app.go('drying')
        self.app.render()

    def tick(self, dt=1.0):
        self.t += dt
        self.app._cache.clear()
        self.app.tick()

    def tap_tid(self, tid):
        t = [t for t in self.app.frame.targets if t.tid == tid][0]
        self.app.tap(t.rect.cx, t.rect.cy)
        self.app.render()

    def test_dialog_offers_eject_all(self):
        from qbdisplay.ui.dialogs import ChoiceDialog
        self.app.dry_start()
        self.app.render()
        self.assertIsInstance(self.app.dialog, ChoiceDialog)
        self.assertIn('A, C', self.app.dialog.title)
        self.tap_tid('yes')                          # trotzdem trocknen
        self.assertEqual(len(self.rpc.scripts), 1)
        self.assertIn('DRY', self.rpc.scripts[0])

    def test_ejects_one_after_another(self):
        self.app.dry_start()
        self.app.render()
        self.tap_tid('eject')
        self.assertEqual(self.rpc.scripts, ['MMU_EJECT GATE=0'])
        self.tick()
        self.assertEqual(len(self.rpc.scripts), 1)  # wartet auf Antwort
        self.rpc.finish()
        self.tick(0.5)
        self.assertEqual(len(self.rpc.scripts), 1)  # kurze Pause für den Status
        self.app.st.update({'mmu': {'action': 'Eject'}})
        self.tick(3)
        self.assertEqual(len(self.rpc.scripts), 1)  # Box arbeitet noch
        self.app.st.update({'mmu': {'action': 'Idle'}})
        self.tick()
        self.assertEqual(self.rpc.scripts[-1], 'MMU_EJECT GATE=2')
        self.rpc.finish()
        self.tick(3)
        self.assertIn('A, C', self.app.dialog.text)  # Abschluss-Hinweis
        self.assertIsNone(self.app._eject_queue)
        self.assertFalse(any('DRY' in s for s in self.rpc.scripts))  # trocknet nicht von selbst

    def test_unloads_loaded_slot_first(self):
        self.app.st.update({'mmu': {'gate': 2, 'filament_pos': 10}})
        self.app._status_changed()
        self.app._cache.clear()
        self.app.eject_all()
        self.assertEqual(self.rpc.scripts, ['MMU_UNLOAD'])
        self.rpc.finish()
        self.app.st.update({'mmu': {'gate': -1, 'filament_pos': 0}})
        self.tick(3)
        self.assertEqual(self.rpc.scripts[-1], 'MMU_EJECT GATE=0')

    def test_error_stops_sequence(self):
        self.app.eject_all()
        self.rpc.finish('Box error')
        self.tick(5)
        self.assertEqual(self.rpc.scripts, ['MMU_EJECT GATE=0'])
        self.assertIsNone(self.app._eject_queue)

    def test_print_start_aborts(self):
        self.app.eject_all()
        self.rpc.finish()
        self.app.st.update({'print_stats': {'state': 'printing'}})
        self.app._status_changed()
        self.tick(3)
        self.assertEqual(len(self.rpc.scripts), 1)
        self.assertIsNone(self.app._eject_queue)

    def test_pla_inserted_only_eject(self):
        from qbdisplay.ui.dialogs import ChoiceDialog
        self.app.st.update({'mmu': {'gate_material': ['PLA', 'PETG', 'ASA', '']}})
        self.app._status_changed()
        self.app._cache.clear()
        self.app.dry_start()
        self.app.render()
        self.assertIsInstance(self.app.dialog, ChoiceDialog)
        self.assertIn('PLA', self.app.dialog.title)
        tids = [t.tid for t in self.app.frame.targets]
        self.assertIn('eject', tids)
        self.assertNotIn('yes', tids)                # kein Trotzdem

    def test_cap_by_pla_spool_even_ejected(self):
        self.app.st.update({'mmu': {'gate_status': [0, 0, 0, 0],
                                    'gate_material': ['PLA', 'ABS', '', '']}})
        self.app._status_changed()
        self.app._cache.clear()
        cap, why, blockers = self.app.dry_cap()
        self.assertEqual((cap, why[0], blockers), (45, 'PLA', []))
        self.app.dry_set_profile(2)                  # ABS/ASA 60 °C
        self.assertEqual(self.app.dry_selection()['temp'], 45)

    def test_qidi_box_limit_only_while_inserted(self):
        self.app.st.update({'mmu': {'gate_box_max': [45, 45, 45, None]}})
        self.app._status_changed()
        self.app._cache.clear()
        self.assertEqual(self.app.dry_cap()[0], 45)
        self.app.st.update({'mmu': {'gate_status': [0, 0, 0, 0]}})
        self.app._status_changed()
        self.app._cache.clear()
        self.assertEqual(self.app.dry_cap()[0], 65)

    def test_no_answer_gives_up(self):
        self.app.eject_all()
        self.tick(301)
        self.assertIsNone(self.app._eject_queue)
        self.assertTrue(self.app.can_eject_all())

    def test_nothing_inserted_plain_question(self):
        from qbdisplay.ui.dialogs import ConfirmDialog
        self.app.st.update({'mmu': {'gate_status': [0, 0, 0, 0]}})
        self.app._status_changed()
        self.app._cache.clear()
        self.app.dry_start()
        self.assertIsInstance(self.app.dialog, ConfirmDialog)


if __name__ == '__main__':
    unittest.main()
