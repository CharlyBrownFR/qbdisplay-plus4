# qbdisplay – Anwendung: Zustand, Seitenwechsel, Befehle, Hauptschleife
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Die App ist zugleich der Kontext (``ctx``) für alle Seiten: Seiten lesen
den Zustand über Eigenschaften (``ctx.slots``, ``ctx.climate`` ...) und lösen
Aktionen über Methoden aus (``ctx.load_slot(1)`` ...).

Threads: Display-Lesethread und Moonraker-Threads legen Ereignisse in eine
Queue; ausgewertet und gezeichnet wird nur im Hauptthread.
"""

import logging
import queue
import subprocess
import threading
import time

from . import __version__
from . import errors
from . import i18n
from . import model
from . import netinfo
from . import qidi
from . import updates
from . import thumbs
from .canvas import Canvas
from .i18n import _
from .filaments import FilamentList
from .ui.core import Frame, Renderer
from .ui import dialogs
from .ui.drying import DryingPage
from .ui.files import FilesPage
from .ui.filament import BoxPage, SlotEditPage
from .ui.home import HomePage
from .ui.move import MovePage
from .ui.system import SystemPage

log = logging.getLogger(__name__)

PAGES = {
    'home': HomePage, 'filament': BoxPage, 'slot_edit': SlotEditPage, 'drying': DryingPage,
    'move': MovePage, 'files': FilesPage, 'system': SystemPage,
}


def subscribe_objects(cfg):
    """Klipper-Objekte für printer.objects.subscribe (None = alle Felder)."""
    p = lambda k: cfg.get('printer', k)   # noqa: E731
    objs = {
        'webhooks': ['state', 'state_message'],
        'print_stats': None,
        'virtual_sdcard': ['progress', 'is_active', 'file_path'],
        'display_status': ['progress', 'message'],
        'pause_resume': ['is_paused'],
        'idle_timeout': ['state'],
        'toolhead': ['position', 'homed_axes'],
        'gcode_move': ['gcode_position', 'speed_factor', 'extrude_factor', 'homing_origin'],
        'extruder': ['temperature', 'target', 'can_extrude'],
        'heater_bed': ['temperature', 'target'],
        p('chamber'): ['temperature', 'target'],
        'output_pin ' + p('light_pin'): ['value'],
        model.fan_object(p('fan_part')): ['speed'],
        model.fan_object(p('fan_aux')): ['speed'],
        model.fan_object(p('fan_chamber')): ['speed'],
        cfg.get('box', 'heater'): ['temperature', 'target', 'power'],
        cfg.get('box', 'climate_sensor'): ['temperature', 'humidity'],
        'mmu': None,
        'save_variables': None,
    }
    if cfg.get('box', 'backend').strip().lower() == 'qidi':
        objs.pop('mmu')
        objs['box_extras'] = None
        objs['multi_color_controller'] = ['task', 'operation', 'box_warning_info',
                                          'auto_reload_detect', 'enable_box']
    return objs


class App(object):
    def __init__(self, cfg, sink, rpc=None, clock=time.time, display=None):
        self.cfg = cfg
        self.clock = clock
        self.display = display
        self.rpc = rpc
        self.events = queue.Queue()
        self.canvas = Canvas(sink)
        self.renderer = Renderer(self.canvas)
        self.st = model.Status(num_slots=cfg.getint('box', 'num_slots'))
        self.flist = FilamentList(cfg.path_of('box', 'filament_list'))
        self.num_slots = cfg.getint('box', 'num_slots')
        self.toolchange_tracker = model.ToolchangeTracker(cfg.getfloat('box', 'purge_seconds'))
        self.state_file = cfg.path_of('state', 'file')
        self.drying_tracker = model.DryingTracker(self.state_file)
        # Sprache: in der Oberfläche gewählt (Zustandsdatei) vor Vorgabe aus der Konfiguration
        i18n.set_language(model.read_state(self.state_file).get('language')
                          or cfg.get('display', 'language'))
        self.profiles = cfg.drying_profiles()
        self.connected = rpc is None
        self.server_info = {}
        self.versions = {}
        self.update_info = {}
        self.page_name = 'home'
        self.pages = {}
        self.dialog = None
        self.ui = {}
        self.pressed = None
        self._press_target = None
        self._toast = None
        self.frame = Frame()
        self.net = {}
        self.files = []
        self.last_print = None
        self.current_meta = None
        self._meta = {}
        self._meta_pending = set()
        self._thumbs = {}
        self._thumb_pending = set()
        self._dismissed_error = None
        self._cmd_error = None
        self._cache = {}
        self.dirty = True
        self._last_render = 0.0
        self._last_net = 0.0
        self._asleep = False
        self._minute = None
        self.thumbs_enabled = cfg.getbool('display', 'thumbnails')
        self.thumb_block = max(2, cfg.getint('display', 'thumb_block'))

    # ==================================================================
    # Kontext für Seiten
    # ==================================================================
    @property
    def now(self):
        return self.clock()

    def _cached(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    @property
    def pstate(self):
        return self._cached('pstate', lambda: model.printer_state(self.st, self.connected))

    @property
    def climate(self):
        return self._cached('climate', lambda: model.box_climate(
            self.st, self.cfg.get('box', 'heater'), self.cfg.get('box', 'climate_sensor')))

    @property
    def drying(self):
        return self._cached('drying', lambda: self.drying_tracker.view(self.climate, self.now))

    @property
    def slots(self):
        return self._cached('slots', lambda: model.slots(self.st, self.flist, self.num_slots))

    @property
    def rack(self):
        return self._cached('rack', lambda: model.rack_view(self.st))

    @property
    def loaded_gate(self):
        return self._cached('lg', lambda: model.loaded_slot(self.st))

    @property
    def toolchange(self):
        return self._cached('tc', lambda: self.toolchange_tracker.view(self.st, self.now))

    @property
    def toast(self):
        if self._toast and self._toast[2] < self.now:
            self._toast = None
        return self._toast[:2] if self._toast else None

    def heater_object(self, key):
        return self.cfg.get('printer', 'chamber') if key == 'chamber' else key

    def thumb(self, filename, size):
        if not self.thumbs_enabled or not filename:
            return None
        n = max(4, size // self.thumb_block)
        key = (filename, n)
        if key in self._thumbs:
            return self._thumbs[key]
        meta = self._meta.get(filename)
        if meta is None:
            self.request_meta(filename)
            return None
        if key not in self._thumb_pending:
            self._thumb_pending.add(key)
            t = threading.Thread(target=self._load_thumb, args=(key, meta), name='thumb')
            t.daemon = True
            t.start()
        return None

    def _load_thumb(self, key, meta):
        try:
            m = thumbs.load_mosaic(self.cfg.get('printer', 'gcode_dir'), key[0], meta, key[1])
        except Exception as e:   # noqa: defektes/fehlendes Bild -> Platzhalter
            log.info('Vorschaubild %s: %s', key[0], e)
            m = None
        self.events.put(('thumb', (key, m)))

    def file_meta(self, path):
        meta = self._meta.get(path)
        if meta is None:
            self.request_meta(path)
            return {}
        return meta

    def request_meta(self, path):
        if path in self._meta_pending or self.rpc is None:
            return
        self._meta_pending.add(path)

        def done(res, err, path=path):
            self._meta_pending.discard(path)
            self._meta[path] = res or {}
            if self.last_print and self.last_print.get('filename') == path:
                self._update_last_print_meta()
            self.mark_dirty()
        self.rpc.call('server.files.metadata', {'filename': path}, done)

    def drying_temp_for(self, ftype):
        t = model.base_type(ftype)
        for name, temp, hours, types in self.profiles:
            if t in [model.base_type(x) for x in types]:
                return temp
        return None

    # ==================================================================
    # Navigation, Dialoge, Rückmeldungen
    # ==================================================================
    def page(self):
        if self.page_name not in self.pages:
            self.pages[self.page_name] = PAGES[self.page_name](self)
        return self.pages[self.page_name]

    def go(self, name, **ui):
        if name == 'filament' and self.page_name == 'filament':
            self.ui['sel_slot'] = None
        if name == 'drying':
            self.ui['dry_edit'] = False
            self.ui.pop('dry', None)
        if name == 'files':
            self.refresh_files()
        self.ui.update(ui)
        self.page_name = name
        self.page().on_show()
        self.mark_dirty()

    def set_ui(self, **kw):
        self.ui.update(kw)
        self.mark_dirty()

    def open_dialog(self, dlg):
        self.dialog = dlg
        self.mark_dirty()

    def close_dialog(self):
        if isinstance(self.dialog, dialogs.ErrorDialog):
            self._dismissed_error = self.dialog.err.get('raw')
        self.dialog = None
        self.mark_dirty()

    def confirm(self, title, text, ok_label, on_ok, danger=True, ok_icon=None):
        self.open_dialog(dialogs.ConfirmDialog(self, title, text, ok_label, on_ok, danger, ok_icon))

    def info(self, title, text):
        self.open_dialog(dialogs.InfoDialog(self, title, text))

    def notify(self, text, kind='info', seconds=4.0):
        self._toast = (text, kind, self.now + seconds)
        self.mark_dirty()

    def clear_toast(self):
        self._toast = None
        self.mark_dirty()

    def mark_dirty(self):
        self.dirty = True

    request_render = mark_dirty

    def redraw(self):
        self.renderer.invalidate()
        self.mark_dirty()

    def set_language(self, lang, persist=True):
        """Sprache umschalten (System › Sprache): sofort alles neu zeichnen und in der
        Zustandsdatei merken (die Konfiguration ist nur die Vorgabe)."""
        code = i18n.set_language(lang)
        log.info('Sprache: %s', code)
        if persist:
            model.write_state(self.state_file, 'language', code)
        self._toast = None
        self.redraw()
        return code

    # ==================================================================
    # Befehle an Klipper
    # ==================================================================
    def gcode(self, script, label=None, on_done=None, retry=None, context=None):
        """G-Code senden. Fehler -> Fehlerdialog (Box-Befehle) bzw. Hinweis."""
        log.info('G-Code: %s', script.replace('\n', ' | '))
        if self.rpc is None:
            return
        if label:
            self.notify(label, 'info', 3.0)

        def done(res, err):
            if err:
                log.warning('G-Code-Fehler (%s): %s', script, err)
                if retry is not None or context is not None:
                    self.show_command_error(err, retry, context)
                else:
                    self.notify(err.splitlines()[0][:80], 'err', 6.0)
            elif on_done is not None:
                on_done()
            self.mark_dirty()
        self.rpc.gcode(script, done)

    def rpc_call(self, method, params=None, label=None):
        if self.rpc is None:
            return
        if label:
            self.notify(label, 'info', 3.0)

        def done(res, err):
            if err:
                self.notify(str(err)[:80], 'err', 6.0)
        self.rpc.call(method, params, done)

    # --- Box ---------------------------------------------------------------
    def box_cmd(self, key, **values):
        gate = values.pop('gate', 0)
        if gate == model.HH_GATE_BYPASS and self.cfg.get('box', 'backend') == 'qidi':
            gate = qidi.SLOT_EXTERNAL
        return self.cfg.command(key, gate=gate, **values)

    def load_slot(self, gate):
        self.ui['sel_slot'] = gate
        cmd = self.box_cmd('cmd_load', gate=gate)
        self.gcode(cmd, _('Slot %s wird geladen ...') % model.letter(gate),
                   retry=cmd, context={'gate': gate, 'what': _('Beim Laden von Slot %s')
                                       % model.letter(gate)})

    def load_rack(self):
        cmd = self.box_cmd('cmd_load_rack')
        self.gcode(cmd, _('Rack wird geladen ...'), retry=cmd,
                   context={'gate': model.HH_GATE_BYPASS, 'what': _('Beim Laden vom Rack')})

    def unload(self):
        g = self.loaded_gate
        cmd = self.box_cmd('cmd_unload', gate=g if g is not None else 0)
        self.gcode(cmd, _('Filament wird entladen ...'), retry=cmd,
                   context={'gate': g, 'what': _('Beim Entladen von Slot %s') % model.letter(g)
                            if g is not None and g >= 0 else _('Beim Entladen')})

    def confirm_eject(self, gate):
        cmd = self.box_cmd('cmd_eject', gate=gate)
        self.confirm(_('Slot %s auswerfen?') % model.letter(gate),
                     _('Das Filament wird ganz aus der Box geschoben (vorher ggf. aus der Düse '
                       'entladen). Danach kann die Spule entnommen werden.'), _('Auswerfen'),
                     lambda: self.gcode(cmd, _('Slot %s wird ausgeworfen ...') % model.letter(gate),
                                        retry=cmd, context={
                                            'gate': gate, 'what': _('Beim Auswerfen von Slot %s')
                                            % model.letter(gate)}),
                     danger=False, ok_icon='eject')

    def open_slot_edit(self, gate):
        self.ui['edit'] = self._edit_from_status(gate)
        self.go('slot_edit')

    def _edit_from_status(self, gate):
        v = self.st.variables
        fl = self.flist

        def var(name):
            try:
                val = int(v.get('%s%d' % (name, gate)))
                return val if val > 0 or name == 'vendor_slot' else None
            except (TypeError, ValueError):
                return None
        fil, col, ven = var('filament_slot'), var('color_slot'), var('vendor_slot')
        s = self.slots[gate] if gate < len(self.slots) else None
        if fil is None and s is not None:
            fil = fl.find(s.name, s.material)
        if col is None and s is not None and s.color:
            col = fl.find_color(s.color)
        if ven is None and s is not None:
            ven = fl.find_vendor(s.vendor)
        if fil not in fl.filaments:
            fil = None
        if col not in fl.colors:
            col = None
        if ven not in fl.vendors:
            ven = fl.vendor_ids()[0] if fl.vendors else None
        return {'slot': gate, 'fil': fil, 'color': col, 'vendor': ven, 'fpage': 0, 'cpage': 0}

    def edit_set(self, **kw):
        e = dict(self.ui.get('edit') or {})
        e.update(kw)
        self.ui['edit'] = e
        self.mark_dirty()

    def save_slot(self, gate, fil, col, ven):
        if self.cfg.getbool('box', 'gate_map_direct'):
            self.gcode(self.gate_map_command(gate, fil, col, ven))
        else:
            lines = ['SAVE_VARIABLE VARIABLE=filament_slot%d VALUE=%d' % (gate, fil),
                     'SAVE_VARIABLE VARIABLE=color_slot%d VALUE=%d' % (gate, col)]
            if ven is not None:
                lines.append('SAVE_VARIABLE VARIABLE=vendor_slot%d VALUE=%d' % (gate, ven))
            self.gcode('\n'.join(lines))
        self.go('filament', sel_slot=gate)
        self.notify(_('Slot %s gespeichert') % model.letter(gate), 'ok')

    def gate_map_command(self, gate, fil, col, ven):
        """MMU_GATE_MAP aus den Indizes der Materialliste (Happy Hare v4)."""
        fl = self.flist
        parts = ['MMU_GATE_MAP GATE=%d' % gate]
        name = fl.name(fil)
        if name:
            parts.append('NAME="%s"' % name.replace('"', ''))
        mat = fl.ftype(fil)
        if mat:
            parts.append('MATERIAL=%s' % mat.replace(' ', '_'))
        color = fl.colors.get(col)
        if color:
            parts.append('COLOR=%s' % color.lstrip('#').lower())
        vendor = fl.vendors.get(ven) if ven is not None else None
        if vendor:
            parts.append('VENDOR="%s"' % vendor.replace('"', ''))
        temps = fl.temp_range(fil)
        if temps:
            parts.append('TEMP=%d' % int((temps[0] + temps[1]) / 2))
        return ' '.join(parts)

    def read_rfid(self, gate):
        def done():
            self.ui['edit'] = self._edit_from_status(gate)
            self.notify(_('RFID gelesen'), 'ok')
        self.gcode(self.box_cmd('cmd_rfid', gate=gate), _('RFID wird gelesen ...'), on_done=done)

    def toggle_endless_spool(self):
        mmu = self.st.mmu
        on = bool(mmu.get('endless_spool_enabled', mmu.get('endless_spool', 0)))
        self.gcode(self.box_cmd('cmd_endless', on=0 if on else 1))

    def confirm_check_gates(self):
        self.confirm(_('Slots prüfen?'), _('Die Box bewegt jedes Filament kurz an, um zu prüfen, '
                                           'ob es da ist. Dauer ca. 1 min.'), _('Prüfen'),
                     lambda: self.gcode(self.box_cmd('cmd_check'), _('Slots werden geprüft ...')),
                     danger=False)

    # --- Trocknung -----------------------------------------------------------
    def dry_selection(self):
        sel = self.ui.get('dry')
        if sel is None:
            mats = [s.material for s in self.slots if s.state != 'empty' and s.material]
            idx, _why = model.suggest_profile(self.profiles, mats)
            dv = self.drying
            if dv.active and self.drying_tracker.data:
                d = self.drying_tracker.data
                names = [p[0] for p in self.profiles]
                idx = names.index(d.get('profile')) if d.get('profile') in names else idx
                sel = {'profile': idx, 'temp': d['temp'],
                       'hours': max(1, int(round(self.drying_tracker.remaining_minutes(self.now)
                                                 / 60.0)))}
            else:
                p = self.profiles[idx] if self.profiles else ('PLA', 55, 12, [])
                sel = {'profile': idx, 'temp': p[1], 'hours': int(p[2])}
            self.ui['dry'] = sel
        return sel

    def dry_set_profile(self, idx):
        p = self.profiles[idx]
        maxt = self.cfg.getint('box', 'dry_max_temp')
        self.ui['dry'] = {'profile': idx, 'temp': min(p[1], maxt), 'hours': int(p[2])}
        self.mark_dirty()

    def dry_adjust(self, temp=0, hours=0):
        sel = dict(self.dry_selection())
        maxt = self.cfg.getint('box', 'dry_max_temp')
        sel['temp'] = max(35, min(maxt, sel['temp'] + temp))
        sel['hours'] = max(1, min(48, sel['hours'] + hours))
        self.ui['dry'] = sel
        self.mark_dirty()

    def dry_start(self):
        sel = self.dry_selection()
        maxt = self.cfg.getint('box', 'dry_max_temp')
        temp = min(sel['temp'], maxt)
        minutes = sel['hours'] * 60
        name = self.profiles[sel['profile']][0] if self.profiles else _('Manuell')
        hum = self.climate[2]
        if self.drying.active and self.drying_tracker.data:
            hum = self.drying_tracker.data.get('hum_start', hum)
        self.drying_tracker.start(name, temp, minutes, self.now, hum)
        self.gcode(self.box_cmd('cmd_dry_start', temp=int(temp), minutes=int(minutes),
                                hours=max(1, int(round(minutes / 60.0))),
                                end=int(self.now + minutes * 60)),
                   _('Trocknung %s gestartet') % name)
        self.ui['dry_edit'] = False
        self.mark_dirty()

    def dry_extend(self):
        d = self.drying_tracker.data
        if not d:
            self.notify(_('Restzeit unbekannt - bitte über »Ändern« neu starten'), 'err')
            return
        rest = self.drying_tracker.remaining_minutes(self.now) + 60
        self.drying_tracker.extend(60)
        self.gcode(self.box_cmd('cmd_dry_start', temp=int(d['temp']), minutes=int(rest),
                                hours=max(1, int(round(rest / 60.0))),
                                end=int(self.now + rest * 60)),
                   _('Trocknung + 1 h'))

    def dry_change(self):
        self.ui.pop('dry', None)
        self.ui['dry_edit'] = True
        self.mark_dirty()

    def confirm_dry_stop(self):
        def stop():
            self.drying_tracker.stop()
            self.gcode(self.box_cmd('cmd_dry_stop'), _('Trocknung beendet'))
        self.confirm(_('Trocknung abbrechen?'), _('Die Box-Heizung wird ausgeschaltet. '
                                                  'Die bisherige Trocknungszeit geht nicht '
                                                  'verloren, die Spulen kühlen ab.'),
                     _('Abbrechen'), stop, ok_icon='stop')

    # --- Druck -----------------------------------------------------------------
    def confirm_print(self, path):
        meta = self.file_meta(path)
        extra = ''
        if meta.get('estimated_time'):
            extra = ' ' + _('Dauer laut Slicer: %s.') % model.fmt_duration(meta['estimated_time'])
        self.confirm(_('Drucken?'), '%s%s %s' % (
            model.short_filename(path), extra, _('Bett und Düse heizen sofort auf.')), _('Drucken'),
            lambda: self.rpc_call('printer.print.start', {'filename': path},
                                  _('Druck wird gestartet ...')),
            danger=False, ok_icon='retry')

    def confirm_cancel(self):
        self.confirm(_('Druck abbrechen?'), _('Der laufende Druck wird beendet und kann nicht '
                                              'fortgesetzt werden.'), _('Druck abbrechen'),
                     lambda: self.gcode('CANCEL_PRINT', _('Druck wird abgebrochen ...')),
                     ok_icon='stop')

    def pause(self):
        self.gcode('PAUSE', _('Druck wird pausiert ...'))

    def resume(self):
        self.gcode('RESUME', _('Druck wird fortgesetzt ...'))

    def open_tune(self):
        self.open_dialog(dialogs.TuneDialog(self))

    def open_temp(self, key):
        obj = self.heater_object(key)
        self.open_dialog(dialogs.TempDialog(self, key, self.st.get(obj, 'target', 0)))

    def set_temperature(self, key, value):
        name = 'extruder' if key == 'extruder' else (
            'heater_bed' if key == 'heater_bed' else self.heater_object(key).split()[-1])
        self.gcode('SET_HEATER_TEMPERATURE HEATER=%s TARGET=%d' % (name, value))

    def toggle_light(self):
        pin = self.cfg.get('printer', 'light_pin')
        on = bool(self.st.get('output_pin ' + pin, 'value', 0))
        self.gcode('SET_PIN PIN=%s VALUE=%d' % (pin, 0 if on else 1))

    # --- Bewegen -----------------------------------------------------------------
    def jog(self, axis, dist):
        feed = 600 if axis == 'Z' else 6000
        self.gcode('G91\nG1 %s%.3f F%d\nG90' % (axis, dist, feed))

    def home(self, axes):
        self.gcode(('G28 ' + axes).strip(), _('Referenzfahrt ...'))

    def motors_off(self):
        self.gcode('M84', _('Motoren aus'))

    def extrude(self, dist):
        self.gcode('M83\nG1 E%.1f F300' % dist)

    def cycle_fan(self, name, speed):
        nxt = 0.5 if speed < 0.25 else (1.0 if speed < 0.75 else 0.0)
        self.gcode(model.fan_gcode(name, nxt))

    # --- System --------------------------------------------------------------
    def confirm_gcode(self, title, question, gcode):
        self.confirm(question, _('%s läuft danach selbstständig. Der Drucker darf dabei nicht '
                                 'berührt werden.') % title, _('Starten'),
                     lambda: self.gcode(gcode, title + ' ...'),
                     danger=False)

    def confirm_restart(self):
        self.confirm(_('Klipper neu starten?'), _('Die Druckersoftware startet neu (ca. 20 s).'),
                     _('Neu starten'), lambda: self.rpc_call('printer.restart', None,
                                                             _('Neustart ...')))

    def confirm_fw_restart(self):
        self.confirm(_('Firmware neu starten?'), _('Klipper und alle Controller (inkl. Box) '
                                                   'werden neu gestartet.'), _('Neu starten'),
                     lambda: self.rpc_call('printer.firmware_restart', None, _('Neustart ...')))

    def confirm_shutdown(self):
        self.confirm(_('Drucker ausschalten?'), _('Das Linux-System fährt herunter. Danach kann '
                                                  'der Netzschalter betätigt werden.'),
                     _('Ausschalten'),
                     lambda: self.rpc_call('machine.shutdown', None, _('Fährt herunter ...')),
                     ok_icon='power')

    def toggle_lan_only(self):
        lan = bool(self.net.get('lan_only'))
        cmd = self.cfg.get('network', 'lan_only_off_cmd' if lan else 'lan_only_on_cmd').strip()
        if not cmd:
            self.info(_('Nur LAN'), _('qbdisplay ersetzt xindi und sendet selbst nichts an QIDI. '
                                      'Umschalten der übrigen Cloud-Teile (frpc, mqtt) ist nicht '
                                      'eingerichtet - siehe README.md.'))
            return
        try:
            subprocess.Popen(cmd, shell=True)
            self.notify(_('Wird umgeschaltet ...'), 'info')
        except OSError as e:
            self.notify(_('Fehler: %s') % e, 'err')
        self._last_net = 0

    def wifi_info(self):
        self.info(_('WLAN ändern'), _('Das WLAN wird über die Weboberfläche oder per SSH '
                                      '(nmtui) eingerichtet. Am Display folgt das später.'))

    # ==================================================================
    # Fehler
    # ==================================================================
    def show_command_error(self, err, retry, context):
        self._cmd_error = (err, retry, context or {})
        self._dismissed_error = None
        self.check_errors(force=True)

    def show_error(self):
        self._dismissed_error = None
        self.check_errors(force=True)

    def error_state(self):
        """-> dict für ErrorDialog oder None."""
        st = self.st
        ps = self.pstate
        mmu = st.mmu
        ext_target = st.get('extruder', 'target', 0) or 0
        names = (self.cfg.get('box', 'pre_gate_sensor'), self.cfg.get('box', 'gate_sensor'),
                 self.cfg.get('box', 'extruder_sensor'), self.cfg.get('box', 'toolhead_sensor'))
        if ps == 'error' and st.get('webhooks', 'state') in ('shutdown', 'error'):
            raw = st.get('webhooks', 'state_message', '') or _('Klipper gestoppt')
            info = errors.ErrorInfo('', _('Druckersoftware angehalten'),
                                    [raw.strip().splitlines()[0][:160],
                                     _('Ursache beheben (z. B. Sensor, Kabel).'),
                                     _('»Firmware neu« startet Klipper und alle Controller neu.')],
                                    'none')
            return {'info': info, 'raw': raw, 'kind': 'klipper',
                    'subtitle': _('Klipper meldet einen Fehler'),
                    'actions': [('fw', _('Firmware neu'), 'primary', 'retry',
                                 lambda: (self.close_dialog(), self.rpc_call(
                                     'printer.firmware_restart', None, _('Neustart ...'))), 1.2),
                                ('restart', _('Klipper neu'), 'secondary', None,
                                 lambda: (self.close_dialog(), self.rpc_call(
                                     'printer.restart', None, _('Neustart ...'))), 1),
                                ('close', _('Schließen'), 'secondary', 'x', self.close_dialog, 1)]}
        reason = mmu.get('reason_for_pause') or ''
        cmd = self._cmd_error
        if ps == 'paused_error' or reason or cmd:
            raw = reason or (cmd[0] if cmd else '') or _('Druck pausiert')
            info = errors.classify(raw)
            gate = (cmd[2].get('gate') if cmd else None)
            if gate is None:
                gate = mmu.get('gate')
            has_gate = gate is not None and gate >= 0
            if cmd:
                sub = cmd[2].get('what') or (_('Slot %s') % model.letter(gate) if has_gate else '')
            else:
                pos = mmu.get('filament_pos')
                loading = isinstance(pos, int) and 0 < pos < model.HH_POS_LOADED
                if has_gate:
                    sub = (_('Beim Laden von Slot %s') if loading else _('Box · Slot %s')) \
                        % model.letter(gate)
                else:
                    sub = _('Beim Laden') if loading else _('Box')
            if ps in ('paused', 'paused_error'):
                sub += ' · ' + _('Druck pausiert')
                if ext_target:
                    sub += ', ' + _('Düse hält %d °C') % ext_target
            color = None
            if gate is not None and 0 <= gate < len(self.slots):
                color = self.slots[gate].color
            printing = ps in ('paused', 'paused_error')
            retry_cmd = cmd[1] if cmd else None

            unlock = self.box_cmd('cmd_retry')
            unload_cmd = self.box_cmd('cmd_unload', gate=gate if gate is not None else 0)

            def retry():
                self._cmd_error = None
                self.close_dialog()
                script = unlock
                if retry_cmd and not printing:
                    script = retry_cmd
                elif printing:
                    script = unlock + '\nRESUME'
                self.gcode(script, _('Neuer Versuch ...'))

            def alt():
                self._cmd_error = None
                self.close_dialog()
                self.gcode((unlock + '\n' + unload_cmd) if printing else unload_cmd,
                           _('Wird entladen ...'))

            def close():
                self._cmd_error = None
                self.close_dialog()
            letter = model.letter(gate) if gate is not None and gate >= 0 else ''
            actions = [('retry', _('Erneut versuchen'), 'primary', 'retry', retry, 1.15),
                       ('alt', _('%s entladen') % letter if letter else _('Entladen'),
                        'secondary', 'up', alt, 0.95)]
            if printing:
                actions.append(('cancel', _('Druck abbrechen'), 'danger', 'stop',
                                lambda: (self.close_dialog(), self.confirm_cancel()), 1.2))
            else:
                actions.append(('close', _('Schließen'), 'secondary', 'x', close, 1))
            sensors = model.normalize_sensors(mmu.get('sensors'), mmu.get('gate'), names[0])
            return {'info': info, 'raw': raw, 'kind': 'mmu', 'subtitle': sub.strip(),
                    'gate': gate, 'color': color, 'sensors': sensors,
                    'sensor_names': names, 'actions': actions}
        if ps == 'error':
            raw = st.get('print_stats', 'message', '') or _('Druckfehler')
            info = errors.classify(raw)
            return {'info': info, 'raw': raw, 'kind': 'print', 'subtitle': _('Druck abgebrochen'),
                    'actions': [('close', _('Schließen'), 'primary', None, self.close_dialog, 1)]}
        return None

    def check_errors(self, force=False):
        err = self.error_state()
        cur = self.dialog
        if err is None:
            if isinstance(cur, dialogs.ErrorDialog):
                self.dialog = None
                self.mark_dirty()
            self._dismissed_error = None
            return
        if err['raw'] == self._dismissed_error and not force:
            return
        if isinstance(cur, dialogs.ErrorDialog) and cur.err.get('raw') == err['raw']:
            cur.err = err        # Sensorstand aktualisieren
            self.mark_dirty()
            return
        self.open_dialog(dialogs.ErrorDialog(self, err))

    # ==================================================================
    # Daten von Moonraker
    # ==================================================================
    def refresh_files(self):
        if self.rpc is None:
            return

        def done(res, err):
            if err:
                return
            files = [f for f in (res or []) if str(f.get('path', '')).lower().endswith('.gcode')]
            files.sort(key=lambda f: f.get('modified', 0), reverse=True)
            self.files = files
            self.mark_dirty()
        self.rpc.call('server.files.list', {'root': 'gcodes'}, done)

    def refresh_history(self):
        if self.rpc is None:
            return

        def done(res, err):
            jobs = (res or {}).get('jobs') or []
            if not jobs:
                return
            job = jobs[0]
            self.last_print = {'filename': job.get('filename'), 'status': job.get('status'),
                               'metadata': job.get('metadata') or {}, 'tools': []}
            self.request_meta(job.get('filename'))
            self._update_last_print_meta()
            self.mark_dirty()
        self.rpc.call('server.history.list', {'limit': 1, 'order': 'desc'}, done)

    def _update_last_print_meta(self):
        lp = self.last_print
        meta = self._meta.get(lp.get('filename'))
        if meta:
            merged = dict(lp.get('metadata') or {})
            merged.update(meta)
            lp['metadata'] = merged
        n = len((lp.get('metadata') or {}).get('filament_colors') or [])
        tools = []
        for t in range(n):
            g = model.gate_for_tool(self.st, t)
            tools.append(model.letter(g) if g is not None else 'T%d' % t)
        lp['tools'] = tools

    def refresh_versions(self):
        if self.rpc is None:
            return

        def pinfo(res, err):
            if res:
                self.versions['klipper'] = res.get('software_version', '')
                self.mark_dirty()
        self.rpc.call('printer.info', None, pinfo)

    # --- Updates ----------------------------------------------------------------
    def check_updates(self):
        """Versionen prüfen (im Hintergrund, nur lesende Abfragen)."""
        if self.update_info.get('state') == 'checking':
            return
        self.update_info = {'state': 'checking'}
        self.mark_dirty()
        repo = self.cfg.get('update', 'repo').strip()

        def run():
            try:
                res = updates.check(repo, __version__)
                res['state'] = 'done'
            except Exception as e:   # noqa: nur Anzeige
                log.exception('Update-Prüfung')
                res = {'state': 'error', 'error': str(e)}
            self.events.put(('updates', res))
        t = threading.Thread(target=run, name='updates')
        t.daemon = True
        t.start()

    def confirm_switch_qidi(self):
        def go_qidi():
            ok, out = updates.switch_to_qidi()
            if ok:
                self.notify(_('Wechsel zur QIDI-Oberfläche läuft (ca. 7 min)'), 'ok', 10.0)
            else:
                log.warning('Wechsel zu QIDI: %s', out)
                self.notify(_('Wechsel nicht möglich - install.sh erneut ausführen'), 'err', 8.0)
        self.confirm(_('Zur QIDI-Oberfläche wechseln?'),
                     _('qbdisplay wird beendet und die QIDI-Oberfläche aufgespielt (ca. 7 min, '
                       'Display solange dunkel). Danach sind QIDI-Updates und die QIDI-App '
                       'wieder verfügbar. qbdisplay später per ./install.sh zurückholen.'),
                     _('Wechseln'), go_qidi, danger=False, ok_icon='retry')

    def refresh_net(self):
        comps = self.server_info.get('components') or []
        try:
            self.net = netinfo.gather(comps)
        except Exception:   # noqa: nur Anzeige
            log.exception('Netzwerkstatus')
        self._last_net = self.now
        self.mark_dirty()

    # ==================================================================
    # Ereignisse
    # ==================================================================
    def on_rpc_event(self, kind, data):
        """Wird aus fremden Threads aufgerufen."""
        self.events.put((kind, data))

    def on_display_event(self, ev):
        self.events.put(('display', ev))

    def handle(self, kind, data):
        if kind == 'status':
            self.st.update(data)
            self._status_changed()
        elif kind == 'status_full':
            self.st = model.Status(data)
            self.connected = True
            self._status_changed()
            self.refresh_history()
            self.refresh_versions()
            fn = self.st.get('print_stats', 'filename')
            if fn:
                self.request_meta(fn)
        elif kind == 'callback':
            cb, result, error = data
            try:
                cb(result, error)
            except Exception:
                log.exception('Rückruf fehlgeschlagen')
        elif kind == 'connected':
            self.connected = True
            self.mark_dirty()
        elif kind == 'disconnected':
            self.connected = False
            self.mark_dirty()
        elif kind == 'server_info':
            self.server_info = data or {}
            self.versions['moonraker'] = self.server_info.get('moonraker_version', '')
            state = self.server_info.get('klippy_state')
            if state and state != 'ready':
                self.st.update({'webhooks': {'state': state}})
            self.mark_dirty()
        elif kind == 'updates':
            self.update_info = data or {}
            self.mark_dirty()
        elif kind == 'klippy_state':
            self.st.update({'webhooks': {'state': data or 'startup'}})
            self._status_changed()
        elif kind == 'gcode_response':
            text = str(data or '')
            if text.startswith('!!') and 'QDE_' in text:
                self._cmd_error = (text[2:].strip(), None, {})
                self.check_errors(force=True)
        elif kind == 'files_changed':
            if self.page_name == 'files':
                self.refresh_files()
        elif kind == 'history_changed':
            self.refresh_history()
        elif kind == 'thumb':
            key, m = data
            self._thumbs[key] = m
            self._thumb_pending.discard(key)
            self.mark_dirty()
        elif kind == 'display':
            self.handle_display(data)

    def _status_changed(self):
        self._cache.clear()
        now = self.now
        self.toolchange_tracker.update(self.st, now)
        self.drying_tracker.update(self.climate[1], now)
        fn = self.st.get('print_stats', 'filename')
        if fn and (self.current_meta is None or self.current_meta.get('_fn') != fn):
            meta = self._meta.get(fn)
            if meta is not None:
                self.current_meta = dict(meta, _fn=fn)
            else:
                self.request_meta(fn)
        self.check_errors()
        self.mark_dirty()

    def handle_display(self, ev):
        from . import tjc
        if isinstance(ev, tjc.TouchEvent):
            if ev.asleep:
                return       # Berührung weckt nur auf
            self.handle_touch(ev.x, ev.y, ev.pressed)
        elif isinstance(ev, tjc.SystemEvent):
            if ev.name in ('startup', 'ready'):
                log.info('Display (neu) gestartet')
                if self.display is not None:
                    self.display.discard_pending()
                    self.display.init_display(self.cfg.getint('display', 'sleep_after'))
                self._asleep = False
                self.redraw()
            elif ev.name == 'sleep':
                self._asleep = True
            elif ev.name == 'wake':
                self._asleep = False
                self.redraw()
            elif ev.name == 'buffer_overflow':
                log.warning('Display-Puffer übergelaufen - zeichne neu')
                self.redraw()

    def handle_touch(self, x, y, pressed):
        if pressed:
            t = self.frame.hit(x, y)
            self._press_target = t
            self.pressed = t.tid if t else None
            if t is not None:
                self.mark_dirty()
            return
        t = self._press_target
        self._press_target = None
        self.pressed = None
        self.mark_dirty()
        if t is None:
            return
        # Loslassen: auf demselben Ziel (oder Koordinate unbekannt = 0,0)
        hit = self.frame.hit(x, y) if (x or y) else t
        if hit is not None and hit.tid == t.tid:
            try:
                t.action()
            except Exception:
                log.exception('Aktion %s fehlgeschlagen', t.tid)
                self.notify(_('Interner Fehler bei %s') % t.tid, 'err')

    def tap(self, x, y):
        """Für Tests/Simulator: Drücken + Loslassen."""
        self.handle_touch(x, y, True)
        self.handle_touch(x, y, False)

    # ==================================================================
    # Zeichnen
    # ==================================================================
    def render(self):
        self._cache.clear()
        page = self.page()
        frame = Frame()
        page.build(frame)
        if self.dialog is not None:
            dframe = Frame()
            self.dialog.build(dframe)
            self.renderer.render(dframe, ('dialog', self.dialog.layer, self.page_name),
                                 dim_frame=frame)
            self.frame = dframe
        else:
            self.renderer.render(frame, ('page', self.page_name))
            self.frame = frame
        self.dirty = False
        self._last_render = time.time()

    def tick(self):
        """Periodisch: Uhr, Restzeiten, Netzwerk."""
        now = self.now
        if now - self._last_net > 15:
            self.refresh_net()
        minute = int(now // 60)
        if self.toolchange.active or self._minute != minute:
            self._cache.clear()
            self._minute = minute
            self.mark_dirty()
        if self._toast and self._toast[2] < now:
            self._toast = None
            self.mark_dirty()

    def run_forever(self):
        """Hauptschleife (Display und Moonraker müssen gestartet sein)."""
        last_tick = 0.0
        while True:
            try:
                kind, data = self.events.get(timeout=0.25)
                self.handle(kind, data)
                for _i in range(200):
                    try:
                        kind, data = self.events.get_nowait()
                    except queue.Empty:
                        break
                    self.handle(kind, data)
            except queue.Empty:
                pass
            now = time.time()
            if now - last_tick >= 1.0:
                self.tick()
                last_tick = now
            if self.dirty and not self._asleep and now - self._last_render >= 0.08:
                if self.display is not None and self.display.pending() > 400:
                    continue    # Leitung voll: erst abarbeiten lassen
                self.render()
