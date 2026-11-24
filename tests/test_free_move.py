# qbdisplay – Tests: Notbewegung (bewegen ohne Referenzfahrt)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.

import unittest

from tests import helpers  # noqa: F401


class AnsweringRpc(object):
    """Wie FakeRpc, meldet G-Code aber sofort als erledigt."""

    def __init__(self):
        self.scripts = []

    def call(self, method, params=None, cb=None):
        if cb:
            cb({}, None)

    def gcode(self, script, cb=None):
        self.scripts.append(script)
        if cb:
            cb('ok', None)


class FreeMoveTest(unittest.TestCase):
    def setUp(self):
        from tools import scenarios
        from qbdisplay.canvas import ListSink
        self.t = scenarios.NOW
        self.app = scenarios.make_app(ListSink())
        self.app.clock = lambda: self.t
        self.rpc = self.app.rpc = AnsweringRpc()
        self.app.st.update({'toolhead': {'homed_axes': '', 'axis_minimum': [-1.5, -2, -2, 0],
                                          'axis_maximum': [307, 325, 285, 0]}})
        self.app._status_changed()
        self.app.go('move', step=50.0)
        self.app.render()

    def tids(self):
        return [t.tid for t in self.app.frame.targets]

    def tap_tid(self, tid):
        t = [t for t in self.app.frame.targets if t.tid == tid][0]
        self.app.tap(t.rect.cx, t.rect.cy)
        self.app.render()

    def unlock(self):
        self.tap_tid('freemove')
        self.tap_tid('yes')

    def test_unlock_sets_middle_and_limits_steps(self):
        from qbdisplay.ui.dialogs import ConfirmDialog
        self.tap_tid('freemove')
        self.assertIsInstance(self.app.dialog, ConfirmDialog)
        self.assertEqual(self.rpc.scripts, [])          # erst nach Bestätigung
        self.tap_tid('yes')
        self.assertEqual(self.rpc.scripts, ['SET_KINEMATIC_POSITION X=152.8 Y=161.5 Z=141.5'])
        self.assertTrue(self.app.free_move)
        self.assertEqual(self.app.ui['step'], 10.0)     # 50 mm -> 10 mm
        self.app.st.update({'toolhead': {'homed_axes': 'xyz'}})
        self.app._status_changed()
        self.app.render()
        self.assertIn('done', self.tids())
        self.assertNotIn('motoff', self.tids())
        self.app.jog('Z', 50)                           # auch direkt höchstens 10 mm
        self.assertEqual(self.rpc.scripts[-1], 'G91\nG1 Z10.000 F600\nG90')
        n = len(self.rpc.scripts)
        self.assertNotIn('hz', self.tids())             # Referenzfahrt gesperrt
        self.assertNotIn('homeall', self.tids())
        self.app.home('X Y')
        self.assertEqual(len(self.rpc.scripts), n)

    def test_only_unhomed_axes_are_set(self):
        self.app.st.update({'toolhead': {'homed_axes': 'xy'}})
        self.app._status_changed()
        self.app.render()
        self.unlock()
        self.assertEqual(self.rpc.scripts, ['SET_KINEMATIC_POSITION Z=141.5'])

    def test_done_turns_motors_off(self):
        self.unlock()
        self.app.st.update({'toolhead': {'homed_axes': 'xyz'}})
        self.app.render()
        self.tap_tid('done')
        self.assertFalse(self.app.free_move)
        self.assertEqual(self.rpc.scripts[-1], 'M84')

    def test_leaving_page_turns_motors_off(self):
        self.unlock()
        self.app.st.update({'toolhead': {'homed_axes': 'xyz'}})
        self.app.go('home')
        self.assertFalse(self.app.free_move)
        self.assertEqual(self.rpc.scripts[-1], 'M84')

    def test_timeout_without_input(self):
        self.unlock()
        self.app.st.update({'toolhead': {'homed_axes': 'xyz'}})
        self.t += 200
        self.app.jog('X', 1)
        self.t += 250
        self.app.tick()
        self.assertTrue(self.app.free_move)
        self.t += 100
        self.app.tick()
        self.assertFalse(self.app.free_move)
        self.assertEqual(self.rpc.scripts[-1], 'M84')

    def test_motors_off_elsewhere_ends_mode_silently(self):
        self.unlock()
        self.app.tick()                                 # Status noch nicht da: bleibt an
        self.assertTrue(self.app.free_move)
        self.app.st.update({'toolhead': {'homed_axes': 'xyz'}})
        self.t += 30
        self.app.st.update({'toolhead': {'homed_axes': ''}})
        self.app.tick()
        self.assertFalse(self.app.free_move)
        self.assertNotEqual(self.rpc.scripts[-1], 'M84')

    def test_not_offered_when_homed_or_printing(self):
        self.app.st.update({'toolhead': {'homed_axes': 'xyz'}})
        self.app._status_changed()
        self.app.render()
        self.assertNotIn('freemove', self.tids())
        self.app.st.update({'toolhead': {'homed_axes': ''}, 'print_stats': {'state': 'printing'}})
        self.app._status_changed()
        self.app.render()
        self.assertNotIn('freemove', self.tids())
        self.app.confirm_free_move()
        self.assertIsNone(self.app.dialog)

    def test_offered_after_failed_print_but_not_on_klipper_error(self):
        self.app.st.update({'print_stats': {'state': 'error'}})
        self.app._status_changed()
        self.app.close_dialog()                         # Fehlermeldung zum Druck
        self.app.render()
        self.assertIn('freemove', self.tids())
        self.app.st.update({'webhooks': {'state': 'shutdown'}})
        self.app._status_changed()
        self.app.render()
        self.assertNotIn('freemove', self.tids())


if __name__ == '__main__':
    unittest.main()
