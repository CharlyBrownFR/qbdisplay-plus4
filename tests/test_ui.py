# qbdisplay – Tests: Hit-Testing, Dirty-Rects, Bedienabläufe
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import unittest

from tests import helpers  # noqa: F401
from qbdisplay.canvas import Canvas, ListSink, Rect
from qbdisplay.ui.core import Frame, Renderer
from qbdisplay.ui import dialogs
import scenarios


def gcodes(app):
    return [p['script'] for m, p in app.rpc.calls if m == 'printer.gcode.script']


class HitTest(unittest.TestCase):
    def test_topmost_wins(self):
        f = Frame()
        f.target('a', Rect(0, 0, 100, 100), None)
        f.target('b', Rect(50, 50, 100, 100), None)
        self.assertEqual(f.hit(60, 60).tid, 'b')
        self.assertEqual(f.hit(10, 10).tid, 'a')

    def test_tolerance_and_disabled(self):
        f = Frame()
        f.target('a', Rect(100, 100, 50, 50), None)
        f.target('off', Rect(0, 0, 50, 50), None, enabled=False)
        self.assertEqual(f.hit(97, 120).tid, 'a')    # 3 px daneben
        self.assertIsNone(f.hit(80, 120))            # zu weit
        self.assertIsNone(f.hit(10, 10))             # deaktiviert


class RendererTest(unittest.TestCase):
    def test_only_changed_regions(self):
        sink = ListSink()
        r = Renderer(Canvas(sink))
        drawn = []

        def frame(val):
            f = Frame()
            f.region('a', Rect(0, 0, 10, 10), 1, lambda c, rr: drawn.append('a'))
            f.region('b', Rect(20, 0, 10, 10), val, lambda c, rr: drawn.append('b'))
            f.region('child', Rect(22, 2, 4, 4), 0, lambda c, rr: drawn.append('child'))
            return f
        r.render(frame(1), 'p')
        self.assertEqual(drawn, ['a', 'b', 'child'])
        del drawn[:]
        self.assertEqual(r.render(frame(1), 'p'), 0)
        r.render(frame(2), 'p')
        self.assertEqual(drawn, ['b', 'child'])      # Kind liegt im geänderten Bereich
        del drawn[:]
        r.render(frame(2), 'q')                      # Seitenwechsel -> alles
        self.assertEqual(drawn, ['a', 'b', 'child'])

    def test_removed_region_cleared(self):
        sink = ListSink()
        r = Renderer(Canvas(sink))
        f = Frame()
        f.region('t', Rect(5, 5, 10, 10), 1, lambda c, rr: None, clear='#FFFFFF')
        r.render(f, 'p')
        del sink.commands[:]
        r.render(Frame(), 'p')
        self.assertEqual(sink.commands, ['fill 5,5,10,10,65535'])


class AppFlowTest(unittest.TestCase):
    def make(self, scenario=None):
        sink = ListSink()
        app = scenarios.make_app(sink)
        if scenario:
            scenario(app)
        app.render()
        return app, sink

    def target_rect(self, app, tid):
        for t in app.frame.targets:
            if t.tid == tid:
                return t.rect
        raise AssertionError('Ziel %s fehlt (%s)' % (tid, [t.tid for t in app.frame.targets]))

    def tap(self, app, tid):
        r = self.target_rect(app, tid)
        app.tap(r.cx, r.cy)
        app.render()

    def test_incremental_update_is_small(self):
        app, sink = self.make(scenarios.s_home_idle)
        del sink.commands[:]
        app.handle('status', {'extruder': {'temperature': 46.0}})
        app.render()
        self.assertGreater(len(sink.commands), 0)
        self.assertLess(len(sink.commands), 12)
        del sink.commands[:]
        app.render()
        self.assertEqual(sink.commands, [])

    def test_nav(self):
        app, _ = self.make(scenarios.s_home_idle)
        self.tap(app, 'nav.filament')
        self.assertEqual(app.page_name, 'filament')
        self.tap(app, 'nav.move')
        self.assertEqual(app.page_name, 'move')

    def test_load_slot(self):
        app, _ = self.make(scenarios.s_filament)
        self.tap(app, 'act.main')
        self.assertEqual(gcodes(app), ['MMU_SELECT GATE=1\nMMU_LOAD'])

    def test_unload_loaded_slot(self):
        app, _ = self.make(scenarios.s_filament)
        self.tap(app, 'card.0')
        self.tap(app, 'act.main')
        self.assertEqual(gcodes(app), ['MMU_UNLOAD'])

    def test_eject_needs_confirmation(self):
        app, _ = self.make(scenarios.s_filament)
        self.tap(app, 'act.eject')
        self.assertIsInstance(app.dialog, dialogs.ConfirmDialog)
        self.assertEqual(gcodes(app), [])
        self.tap(app, 'yes')
        self.assertIsNone(app.dialog)
        self.assertEqual(gcodes(app), ['MMU_EJECT GATE=1'])

    def test_empty_slot_has_no_load(self):
        app, _ = self.make(scenarios.s_filament)
        self.tap(app, 'card.3')
        self.assertNotIn('act.main', [t.tid for t in app.frame.targets])

    def test_slot_edit_save(self):
        app, _ = self.make(scenarios.s_slot_edit)
        self.tap(app, 'm.1')     # PLA Matte
        self.tap(app, 'c.3')     # Farbe 4
        self.tap(app, 'save')
        self.assertEqual(gcodes(app), ['MMU_GATE_MAP GATE=1 NAME="PLA Matte" MATERIAL=PLA '
                                       'COLOR=c62828 VENDOR="QIDI" TEMP=210'])
        self.assertEqual(app.page_name, 'filament')

    def test_slot_edit_save_qidi_variables(self):
        app, _ = self.make(scenarios.s_slot_edit)
        app.cfg.cp.set('box', 'gate_map_direct', 'no')
        self.tap(app, 'm.1')
        self.tap(app, 'c.3')
        self.tap(app, 'save')
        self.assertEqual(gcodes(app), ['SAVE_VARIABLE VARIABLE=filament_slot1 VALUE=2\n'
                                       'SAVE_VARIABLE VARIABLE=color_slot1 VALUE=4\n'
                                       'SAVE_VARIABLE VARIABLE=vendor_slot1 VALUE=1'])

    def test_commands_configurable_qidi_compat(self):
        app, _ = self.make(scenarios.s_filament)
        app.cfg.cp.set('box', 'cmd_load', 'E_LOAD SLOT=slot{gate}')
        self.tap(app, 'act.main')
        self.assertEqual(gcodes(app), ['E_LOAD SLOT=slot1'])

    def test_part_fan_as_klipper_fan(self):
        app, _ = self.make(scenarios.s_move)
        app.cfg.cp.set('printer', 'fan_part', 'fan')
        app.st.update({'fan': {'speed': 0.0}})
        app._status_changed()
        app.render()
        self.tap(app, 'f.fan_part')
        self.assertEqual(gcodes(app), ['M106 S128'])

    def test_drying_start_capped(self):
        app, _ = self.make(scenarios.s_drying_select)
        for _ in range(5):
            self.tap(app, 'adj.t+')
            if 'adj.t+' not in [t.tid for t in app.frame.targets]:
                break
        self.tap(app, 'start')
        self.assertEqual(gcodes(app), [])              # erst Rückfrage
        self.tap(app, 'yes')
        self.assertEqual(gcodes(app), ['MMU_HEATER DRY=1 TEMP=65 TIMER=720'])
        self.assertEqual(app.drying_tracker.data['temp'], 65)

    def test_drying_cancel(self):
        app, _ = self.make(scenarios.s_drying_running)
        self.tap(app, 'abort')
        self.tap(app, 'yes')
        self.assertEqual(gcodes(app), ['MMU_HEATER STOP=1'])
        self.assertIsNone(app.drying_tracker.data)

    def test_drying_plus_one_hour(self):
        app, _ = self.make(scenarios.s_drying_running)
        self.tap(app, 'plus1')
        self.assertEqual(gcodes(app), ['MMU_HEATER DRY=1 TEMP=55 TIMER=522'])

    def test_error_dialog_opens_and_retries(self):
        app, _ = self.make(scenarios.s_error)
        self.assertIsInstance(app.dialog, dialogs.ErrorDialog)
        self.assertEqual(app.dialog.err['info'].code, 'QDE_004_006')
        self.tap(app, 'retry')
        self.assertEqual(gcodes(app), ['MMU_UNLOCK\nRESUME'])

    def test_error_dismiss_stays_closed(self):
        app, _ = self.make(scenarios.s_error)
        self.tap(app, 'alt')
        self.assertIsNone(app.dialog)
        app.handle('status', {'extruder': {'temperature': 239.0}})
        self.assertIsNone(app.dialog)

    def test_command_error_shows_dialog(self):
        app, _ = self.make(scenarios.s_filament)
        app.show_command_error('QDE_004_001 Slot loading failure', 'E_LOAD SLOT=slot1',
                               {'gate': 1, 'what': 'Beim Laden von Slot B'})
        app.render()
        self.assertIsInstance(app.dialog, dialogs.ErrorDialog)
        self.tap(app, 'retry')
        self.assertEqual(gcodes(app), ['E_LOAD SLOT=slot1'])

    def test_jog_and_step(self):
        app, _ = self.make(scenarios.s_move)
        self.tap(app, 'step.0')
        self.tap(app, 'x+')
        self.tap(app, 'z-')
        self.assertEqual(gcodes(app), ['G91\nG1 X0.100 F6000\nG90', 'G91\nG1 Z-0.100 F600\nG90'])

    def test_extruder_locked_when_cold(self):
        app, _ = self.make(scenarios.s_move)
        self.assertNotIn('extrude', [t.tid for t in app.frame.targets])

    def test_cancel_print_confirm(self):
        app, _ = self.make(scenarios.s_home_print)
        self.tap(app, 'cancel')
        self.tap(app, 'yes')
        self.assertEqual(gcodes(app), ['CANCEL_PRINT'])

    def test_temp_dialog(self):
        app, _ = self.make(scenarios.s_home_idle)
        self.tap(app, 'temp.extruder')
        self.tap(app, 'pre2')      # PETG 240
        self.tap(app, 'p0')        # +1
        self.tap(app, 'yes')
        self.assertEqual(gcodes(app), ['SET_HEATER_TEMPERATURE HEATER=extruder TARGET=241'])

    def test_light_toggle(self):
        app, _ = self.make(scenarios.s_home_idle)
        self.tap(app, 'light')
        self.assertEqual(gcodes(app), ['SET_PIN PIN=caselight VALUE=0'])

    def test_print_file_confirm(self):
        app, _ = self.make(scenarios.s_files)
        self.tap(app, 'row.1')
        self.tap(app, 'yes')
        self.assertIn(('printer.print.start', {'filename': 'halter_v3.gcode'}), app.rpc.calls)

    def test_press_release_elsewhere_cancels(self):
        app, _ = self.make(scenarios.s_home_idle)
        r = self.target_rect(app, 'light')
        app.handle_touch(r.cx, r.cy, True)
        self.assertEqual(app.pressed, 'light')
        app.handle_touch(5, 5, False)
        self.assertEqual(gcodes(app), [])

    def test_all_scenarios_render_without_missing_icons(self):
        for name, fn in scenarios.SCENARIOS:
            missing = []
            app = scenarios.make_app(ListSink())
            app.canvas.missing_icon_cb = missing.append
            fn(app)
            app.render()
            self.assertEqual(missing, [], name)


if __name__ == '__main__':
    unittest.main()
