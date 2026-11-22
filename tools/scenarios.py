# qbdisplay – Beispielzustände für Vorschau, Icon-Sammlung und Tests
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Beispieldaten nach den Entwürfen (docs/display-redesign.html): Slot A
PLA Wood in der Düse, B PLA Basic schwarz, C PETG Rapido schwarz, D leer."""

import copy
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SAMPLES = os.path.join(ROOT, 'samples')

# feste Uhrzeit: 18.10.2026 14:32 (lokal)
NOW = time.mktime((2026, 10, 18, 14, 32, 0, 0, 0, -1))

BASE_STATUS = {
    'webhooks': {'state': 'ready', 'state_message': 'Printer is ready'},
    'print_stats': {'state': 'standby', 'filename': '', 'print_duration': 0,
                    'info': {'current_layer': None, 'total_layer': None}, 'message': ''},
    'virtual_sdcard': {'progress': 0.0, 'is_active': False},
    'display_status': {'progress': 0.0},
    'pause_resume': {'is_paused': False},
    'toolhead': {'position': [150.0, 150.0, 10.0, 0.0], 'homed_axes': 'xyz'},
    'gcode_move': {'gcode_position': [150.0, 150.0, 10.0, 0.0], 'speed_factor': 1.0,
                   'extrude_factor': 1.0, 'homing_origin': [0.0, 0.0, -0.02, 0.0]},
    'extruder': {'temperature': 45.2, 'target': 0.0, 'can_extrude': False},
    'heater_bed': {'temperature': 47.1, 'target': 0.0},
    'heater_generic chamber': {'temperature': 31.0, 'target': 0.0},
    'output_pin caselight': {'value': 1.0},
    'fan_generic cooling_fan': {'speed': 0.0},
    'fan_generic auxiliary_cooling_fan': {'speed': 0.0},
    'fan_generic chamber_circulation_fan': {'speed': 0.0},
    'heater_generic unit0_heater': {'temperature': 23.0, 'target': 0.0, 'power': 0.0},
    'temperature_sensor unit0_Env': {'temperature': 23.2, 'humidity': 45.0},
    'mmu': {
        'enabled': True, 'num_gates': 4, 'print_state': 'ready', 'gate': 0, 'tool': 0,
        'filament_pos': 10, 'action': 'Idle', 'num_toolchanges': 0, 'last_tool': -1,
        'next_tool': -1, 'toolchange_purge_volume': 0, 'reason_for_pause': '',
        'gate_status': [1, 1, 1, 0],
        'gate_material': ['PLA', 'PLA', 'PETG', ''],
        'gate_filament_name': ['PLA Wood', 'PLA Basic', 'PETG Rapido', ''],
        'gate_color': ['B87F2B', '151515', '151515', ''],
        'gate_vendor': ['QIDI', 'QIDI', 'QIDI', ''],
        'gate_spool_rfid': [None, None, None, None],
        'ttg_map': [0, 1, 2, 3], 'endless_spool_enabled': 1,
        'slicer_tool_map': {'total_toolchanges': 0},
        'sensors': {'mmu_entry_0': True, 'mmu_entry_1': True, 'mmu_entry_2': True,
                    'mmu_entry_3': False, 'mmu_shared_exit': True, 'extruder': True},
    },
    'save_variables': {'variables': {
        'filament_slot0': 3, 'color_slot0': 11, 'vendor_slot0': 1,
        'filament_slot1': 1, 'color_slot1': 1, 'vendor_slot1': 1,
        'filament_slot2': 4, 'color_slot2': 1, 'vendor_slot2': 1,
        'is_tool_change': 0,
    }},
}

FRONT_META = {
    'layer_count': 51, 'estimated_time': 6840,
    'filament_colors': ['#B87F2B', '#151515'],
    'thumbnails': [{'width': 160, 'height': 160, 'relative_path': '.thumbs/front-160x160.png'}],
}

FILES = [
    {'path': 'front.gcode', 'modified': NOW - 3600 * 5, 'size': 2400000},
    {'path': 'halter_v3.gcode', 'modified': NOW - 86400, 'size': 845000},
    {'path': 'Kabelclip_x12.gcode', 'modified': NOW - 86400 * 2, 'size': 412000},
    {'path': 'Spulenhalter_Rack.gcode', 'modified': NOW - 86400 * 4, 'size': 5200000},
    {'path': 'Testwürfel_PETG.gcode', 'modified': NOW - 86400 * 9, 'size': 310000},
    {'path': 'Gehäuse_Deckel_lang_mit_sehr_langem_Namen.gcode', 'modified': NOW - 86400 * 12,
     'size': 7700000},
]


def ensure_sample_thumb():
    """Erzeugt ein eigenes Beispiel-Vorschaubild (braune Platte) mit Pillow."""
    path = os.path.join(SAMPLES, 'gcodes', '.thumbs', 'front-160x160.png')
    if os.path.exists(path):
        return path
    from PIL import Image, ImageDraw
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ss = 4
    img = Image.new('RGBA', (160 * ss, 160 * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def iso(x, y):
        return (80 * ss + (x - y) * 0.87 * ss, 88 * ss + (x + y) * 0.42 * ss)

    def quad(pts, col, dz=0):
        d.polygon([(p[0], p[1] + dz * ss) for p in (iso(*q) for q in pts)], fill=col)
    plate = [(-58, -42), (58, -42), (58, 42), (-58, 42)]
    quad(plate, (122, 82, 26, 255), dz=7)
    quad(plate, (184, 127, 43, 255))
    quad([(-26, -16), (28, -16), (28, 20), (-26, 20)], (0, 0, 0, 0))
    quad([(-50, -34), (24, -34), (24, -25), (-50, -25)], (0, 0, 0, 0))
    for (x, y) in ((42, -28), (-46, 30), (-38, -12)):
        cx, cy = iso(x, y)
        d.ellipse([cx - 3 * ss, cy - 3 * ss, cx + 3 * ss, cy + 3 * ss], fill=(224, 176, 103, 255))
    img = img.resize((160, 160), Image.LANCZOS)
    img.save(path)
    return path


def make_config():
    from qbdisplay.config import Config
    cfg = Config(os.path.join(SAMPLES, 'nicht-vorhanden.cfg'))
    cfg.cp.set('box', 'filament_list', os.path.join(SAMPLES, 'filas_sample.cfg'))
    cfg.cp.set('printer', 'gcode_dir', os.path.join(SAMPLES, 'gcodes'))
    cfg.cp.set('state', 'file', '')
    return cfg


class FakeRpc(object):
    """Nimmt Aufrufe entgegen, ohne etwas zu senden (für Vorschau/Tests)."""

    def __init__(self):
        self.calls = []

    def call(self, method, params=None, cb=None):
        self.calls.append((method, params))

    def gcode(self, script, cb=None):
        self.calls.append(('printer.gcode.script', {'script': script}))


def make_app(sink, status=None):
    from qbdisplay.app import App
    from qbdisplay import model, thumbs
    app = App(make_config(), sink, rpc=FakeRpc(), clock=lambda: NOW)
    app.drying_tracker.path = None
    app.st = model.Status(copy.deepcopy(status or BASE_STATUS))
    app.connected = True
    app.net = {'ip': '192.168.1.50', 'iface_kind': 'wifi', 'quality': 'gut', 'lan_only': True,
               'services': (('cloudoff', 'QIDI-Cloud / App', 'blockiert'),
                            ('link', 'Fernzugriff (QIDI Link)', 'blockiert'),
                            ('monitor', 'Slicer & Browser im LAN', 'aktiv'))}
    app._last_net = NOW + 10 ** 9      # kein echtes Netz abfragen
    app.versions = {'klipper': 'v0.12.0-65-g96ab9069', 'moonraker': 'v0.8.0-379-g346a3d7',
                    'display': 'TJC8048X250_011C @ 115200'}
    app.files = list(FILES)
    for f in FILES:
        app._meta[f['path']] = {'estimated_time': 3600 + len(f['path']) * 120,
                                'filament_colors': ['#151515'] if 'PETG' in f['path'] else
                                ['#F2F2F2', '#C62828']}
    app._meta['front.gcode'] = dict(FRONT_META)
    app.last_print = {'filename': 'front.gcode', 'status': 'completed',
                      'metadata': dict(FRONT_META), 'tools': []}
    app._update_last_print_meta()
    ensure_sample_thumb()
    for size in (164, 128):
        n = max(4, size // app.thumb_block)
        app._thumbs[('front.gcode', n)] = thumbs.load_mosaic(
            app.cfg.get('printer', 'gcode_dir'), 'front.gcode', FRONT_META, n)
    app._status_changed()
    return app


# ---------------------------------------------------------------------------
def s_home_idle(app):
    app.go('home')


def _printing(app, toolchange=True):
    from qbdisplay import model
    st = app.st
    st.update({'print_stats': {'state': 'printing', 'filename': 'front.gcode',
                               'print_duration': 957.0,
                               'info': {'current_layer': 7, 'total_layer': 51}},
               'virtual_sdcard': {'progress': 0.14, 'is_active': True},
               'display_status': {'progress': 0.14},
               'extruder': {'temperature': 240.0, 'target': 240.0},
               'heater_bed': {'temperature': 60.0, 'target': 60.0},
               'fan_generic cooling_fan': {'speed': 1.0}})
    st.update({'mmu': {'print_state': 'printing', 'num_toolchanges': 1,
                       'slicer_tool_map': {'total_toolchanges': 4}, 'gate': 1, 'tool': 1}})
    app.current_meta = dict(FRONT_META, _fn='front.gcode')
    if toolchange:
        tr = app.toolchange_tracker
        seq = [
            (NOW - 200, {'save_variables': {'variables': dict(
                st.variables, is_tool_change=1)}, 'mmu': {'action': 'Cutting Tip',
                                                          'next_tool': 0}}),
            (NOW - 185, {'mmu': {'action': 'Unloading', 'filament_pos': 3}}),
            (NOW - 140, {'mmu': {'action': 'Loading', 'gate': 0, 'filament_pos': 4}}),
            (NOW - 93, {'mmu': {'action': 'Idle', 'gate': 0, 'tool': 0, 'filament_pos': 10}}),
        ]
        for t, delta in seq:
            st.update(delta)
            tr.update(st, t)
    else:
        st.update({'mmu': {'gate': 0, 'tool': 0, 'filament_pos': 10, 'action': 'Idle'}})
    app._status_changed()
    assert not toolchange or app.toolchange.active, model


def s_home_print(app):
    _printing(app, True)
    app.go('home')


def s_home_print_plain(app):
    _printing(app, False)
    app.go('home')


def s_filament(app):
    app.go('filament', sel_slot=1)


def s_filament_loading(app):
    app.st.update({'mmu': {'gate': 2, 'filament_pos': 4, 'action': 'Loading'}})
    app._status_changed()
    app.go('filament', sel_slot=2)


def s_slot_edit(app):
    app.open_slot_edit(1)


def s_move(app):
    app.go('move', step=10.0)


def s_error(app):
    _printing(app, False)
    app.st.update({'print_stats': {'state': 'paused'}, 'pause_resume': {'is_paused': True},
                   'mmu': {'print_state': 'pause_locked', 'gate': 0, 'filament_pos': 4,
                           'action': 'Idle',
                           'reason_for_pause': 'QDE_004_006: Failed to load filament to '
                                               'extruder (extruder sensor not triggered)',
                           'sensors': {'mmu_entry_0': True, 'mmu_shared_exit': True,
                                       'extruder': False}}})
    app._status_changed()
    app.go('home')


def s_system_network(app):
    app.go('system', sys_sub='network')


def s_system_box(app):
    app.go('system', sys_sub='box')


def s_system_info(app):
    # feste Werte statt echter Netzabfrage
    app.update_info = {'state': 'done', 'qidi_local': (2, 1, 1), 'qidi_remote': (2, 1, 1),
                       'qidi_source': 'GitHub', 'qidi_newer': False, 'self_local': (0, 2, 0),
                       'self_remote': (0, 2, 0), 'self_newer': False, 'helper': True}
    app.go('system', sys_sub='info')


def _update_available(app):
    s_system_info(app)
    app.update_info = dict(app.update_info, self_local=(0, 4, 0), self_remote=(0, 4, 1),
                           self_newer=True)


def s_system_update_available(app):
    _update_available(app)
    app.go('system', sys_sub='info')


def s_system_update_test(app):
    """Testdrucker mit prerelease: yes – Vorabversion wird angeboten."""
    _update_available(app)
    app.update_info['self_prerelease'] = True
    app.go('system', sys_sub='info')


def s_system_update_confirm(app):
    _update_available(app)
    app.go('system', sys_sub='info')
    app.confirm_install_update()


def s_system_update_failed(app):
    """Nach dem Neustart: Update ist schiefgegangen, alte Version läuft weiter."""
    from unittest import mock
    from qbdisplay import updates
    s_system_info(app)
    st = {'state': 'failed', 'from': '0.4.0', 'to': '0.4.1',
          'message': 'qbdisplay 0.4.1 startet nicht'}
    with mock.patch.object(updates, 'read_status', lambda: st),             mock.patch.object(updates, 'clear_status', lambda: None):
        app.show_update_result()


def s_drying_select(app):
    app.go('drying')


def s_drying_running(app):
    app.st.update({'heater_generic unit0_heater': {'temperature': 54.0, 'target': 55.0,
                                                  'power': 0.4},
                   'temperature_sensor unit0_Env': {'temperature': 54.0, 'humidity': 31.0}})
    app.drying_tracker.data = {'start': NOW - (4 * 3600 + 18 * 60), 'minutes': 720, 'temp': 55,
                               'profile': 'PETG', 'hum_start': 45.0}
    app._status_changed()
    app.go('drying')


def s_files(app):
    app.go('files')


def s_confirm(app):
    app.go('filament', sel_slot=2)
    app.confirm_eject(2)


def s_temp_dialog(app):
    app.go('home')
    app.open_temp('extruder')


def s_tune(app):
    _printing(app, False)
    app.go('home')
    app.open_tune()


def s_klipper_error(app):
    app.st.update({'webhooks': {'state': 'shutdown', 'state_message':
                                'MCU \'mcu_box1\' shutdown: Timer too close'}})
    app._status_changed()
    app.go('home')


def s_home_paused(app):
    _printing(app, False)
    app.st.update({'print_stats': {'state': 'paused'}, 'pause_resume': {'is_paused': True}})
    app._status_changed()
    app.go('home')


def s_filament_unload(app):
    app.go('filament', sel_slot=0)


def s_error_command(app):
    from qbdisplay.i18n import _
    app.st.update({'mmu': {'gate': 1, 'filament_pos': 0, 'sensors': {
        'mmu_entry_1': True, 'mmu_shared_exit': False, 'extruder': False}}})
    app._status_changed()
    app.go('filament', sel_slot=1)
    app.show_command_error('QDE_004_001 Slot loading failure', 'E_LOAD SLOT=slot1',
                           {'gate': 1, 'what': _('Beim Laden von Slot %s') % 'B'})


def s_system_language(app):
    app.go('system', sys_sub='lang')


EXTERNAL = {'identity': 'external', 'filament_info': {
    'filament_str': 'PLA Rapido', 'filament_type': 'PLA', 'color_rgb_str': ['#E8731A'],
    'vendor_str': 'QIDI', 'min_temp': 190, 'max_temp': 240}}


def _qidi_box(inserted, infos, online=1):
    b = {'is_online': online, 'aht20_temp': 24.1, 'aht20_humidity': 38, 'dry_state': 0,
         'box_target_temp': 0, 'end_time': 0, 'filament_info': []}
    for k in range(4):
        b['box_inserted_%d' % k] = 1 if k < inserted else 0
        name, typ, col = infos[k] if k < len(infos) else ('', '', '')
        b['filament_info'].append({'filament_str': name, 'filament_type': typ,
                                   'color_rgb_str': [col] if col else [], 'vendor_str': 'QIDI',
                                   'min_temp': 190 if typ == 'PLA' else 240,
                                   'max_temp': 240 if typ == 'PLA' else 270})
    return b


def _qidi_status(app, boxes, loaded):
    """QIDI-Firmware statt Happy Hare: Box-Zustand aus box_extras/multi_color_controller."""
    from qbdisplay import model
    data = copy.deepcopy(BASE_STATUS)
    data.pop('mmu')
    if boxes:
        data['box_extras'] = {'boxes': boxes, 'loaded_slot': loaded}
    # ohne Box nimmt QIDI box_extras ganz aus der Config (am Plus4 gesehen)
    data['multi_color_controller'] = {
        'task': {}, 'box_warning_info': [], 'auto_reload_detect': 0, 'enable_box': 1,
        'box_count': sum(1 for b in boxes if b.get('is_online')),
        'operation': {'operate_state': 0, 'active_slot': 'slot16'}, 'extra': EXTERNAL}
    if not boxes:
        for k in ('heater_generic unit0_heater', 'temperature_sensor unit0_Env'):
            data.pop(k, None)
    app.st = model.Status(data)
    app._status_changed()


def s_filament_no_box(app):
    _qidi_status(app, [], '')
    app.go('filament')


def s_home_no_box(app):
    _qidi_status(app, [], '')
    app.go('home')


def s_print_no_box(app):
    _qidi_status(app, [], '')
    _printing(app, False)
    app.st.data.pop('mmu', None)     # _printing setzt Happy-Hare-Werte; hier QIDI ohne Box
    app.st.update({})
    app._status_changed()
    app.go('home')


def s_home_cloud_dark(app):
    """Cloud an, Licht aus, letzter Druck ohne Vorschaubild (so am Plus4 gesehen)."""
    app.net = dict(app.net, lan_only=False)
    app._thumbs.clear()
    app.last_print['metadata'] = {k: v for k, v in app.last_print['metadata'].items()
                                  if k != 'thumbnails'}
    app.st.update({'output_pin ' + app.cfg.get('printer', 'light_pin'): {'value': 0}})
    app._status_changed()
    app.go('home')


def s_filament_rack_selected(app):
    app.go('filament', sel_slot=-2)


def _two_boxes(app):
    box1 = _qidi_box(3, [('PLA Basic', 'PLA', '#151515'), ('PLA Basic', 'PLA', '#F2F2F2'),
                         ('PETG Rapido', 'PETG', '#1714B0')])
    box2 = _qidi_box(4, [('PLA Matte', 'PLA', '#C62828'), ('PLA Matte', 'PLA', '#2E7D32'),
                         ('PLA Silk', 'PLA', '#D4AF37'), ('ASA', 'ASA', '#9E9E9E')])
    off = _qidi_box(0, [], online=0)
    _qidi_status(app, [box1, box2, off, off], 'slot5')


def s_filament_two_boxes(app):
    _two_boxes(app)
    app.go('filament', box_unit=1)


def s_home_two_boxes(app):
    _two_boxes(app)
    app.go('home')


SCENARIOS = [
    ('01_start_leerlauf', s_home_idle),
    ('02_start_druck_farbwechsel', s_home_print),
    ('03_filament_box', s_filament),
    ('04_slot_bearbeiten', s_slot_edit),
    ('05_bewegen', s_move),
    ('06_fehler_dialog', s_error),
    ('07_system_netzwerk', s_system_network),
    ('08_trocknung_auswahl', s_drying_select),
    ('09_trocknung_laeuft', s_drying_running),
    ('10_dateien', s_files),
    ('11_start_druck_ohne_wechsel', s_home_print_plain),
    ('12_filament_laedt', s_filament_loading),
    ('13_bestaetigung', s_confirm),
    ('14_temperatur', s_temp_dialog),
    ('15_anpassen', s_tune),
    ('16_klipper_fehler', s_klipper_error),
    ('17_system_box', s_system_box),
    ('18_system_info', s_system_info),
    ('19_start_pausiert', s_home_paused),
    ('20_filament_entladen', s_filament_unload),
    ('21_fehler_befehl', s_error_command),
    ('22_system_sprache', s_system_language),
    ('23_filament_ohne_box', s_filament_no_box),
    ('24_start_ohne_box', s_home_no_box),
    ('25_druck_ohne_box', s_print_no_box),
    ('26_filament_rack_gewaehlt', s_filament_rack_selected),
    ('27_filament_zwei_boxen', s_filament_two_boxes),
    ('28_start_zwei_boxen', s_home_two_boxes),
    ('29_start_cloud_licht_aus', s_home_cloud_dark),
    ('30_system_update_verfuegbar', s_system_update_available),
    ('31_system_update_bestaetigen', s_system_update_confirm),
    ('32_system_update_fehlgeschlagen', s_system_update_failed),
    ('33_system_update_testversion', s_system_update_test),
]
