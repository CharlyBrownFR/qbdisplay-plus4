# qbdisplay – Tests: Box-Zustand der QIDI-Stock-Firmware 2.1.1 (echter Status vom Plus4)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import copy
import json
import os
import tempfile
import unittest

from tests import helpers  # noqa: F401
from qbdisplay import model, qidi
from qbdisplay.config import Config

with open(os.path.join(os.path.dirname(__file__), 'data', 'qidi211_status.json'),
          encoding='utf-8') as f:
    REAL = json.load(f)


def status(**changes):
    data = copy.deepcopy(REAL)
    for obj, fields in changes.items():
        data.setdefault(obj, {}).update(fields)
    return model.Status(data)


class SlotNumberTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(qidi.slot_number('slot3'), 3)
        self.assertEqual(qidi.slot_number('slot16'), 16)
        self.assertIsNone(qidi.slot_number('slot-1'))
        self.assertIsNone(qidi.slot_number(None))


class SynthTest(unittest.TestCase):
    def test_real_status(self):
        st = status()
        mmu = st.mmu
        self.assertEqual(mmu['source'], 'qidi')
        # Spulen in Slot 0-2, Slot 3 leer
        self.assertEqual(mmu['gate_status'], [1, 1, 1, 0])
        # externe Spule (slot16) geladen
        self.assertEqual(mmu['gate'], model.HH_GATE_BYPASS)
        self.assertEqual(mmu['filament_pos'], model.HH_POS_LOADED)
        self.assertEqual(mmu['gate_material'][2], 'ASA')
        self.assertEqual(mmu['gate_filament_name'][0], 'PETG Rapido')
        self.assertEqual(mmu['gate_color'][1], '#FF362D')
        self.assertEqual(mmu['ttg_map'], [0, 1, 2, 2])
        self.assertEqual(mmu['action'], 'Idle')

    def test_slot_views(self):
        st = status()
        views = model.slots(st)
        self.assertEqual([v.state for v in views], ['ready', 'ready', 'ready', 'empty'])
        self.assertEqual(views[0].name, 'PETG Rapido')
        self.assertEqual(views[2].temps, (240, 280))
        self.assertEqual(model.rack_view(st).state, 'loaded')
        self.assertIsNone(model.loaded_slot(st) if model.loaded_slot(st) != model.HH_GATE_BYPASS
                          else None)

    def test_loaded_box_slot(self):
        st = status(box_extras={'loaded_slot': 'slot1'})
        self.assertEqual(model.loaded_slot(st), 1)
        self.assertEqual(model.slot_state(st.mmu, 1), 'loaded')

    def test_running_task(self):
        st = status(multi_color_controller={'task': {'type': 'unload'},
                                            'operation': {'operate_state': 1,
                                                          'active_slot': 'slot2'}})
        self.assertEqual(st.mmu['action'], 'Unloading')
        self.assertEqual(model.slot_state(st.mmu, 2), 'unloading')

    def test_drying(self):
        boxes = copy.deepcopy(REAL['box_extras']['boxes'])
        boxes[0]['dry_state'] = 1
        boxes[0]['box_target_temp'] = 55
        st = status(box_extras={'boxes': boxes},
                    **{'heater_generic heater_box1': {'target': 55.0}})
        self.assertTrue(model.drying_active(st.mmu))
        climate = model.box_climate(st, 'heater_generic heater_box1', 'aht20_f heater_box1')
        self.assertEqual(climate[2], 54)
        self.assertTrue(climate[3])

    def test_box_offline(self):
        boxes = copy.deepcopy(REAL['box_extras']['boxes'])
        boxes[0]['is_online'] = 0
        st = status(box_extras={'boxes': boxes})
        self.assertEqual(st.mmu['gate_status'], [0, 0, 0, 0])

    def test_happy_hare_wins(self):
        st = status(mmu={'gate': 2, 'filament_pos': 10})
        self.assertEqual(st.mmu['gate'], 2)

    def test_cache_invalidated(self):
        st = status()
        self.assertEqual(st.mmu['gate'], model.HH_GATE_BYPASS)
        st.update({'box_extras': {'loaded_slot': 'slot0'}})
        self.assertEqual(st.mmu['gate'], 0)


EXTRA = {'identity': 'external', 'filament_info': {
    'filament_id': 'QFA02', 'filament_str': 'PLA Rapido', 'filament_type': 'PLA',
    'color_rgb_str': ['#FAFAFA'], 'vendor_str': 'QIDI', 'min_temp': 190, 'max_temp': 240,
    'box_min_temp': 0, 'box_max_temp': 0, 'filament_per': 100}}


def no_box_status():
    """Zustand nach Abziehen der Box (am Plus4 gelesen 2026-11-21)."""
    data = copy.deepcopy(REAL)
    # nach dem Neustart gibt es box_extras gar nicht mehr (am Plus4 gelesen)
    data.pop('box_extras', None)
    data['multi_color_controller'].update(box_count=0, extra=EXTRA)
    data['multi_color_controller'].setdefault('operation', {})['active_slot'] = 'slot16'
    for k in ('aht20_f heater_box1', 'heater_generic heater_box1'):
        data.pop(k, None)
    return data


class NoBoxTest(unittest.TestCase):
    def test_box_extras_still_empty(self):
        # Übergang vor dem Klipper-Neustart: box_extras da, aber ohne Boxen
        data = no_box_status()
        data['box_extras'] = {'boxes': [], 'loaded_slot': ''}
        st = model.Status(data)
        self.assertEqual(model.box_units(st), [])
        self.assertEqual(model.loaded_slot(st), model.HH_GATE_BYPASS)

    def test_detect(self):
        st = model.Status(no_box_status())
        self.assertEqual(model.box_units(st), [])
        self.assertEqual(model.box_units(status()), [0])

    def test_external_spool_loaded(self):
        st = model.Status(no_box_status())
        self.assertEqual(model.loaded_slot(st), model.HH_GATE_BYPASS)
        rack = model.rack_view(st)
        self.assertEqual(rack.state, 'loaded')
        self.assertEqual(rack.name, 'PLA Rapido')
        self.assertEqual(rack.material, 'PLA')
        self.assertEqual(rack.temps, (190, 240))

    def test_rack_info_with_box(self):
        st = status(multi_color_controller=dict(REAL['multi_color_controller'], extra=EXTRA))
        self.assertEqual(model.rack_view(st).name, 'PLA Rapido')

    def test_offline_box_is_no_box(self):
        boxes = copy.deepcopy(REAL['box_extras']['boxes'])
        boxes[0]['is_online'] = 0
        self.assertEqual(model.box_units(status(box_extras={'boxes': boxes})), [])

    def test_two_boxes(self):
        boxes = copy.deepcopy(REAL['box_extras']['boxes'])
        second = copy.deepcopy(boxes[0])
        second['box_inserted_3'] = 1
        offline = dict(copy.deepcopy(boxes[0]), is_online=0)
        st = status(box_extras={'boxes': boxes + [second, offline, offline],
                                'loaded_slot': 'slot7'})
        self.assertEqual(model.box_units(st), [0, 1])
        self.assertEqual(len(st.mmu['gate_status']), 16)
        self.assertEqual(model.loaded_slot(st), 7)
        self.assertEqual(model.slot_state(st.mmu, 7), 'loaded')
        self.assertEqual(model.slot_state(st.mmu, 12), 'empty')


class NoBoxAppTest(unittest.TestCase):
    def make(self, data):
        from tools import scenarios
        from qbdisplay.canvas import ListSink
        from qbdisplay.config import QIDI_BOX
        app = scenarios.make_app(ListSink(), data)
        app.cfg.cp.read_dict({'box': dict(QIDI_BOX, backend='qidi')})
        return app

    def test_pages_render_without_box(self):
        app = self.make(no_box_status())
        self.assertFalse(app.has_box)
        self.assertEqual(app.slots, [])
        for page in ('home', 'filament', 'system', 'move', 'files'):
            app.go(page)
            app.render()
        app.set_ui(sys_sub='box')
        app.render()
        # Trocknen und Slot bearbeiten gibt es ohne Box nicht
        app.go('drying')
        self.assertEqual(app.page_name, 'filament')

    def test_unplug_while_on_drying_page(self):
        app = self.make(copy.deepcopy(REAL))
        app.go('drying')
        app.render()
        app.st = model.Status(no_box_status())
        app._status_changed()
        app.render()
        self.assertEqual(app.page_name, 'filament')

    def test_load_external_without_box(self):
        app = self.make(no_box_status())
        app.go('filament')
        app.render()
        app.unload()
        self.assertIn('E_UNLOAD SLOT=16', str(app.rpc.calls[-1]))


class ConfigTest(unittest.TestCase):
    def _cfg(self, text):
        fd, path = tempfile.mkstemp(suffix='.cfg')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        self.addCleanup(os.remove, path)
        return Config(path)

    def test_qidi_defaults(self):
        cfg = self._cfg('[box]\nbackend: qidi\n')
        self.assertEqual(cfg.command('cmd_load', gate=2), 'E_LOAD SLOT=2')
        self.assertEqual(cfg.get('box', 'heater'), 'heater_generic heater_box1')
        self.assertFalse(cfg.getbool('box', 'gate_map_direct'))

    def test_qidi_drying(self):
        cfg = self._cfg('[box]\nbackend: qidi\n')
        self.assertEqual(cfg.command('cmd_dry_start', temp=55, hours=8, minutes=480, end=0),
                         'ENABLE_BOX_DRY BOX=1 END_TIME=8 TEMP=55')

    def test_user_overrides_qidi(self):
        cfg = self._cfg('[box]\nbackend: qidi\ncmd_rfid: READ_RFID SLOT=slot{gate}\n')
        self.assertEqual(cfg.command('cmd_rfid', gate=1), 'READ_RFID SLOT=slot1')

    def test_happy_hare_default(self):
        cfg = self._cfg('')
        self.assertEqual(cfg.command('cmd_unload'), 'MMU_UNLOAD')


if __name__ == '__main__':
    unittest.main()
