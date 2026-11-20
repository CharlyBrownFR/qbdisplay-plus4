# qbdisplay – Tests: Zustandslogik (Slots, Farbwechsel, Trocknung, Fehler)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import copy
import os
import tempfile
import unittest

from tests import helpers  # noqa: F401
from qbdisplay import errors, model
from qbdisplay.filaments import FilamentList
import scenarios

FLIST = FilamentList(os.path.join(scenarios.SAMPLES, 'filas_sample.cfg'))


def status(**mmu):
    st = model.Status(copy.deepcopy(scenarios.BASE_STATUS))
    if mmu:
        st.update({'mmu': mmu})
    return st


class StatusTest(unittest.TestCase):
    def test_merge_nested(self):
        st = model.Status({'print_stats': {'state': 'printing', 'info': {'current_layer': 1,
                                                                        'total_layer': 9}}})
        st.update({'print_stats': {'info': {'current_layer': 2}}})
        self.assertEqual(st.get('print_stats', 'info'), {'current_layer': 2, 'total_layer': 9})
        self.assertEqual(st.get('print_stats', 'state'), 'printing')


class SlotStateTest(unittest.TestCase):
    def test_states_from_mmu(self):
        st = status()
        views = model.slots(st, FLIST)
        self.assertEqual([v.state for v in views], ['loaded', 'ready', 'ready', 'empty'])
        self.assertEqual(views[0].name, 'PLA Wood')
        self.assertEqual(views[0].temps, (190, 230))
        self.assertEqual(views[1].color_name, 'Schwarz')
        self.assertEqual(views[2].letter, 'C')

    def test_loading_and_unloading(self):
        st = status(gate=2, filament_pos=4, action='Loading')
        self.assertEqual(model.slot_state(st.mmu, 2), 'loading')
        self.assertEqual(model.slot_state(st.mmu, 0), 'ready')
        st = status(gate=0, filament_pos=10, action='Unloading')
        self.assertEqual(model.slot_state(st.mmu, 0), 'unloading')

    def test_unknown(self):
        st = status(gate_status=[-1, 1, 1, 0], gate=1)
        self.assertEqual(model.slot_state(st.mmu, 0), 'unknown')

    def test_loaded_slot_and_bypass(self):
        self.assertEqual(model.loaded_slot(status()), 0)
        self.assertIsNone(model.loaded_slot(status(filament_pos=0)))
        st = status(gate=-2, filament_pos=10)
        self.assertEqual(model.rack_view(st).state, 'loaded')
        self.assertEqual(model.letter(-2), 'Rack')

    def test_matches_compat_mapping(self):
        """Gleiche Zustände wie qidi_box_compat.slot_state (0/1/2/3)."""
        qidi = {'empty': 0, 'ready': 1, 'loaded': 2, 'loading': 3}
        st = status(gate=1, filament_pos=5, action='Idle')
        self.assertEqual(qidi[model.slot_state(st.mmu, 1)], 3)


class PrinterStateTest(unittest.TestCase):
    def test_states(self):
        st = status()
        self.assertEqual(model.printer_state(st), 'idle')
        self.assertEqual(model.printer_state(st, connected=False), 'offline')
        st.update({'print_stats': {'state': 'printing'}})
        self.assertEqual(model.printer_state(st), 'printing')
        st.update({'print_stats': {'state': 'paused'}})
        self.assertEqual(model.printer_state(st), 'paused')
        st.update({'mmu': {'reason_for_pause': 'x'}})
        self.assertEqual(model.printer_state(st), 'paused_error')
        st.update({'webhooks': {'state': 'shutdown'}})
        self.assertEqual(model.printer_state(st), 'error')

    def test_print_view(self):
        st = status()
        st.update({'print_stats': {'state': 'printing', 'filename': 'a.gcode',
                                   'print_duration': 100.0},
                   'display_status': {'progress': 0.5}})
        pv = model.print_view(st, {}, now=1000.0)
        self.assertAlmostEqual(pv.remaining, 100.0)
        self.assertAlmostEqual(pv.eta, 1100.0)


class HumidityTest(unittest.TestCase):
    def test_rating(self):
        self.assertEqual(model.humidity_rating(45, ['PLA', 'PETG'])[0], 'warn')
        self.assertEqual(model.humidity_rating(45, ['PLA', 'PETG'])[1], 'für PETG zu feucht')
        self.assertEqual(model.humidity_rating(30, ['PLA'])[0], 'ok')
        self.assertEqual(model.humidity_rating(70, ['PETG'])[0], 'err')
        self.assertEqual(model.humidity_rating(None, [])[0], 'none')

    def test_suggest_profile(self):
        profiles = [('PLA', 55, 12, ['PLA']), ('PETG', 55, 12, ['PETG']),
                    ('ABS/ASA', 60, 12, ['ABS', 'ASA'])]
        self.assertEqual(model.suggest_profile(profiles, ['PLA', 'PETG']), (1, 'PETG'))
        self.assertEqual(model.suggest_profile(profiles, ['ABS', 'PLA-CF']), (0, 'PLA'))
        self.assertEqual(model.suggest_profile(profiles, []), (0, None))


class ToolchangeTest(unittest.TestCase):
    def test_phases(self):
        st = status(gate=1, tool=1, num_toolchanges=1)
        st.update({'print_stats': {'state': 'printing'}})
        tr = model.ToolchangeTracker(150)
        tr.update(st, 0)
        self.assertFalse(tr.active)
        st.update({'save_variables': {'variables': {'is_tool_change': 1}},
                   'mmu': {'action': 'Cutting Tip', 'next_tool': 0}})
        tr.update(st, 10)
        v = tr.view(st, 10)
        self.assertTrue(v.active)
        self.assertEqual((v.phase, v.number, v.from_gate, v.to_gate), ('cut', 2, 1, 0))
        st.update({'mmu': {'action': 'Unloading', 'filament_pos': 3}})
        tr.update(st, 20)
        self.assertEqual(tr.phase, 'unload')
        st.update({'mmu': {'action': 'Loading', 'gate': 0, 'filament_pos': 4}})
        tr.update(st, 60)
        self.assertEqual(tr.phase, 'load')
        st.update({'mmu': {'action': 'Idle', 'gate': 0, 'filament_pos': 10}})
        tr.update(st, 100)
        self.assertEqual(tr.phase, 'purge')
        v = tr.view(st, 175)
        self.assertAlmostEqual(v.purge_frac, 0.5)
        self.assertAlmostEqual(v.remaining, 75 + 10)
        # Phasen laufen nicht rückwärts
        st.update({'mmu': {'action': 'Loading'}})
        tr.update(st, 180)
        self.assertEqual(tr.phase, 'purge')
        st.update({'save_variables': {'variables': {'is_tool_change': 0}},
                   'mmu': {'action': 'Idle'}})
        tr.update(st, 260)
        self.assertFalse(tr.active)

    def test_purge_volume(self):
        st = status(toolchange_purge_volume=380)
        tr = model.ToolchangeTracker(150)
        self.assertAlmostEqual(tr.purge_seconds(st), 100.0)

    def test_reset_when_not_printing(self):
        st = status(action='Loading')
        tr = model.ToolchangeTracker()
        tr.update(st, 0)
        self.assertFalse(tr.active)


class DryingTest(unittest.TestCase):
    def test_tracker_persist_and_view(self):
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        os.remove(path)
        try:
            tr = model.DryingTracker(path)
            tr.start('PETG', 55, 720, 1000.0, 45.0)
            tr2 = model.DryingTracker(path)
            self.assertEqual(tr2.data['profile'], 'PETG')
            v = tr2.view((54.0, 55.0, 31.0, True), 1000.0 + 360 * 60)
            self.assertTrue(v.active and v.known)
            self.assertAlmostEqual(v.frac, 0.5)
            self.assertAlmostEqual(v.remaining, 360 * 60)
            tr2.extend(60)
            self.assertEqual(tr2.remaining_minutes(1000.0 + 360 * 60), 420)
            # Heizung aus -> nach 30 s aufräumen
            tr2.update(0.0, 1000.0 + 400 * 60)
            tr2.update(0.0, 1000.0 + 400 * 60 + 31)
            self.assertIsNone(tr2.data)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_unknown_start(self):
        tr = model.DryingTracker(None)
        v = tr.view((50.0, 55.0, None, True), 0)
        self.assertTrue(v.active)
        self.assertFalse(v.known)


class ErrorsTest(unittest.TestCase):
    def test_qde(self):
        e = errors.classify('!! QDE_004_006 Extruder loading failure')
        self.assertEqual(e.code, 'QDE_004_006')
        self.assertEqual(e.title, 'Filament erreicht den Extruder nicht')
        self.assertEqual(len(e.steps), 3)

    def test_hh_reason(self):
        e = errors.classify('Failed to load filament to extruder: sensor not triggered')
        self.assertEqual(e.title, 'Filament erreicht den Extruder nicht')
        e = errors.classify('Runout detected on gate 2')
        self.assertEqual(e.title, 'Filament aufgebraucht')

    def test_unknown(self):
        e = errors.classify('Something odd')
        self.assertEqual(e.title, 'Box angehalten')
        self.assertEqual(e.steps[0], 'Something odd')

    def test_filament_path(self):
        nodes, links = errors.filament_path(
            {'mmu_entry_0': True, 'mmu_shared_exit': True, 'extruder': False}, 0)
        self.assertEqual(links, ['ok', 'ok', 'bad'])
        self.assertEqual(nodes[3].state, 'bad')
        nodes, links = errors.filament_path({'mmu_entry_1': True, 'mmu_shared_exit': False,
                                             'extruder': False}, 1)
        self.assertEqual(links, ['bad', 'unknown', 'unknown'])
        nodes, links = errors.filament_path({}, None)
        self.assertEqual(links, ['unknown'] * 3)

    def test_normalize_sensors_gate_form(self):
        # HH v4 liefert bei gewaehltem Gate die Kurzform ohne Index (Review H2)
        s = model.normalize_sensors({'mmu_entry': True, 'mmu_shared_exit': True, 'extruder': False}, 2)
        self.assertEqual(s['mmu_entry_2'], True)
        nodes, links = errors.filament_path(s, 2)
        self.assertEqual(nodes[0].state, 'ok')
        # Unit-Form bleibt unveraendert, kein Gate -> keine Ergaenzung
        s = model.normalize_sensors({'mmu_entry_1': False, 'mmu_entry': True}, 1)
        self.assertEqual(s['mmu_entry_1'], False)
        self.assertEqual(model.normalize_sensors({'mmu_entry': True}, None), {'mmu_entry': True})

    def test_drying_active_from_hh_state(self):
        self.assertTrue(model.drying_active({'drying_state': ['active', 'none', 'none', 'none']}))
        self.assertFalse(model.drying_active({'drying_state': ['none'] * 4}))
        self.assertFalse(model.drying_active({}))
        st = model.Status({'mmu': {'drying_state': ['active']},
                           'heater_generic unit0_heater': {'temperature': 40.0, 'target': 0.0},
                           'temperature_sensor unit0_Env': {'temperature': 40.5, 'humidity': 20.0}})
        temp, target, hum, heating = model.box_climate(st, 'heater_generic unit0_heater',
                                                       'temperature_sensor unit0_Env')
        self.assertTrue(heating)
        self.assertEqual((temp, hum), (40.5, 20.0))

    def test_fan_object_and_gcode(self):
        self.assertEqual(model.fan_object('fan'), 'fan')
        self.assertEqual(model.fan_object('cooling_fan'), 'fan_generic cooling_fan')
        self.assertEqual(model.fan_gcode('fan', 0.5), 'M106 S128')
        self.assertEqual(model.fan_gcode('cooling_fan', 1.0), 'SET_FAN_SPEED FAN=cooling_fan SPEED=1.00')


class FormatTest(unittest.TestCase):
    def test_duration(self):
        self.assertEqual(model.fmt_duration(5880), '1 h 38 min')
        self.assertEqual(model.fmt_duration(27720, 'clock'), '7:42 h')
        self.assertEqual(model.fmt_duration(95, 'ms'), '1:35 min')
        self.assertEqual(model.fmt_duration(None), '–')

    def test_clock_tomorrow(self):
        now = scenarios.NOW
        self.assertEqual(model.fmt_clock(now + 12 * 3600, now), 'morgen 02:32')
        self.assertEqual(model.fmt_clock(now + 3600, now), '15:32')


class FilamentListTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(FLIST.name(3), 'PLA Wood')
        self.assertEqual(FLIST.ftype(4), 'PETG')
        self.assertEqual(FLIST.colors[1], '#151515')
        self.assertEqual(FLIST.vendors[1], 'QIDI')

    def test_find(self):
        self.assertEqual(FLIST.find('pla-wood'), 3)
        self.assertEqual(FLIST.find('', 'ABS'), 6)
        self.assertIsNone(FLIST.find('xyz', 'nope'))
        self.assertEqual(FLIST.find_color('#141414'), 1)
        self.assertEqual(FLIST.find_vendor('qidi'), 1)

    def test_missing_file(self):
        fl = FilamentList('/nicht/vorhanden.cfg')
        self.assertEqual(fl.filament_ids(), [])


if __name__ == '__main__':
    unittest.main()
