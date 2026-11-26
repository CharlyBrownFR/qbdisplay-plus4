# qbdisplay – Tests: Werkzeug -> Slot vor dem Druck
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.

import unittest

from tests import helpers  # noqa: F401


class SuggestTest(unittest.TestCase):
    def test_type_and_nearest_colour_each_slot_once(self):
        from qbdisplay import model
        tools = [(0, 'PETG', '#FF362D'), (1, 'PETG', '#1714B0'), (2, 'ASA', '#FAFAFA')]
        cands = [(0, 'PETG', '#1714B0'), (1, 'PETG', '#FF362D'), (2, 'ASA', '#FAFAFA')]
        self.assertEqual(model.suggest_tool_map(tools, cands), {0: 1, 1: 0, 2: 2})

    def test_no_match(self):
        from qbdisplay import model
        self.assertEqual(model.suggest_tool_map([(0, 'TPU', None)], [(0, 'PLA', '#000000')]),
                         {0: None})

    def test_file_tools(self):
        from qbdisplay import model
        meta = {'used_extruders': [0, 2], 'filament_type': 'PETG;PETG;ASA',
                'preset_colours': ['#111111', '#222222', '#333333']}
        self.assertEqual(model.file_tools(meta), [(0, 'PETG', '#111111'), (2, 'ASA', '#333333')])
        self.assertEqual(model.file_tools({}), [])


class DialogTest(unittest.TestCase):
    def setUp(self):
        from tools import scenarios
        from qbdisplay.canvas import ListSink
        self.scenarios = scenarios
        self.app = scenarios.make_app(ListSink())
        self.sent, self.calls = [], []

        def gcode(cmd, *a, **k):
            self.sent.append(cmd)
            if k.get('on_done'):
                k['on_done']()
        self.app.gcode = gcode
        self.app.rpc_call = lambda m, p=None, label=None: self.calls.append((m, p))

    def test_dialog_and_commands(self):
        from qbdisplay.ui.dialogs import ToolMapDialog
        self.scenarios.s_print_tool_map(self.app)
        dlg = self.app.dialog
        self.assertIsInstance(dlg, ToolMapDialog)
        self.assertTrue(dlg.ready())
        dlg._print()
        self.assertEqual(self.sent, ['SAVE_VARIABLE VARIABLE=value_t0 VALUE="\'slot1\'"\n'
                                     'SAVE_VARIABLE VARIABLE=value_t1 VALUE="\'slot0\'"\n'
                                     'SAVE_VARIABLE VARIABLE=value_t2 VALUE="\'slot2\'"'])
        self.assertEqual(self.calls, [('printer.print.start', {'filename': 'front.gcode'})])

    def test_rack_is_slot16(self):
        self.scenarios.s_print_tool_map_missing(self.app)
        self.app.dialog._print()
        self.assertIn('VARIABLE=value_t3 VALUE="\'slot16\'"', self.sent[0])

    def test_cycle_and_unmatched_blocks(self):
        self.scenarios.s_print_tool_map(self.app)
        dlg = self.app.dialog
        dlg.mapping[0] = None
        self.assertFalse(dlg.ready())
        dlg.cycle(0)
        self.assertIsNotNone(dlg.mapping[0])

    def test_happy_hare_plain_confirm(self):
        from qbdisplay.ui.dialogs import ConfirmDialog
        self.app._meta['front.gcode'] = dict(self.scenarios.FRONT_META, used_extruders=[0],
                                             filament_type='PLA')
        self.app.confirm_print('front.gcode')
        self.assertIsInstance(self.app.dialog, ConfirmDialog)


if __name__ == '__main__':
    unittest.main()
