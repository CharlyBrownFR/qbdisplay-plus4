# qbdisplay – Zustandsmodell: Moonraker-Status -> Anzeige-Daten
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Reine Logik ohne Display-/Netzwerkzugriff (gut testbar).

Quellen: Klipper-Objekte über Moonraker, v. a. ``mmu`` (Happy Hare v4),
``save_variables`` (QIDI-Variablen, von qidi_box_compat gespiegelt),
``heater_generic heater_box1`` und ``aht20_f heater_box1`` (Box-Klima).
"""

import collections
import json
import logging
import os
import re
import time

from . import colors
from . import qidi
from .i18n import _

log = logging.getLogger(__name__)

LETTERS = 'ABCDEFGHIJKLMNOP'

# Happy Hare (extras/mmu/mmu_constants.py)
HH_POS_UNLOADED = 0
HH_POS_LOADED = 10
HH_GATE_BYPASS = -2
HH_GATE_UNKNOWN = -1

ACTIONS_CUT = ('Cutting Tip', 'Forming Tip', 'Cutting Filament')
ACTIONS_UNLOAD = ('Unloading', 'Exiting Ext')
ACTIONS_LOAD = ('Loading', 'Loading Ext', 'Selecting', 'Homing', 'Checking', 'Heating', 'Preload')
ACTIONS_PURGE = ('Purging',)


def letter(gate):
    if gate == HH_GATE_BYPASS:
        return 'Rack'
    if gate is None or gate < 0:
        return '?'
    return LETTERS[gate] if gate < len(LETTERS) else str(gate)


def _get(seq, idx, default=None):
    try:
        v = seq[idx]
    except (TypeError, IndexError, KeyError):
        return default
    return default if v is None else v


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Status-Speicher
# ---------------------------------------------------------------------------
class Status(object):
    """Zusammengeführter Objektstatus wie von printer.objects.subscribe."""

    def __init__(self, data=None, num_slots=4):
        self.data = {}
        self.num_slots = num_slots
        self._mmu = None
        if data:
            self.update(data)

    def update(self, delta):
        self._mmu = None
        for obj, fields in (delta or {}).items():
            cur = self.data.setdefault(obj, {})
            if not isinstance(fields, dict):
                self.data[obj] = fields
                continue
            for k, v in fields.items():
                if isinstance(v, dict) and isinstance(cur.get(k), dict):
                    merged = dict(cur[k])
                    merged.update(v)
                    cur[k] = merged
                else:
                    cur[k] = v

    def obj(self, name):
        return self.data.get(name) or {}

    def get(self, name, field, default=None):
        v = self.obj(name).get(field, default)
        return default if v is None else v

    @property
    def mmu(self):
        """Happy Hare ``mmu``; auf der QIDI-Firmware aus deren Box-Objekten nachgebaut."""
        if self._mmu is None:
            self._mmu = self.obj('mmu') or qidi.synth_mmu(self, self.num_slots)
        return self._mmu

    @property
    def variables(self):
        return self.obj('save_variables').get('variables') or {}


# ---------------------------------------------------------------------------
# Druckerzustand
# ---------------------------------------------------------------------------
def printer_state(st, connected=True):
    """'offline' | 'startup' | 'error' | 'idle' | 'printing' | 'paused' | 'paused_error'."""
    if not connected:
        return 'offline'
    wh = st.get('webhooks', 'state', 'ready')
    if wh in ('shutdown', 'error'):
        return 'error'
    if wh == 'startup':
        return 'startup'
    ps = st.get('print_stats', 'state', 'standby')
    mmu = st.mmu
    if ps == 'paused' or st.get('pause_resume', 'is_paused', False):
        if mmu.get('reason_for_pause') or mmu.get('print_state') == 'pause_locked':
            return 'paused_error'
        return 'paused'
    if ps == 'printing':
        return 'printing'
    if ps == 'error':
        return 'error'
    return 'idle'


def progress(st):
    p = _num(st.get('display_status', 'progress', 0))
    if p <= 0:
        p = _num(st.get('virtual_sdcard', 'progress', 0))
    return max(0.0, min(1.0, p))


PrintView = collections.namedtuple(
    'PrintView', 'filename progress layer total_layers elapsed remaining eta')


def print_view(st, metadata=None, now=None):
    now = now or time.time()
    ps = st.obj('print_stats')
    info = ps.get('info') or {}
    p = progress(st)
    elapsed = _num(ps.get('print_duration'))
    est = _num((metadata or {}).get('estimated_time'))
    remaining = None
    if p > 0.05 and elapsed > 0:
        remaining = max(0.0, elapsed / p - elapsed)
    elif est > 0:
        remaining = max(0.0, est - elapsed)
    eta = now + remaining if remaining is not None else None
    total = info.get('total_layer') or (metadata or {}).get('layer_count')
    return PrintView(ps.get('filename') or '', p, info.get('current_layer'), total,
                     elapsed, remaining, eta)


# ---------------------------------------------------------------------------
# Slots (Happy Hare Gates)
# ---------------------------------------------------------------------------
SlotView = collections.namedtuple(
    'SlotView', 'index letter state material name color color_name vendor temps')
# state: 'loaded' | 'ready' | 'loading' | 'unloading' | 'empty' | 'unknown'


def slot_state(mmu, i):
    gate = mmu.get('gate')
    pos = mmu.get('filament_pos')
    action = mmu.get('action') or 'Idle'
    gs = _get(mmu.get('gate_status'), i, HH_GATE_UNKNOWN)
    if gate == i:
        if action in ACTIONS_UNLOAD:
            return 'unloading'
        if pos == HH_POS_LOADED:
            return 'loaded'
        if (pos is not None and pos > HH_POS_UNLOADED) or action in ACTIONS_LOAD:
            return 'loading'
    if gs is not None and gs > 0:
        return 'ready'
    if gs == 0:
        return 'empty'
    return 'unknown'


def slot_view(st, i, flist=None):
    mmu = st.mmu
    state = slot_state(mmu, i)
    name = _get(mmu.get('gate_filament_name'), i, '') or ''
    material = _get(mmu.get('gate_material'), i, '') or ''
    color = colors.parse_filament_color(_get(mmu.get('gate_color'), i))
    vendor = _get(mmu.get('gate_vendor'), i, '') or ''
    temps = None
    if flist is not None:
        idx = flist.find(name, material)
        if idx is not None:
            temps = flist.temp_range(idx)
            if not material:
                material = flist.ftype(idx)
    if temps is None:
        temps = _get(mmu.get('gate_temps'), i)
    # Anzeigename: HH-Filamentname, sonst Material
    display = name or material
    return SlotView(i, letter(i), state, material, display, color,
                    colors.color_name(color) if color else '', vendor, temps)


def slots(st, flist=None, num=4):
    return [slot_view(st, i, flist) for i in range(num)]


def rack_view(st):
    mmu = st.mmu
    loaded = mmu.get('gate') == HH_GATE_BYPASS and mmu.get('filament_pos') == HH_POS_LOADED
    return SlotView(HH_GATE_BYPASS, 'Rack', 'loaded' if loaded else 'empty',
                    '', _('Extern'), None, '', '', None)


def loaded_slot(st):
    """Gate, das in der Düse steckt (oder None)."""
    mmu = st.mmu
    if mmu.get('filament_pos') == HH_POS_LOADED and mmu.get('gate') is not None \
            and mmu.get('gate') != HH_GATE_UNKNOWN:
        return mmu.get('gate')
    return None


def temp_range_text(temps):
    if not temps:
        return ''
    return '%d–%d °C' % temps


def gate_for_tool(st, tool):
    ttg = st.mmu.get('ttg_map') or []
    g = _get(ttg, tool)
    return g if isinstance(g, int) else None


# ---------------------------------------------------------------------------
# Material-Typen, Feuchte, Trocknungsprofile
# ---------------------------------------------------------------------------
HUMIDITY_LIMIT = collections.OrderedDict([
    ('PA', 20), ('PC', 25), ('TPU', 35), ('PETG', 40), ('ABS', 40), ('ASA', 40), ('PLA', 50),
])


def base_type(material):
    m = (material or '').upper()
    for key in ('PETG', 'PCTG', 'PET', 'ABS', 'ASA', 'TPU', 'TPE', 'PLA', 'PA', 'PC'):
        if m.startswith(key):
            return {'PCTG': 'PETG', 'PET': 'PETG', 'TPE': 'TPU'}.get(key, key)
    return m


def humidity_rating(humidity, materials):
    """-> (stufe, text) mit stufe 'ok' | 'warn' | 'err' | 'none'."""
    if humidity is None:
        return 'none', _('Feuchte unbekannt')
    types = [base_type(m) for m in materials if m]
    limits = [(HUMIDITY_LIMIT[t], t) for t in types if t in HUMIDITY_LIMIT]
    if not limits:
        limits = [(HUMIDITY_LIMIT['PLA'], 'PLA')]
    lim, t = min(limits)
    if humidity <= lim:
        return 'ok', _('für %s ok') % t
    if humidity <= lim + 15:
        return 'warn', _('für %s zu feucht') % t
    return 'err', _('für %s viel zu feucht') % t


def suggest_profile(profiles, materials):
    """Profil für die Belegung: niedrigste Temperatur, bei Gleichstand das
    feuchteempfindlichere Material. -> (index, grund-material) oder (0, None)."""
    cands = []
    for m in materials:
        t = base_type(m)
        for i, (name, temp, hours, types) in enumerate(profiles):
            if t in [base_type(x) for x in types]:
                cands.append((temp, HUMIDITY_LIMIT.get(t, 99), i, t))
                break
    if not cands:
        return 0, None
    temp, _, idx, t = min(cands)
    return idx, t


def drying_active(mmu):
    """Happy Hare v4: printer.mmu.drying_state = Liste je Gate ('active' | ...)."""
    states = mmu.get('drying_state') or []
    if isinstance(states, str):
        states = [states]
    return any(s == 'active' for s in states)


def box_climate(st, cfg_heater, cfg_sensor):
    """-> (temp, target, humidity, heating)"""
    h = st.obj(cfg_heater)
    s = st.obj(cfg_sensor)
    temp = s.get('temperature', h.get('temperature'))
    hum = s.get('humidity')
    target = _num(h.get('target'))
    return (None if temp is None else _num(temp), target,
            None if hum is None else _num(hum), target > 0 or drying_active(st.mmu))


def normalize_sensors(sensors, selected_gate, pre_tpl='mmu_entry_%d'):
    """printer.mmu.sensors hat zwei Formen (HH v4, mmu_sensor_manager.active_sensors_map):
    ohne gewaehltes Gate die Unit-Form mit Index (mmu_entry_0..3), mit gewaehltem Gate die
    Gate-Form ohne Index (mmu_entry). Liefert eine Kopie, in der der indizierte Schluessel
    des gewaehlten Gates aus der Kurzform ergaenzt ist."""
    out = dict(sensors or {})
    if selected_gate is None or selected_gate < 0 or '%d' not in pre_tpl:
        return out
    short = pre_tpl.replace('_%d', '').replace('%d', '')
    key = pre_tpl % selected_gate
    if key not in out and short in out:
        out[key] = out[short]
    return out


def fan_object(name):
    """Klipper-Objektname zu einem Lueftername: 'fan' = [fan] (Bauteilluefter, M106),
    sonst [fan_generic name]."""
    return 'fan' if name == 'fan' else 'fan_generic ' + name


def fan_gcode(name, speed):
    if name == 'fan':
        return 'M106 S%d' % int(round(speed * 255))
    return 'SET_FAN_SPEED FAN=%s SPEED=%.2f' % (name, speed)


# ---------------------------------------------------------------------------
# Farbwechsel-Fortschritt
# ---------------------------------------------------------------------------
PHASES = ('cut', 'unload', 'load', 'purge', 'resume')
PHASE_EST = {'cut': 15.0, 'unload': 45.0, 'load': 45.0, 'resume': 10.0}
PURGE_RATE_MM3_S = 3.8   # gemessen: ~240 mm 1,75er Filament in ~150 s

ToolchangeView = collections.namedtuple(
    'ToolchangeView', 'active number total from_gate to_gate phase purge_frac remaining')


class ToolchangeTracker(object):
    """Leitet die Schritte Schneiden -> Entladen -> Laden -> Spülen -> Weiter
    aus Happy-Hare-``action``, ``filament_pos`` und der QIDI-Variable
    ``is_tool_change`` (TOOL_CHANGE_START/END aus dem Slicer-G-Code) ab."""

    def __init__(self, purge_seconds=150.0):
        self.purge_default = purge_seconds
        self.reset()

    def reset(self):
        self.active = False
        self.phase = None
        self.phase_start = 0.0
        self.number = 0
        self.from_gate = None
        self.to_gate = None
        self._flag_seen = False

    def _set_phase(self, phase, now):
        if self.phase is None or PHASES.index(phase) > PHASES.index(self.phase):
            self.phase = phase
            self.phase_start = now

    def purge_seconds(self, st):
        vol = _num(st.mmu.get('toolchange_purge_volume'))
        if vol > 0:
            return max(20.0, vol / PURGE_RATE_MM3_S)
        return self.purge_default

    def update(self, st, now):
        ps = st.get('print_stats', 'state', 'standby')
        mmu = st.mmu
        if ps not in ('printing', 'paused'):
            self.reset()
            return
        flag = str(st.variables.get('is_tool_change', 0)) in ('1', 'True', 'true')
        action = mmu.get('action') or 'Idle'
        busy = action in ACTIONS_CUT + ACTIONS_UNLOAD + ACTIONS_LOAD + ACTIONS_PURGE
        if not self.active:
            if flag or busy:
                self.active = True
                self._flag_seen = flag
                self.phase = None
                self._set_phase('cut', now)
                self.number = int(_num(mmu.get('num_toolchanges'))) + 1
                self.from_gate = loaded_slot(st)
            else:
                return
        self._flag_seen = self._flag_seen or flag
        if action in ACTIONS_CUT:
            self._set_phase('cut', now)
        elif action in ACTIONS_UNLOAD:
            self._set_phase('unload', now)
        elif action in ACTIONS_LOAD:
            self._set_phase('load', now)
        elif action in ACTIONS_PURGE:
            self._set_phase('purge', now)
        nt = mmu.get('next_tool')
        if isinstance(nt, int) and nt >= 0:
            g = gate_for_tool(st, nt)
            if g is not None:
                self.to_gate = g
        if action == 'Idle' and mmu.get('filament_pos') == HH_POS_LOADED:
            g = mmu.get('gate')
            if self.phase in ('load',) or (g is not None and g != self.from_gate):
                if self.to_gate is None:
                    self.to_gate = g
                if self._flag_seen:
                    self._set_phase('purge', now)
                else:
                    self.active = False     # reiner HH-Wechsel ohne Slicer-Spülen
                    return
        if self._flag_seen and not flag:
            self.active = False             # TOOL_CHANGE_END

    def view(self, st, now):
        if not self.active:
            return ToolchangeView(False, 0, 0, None, None, None, 0.0, None)
        total = int(_num((st.mmu.get('slicer_tool_map') or {}).get('total_toolchanges')))
        elapsed = now - self.phase_start
        purge = self.purge_seconds(st)
        est = dict(PHASE_EST)
        est['purge'] = purge
        idx = PHASES.index(self.phase)
        remaining = max(5.0, est[self.phase] - elapsed)
        for ph in PHASES[idx + 1:]:
            remaining += est[ph]
        purge_frac = 0.0
        if self.phase == 'purge':
            purge_frac = min(0.99, elapsed / purge)
        elif idx > PHASES.index('purge'):
            purge_frac = 1.0
        return ToolchangeView(True, self.number, total, self.from_gate, self.to_gate,
                              self.phase, purge_frac, remaining)


# ---------------------------------------------------------------------------
# Zustandsdatei ([state] file): {"drying": {...}, "language": "en", ...}
# ---------------------------------------------------------------------------
def read_state(path):
    """Inhalt der Zustandsdatei als dict (fehlt/unlesbar -> {})."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        log.warning('Zustandsdatei %s unlesbar', path)
        return {}
    return data if isinstance(data, dict) else {}


def write_state(path, key, value):
    """Einen Schlüssel der Zustandsdatei setzen, die übrigen bleiben erhalten."""
    if not path:
        return False
    data = read_state(path)
    data[key] = value
    try:
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError:
        log.exception('Zustandsdatei %s nicht schreibbar', path)
        return False
    return True


# ---------------------------------------------------------------------------
# Trocknung
# ---------------------------------------------------------------------------
DryingView = collections.namedtuple(
    'DryingView', 'active known profile target temp humidity hum_start start end '
                  'remaining frac')


class DryingTracker(object):
    """Merkt sich Start, Dauer und Profil der Box-Trocknung (die Firmware
    liefert keine Restzeit im Status). Wird in einer kleinen JSON-Datei
    gespeichert, damit ein Neustart der Display-Software nichts verliert."""

    def __init__(self, path=None):
        self.path = os.path.expanduser(path) if path else None
        self.data = None
        self._target_zero_since = None
        self.load()

    def load(self):
        self.data = read_state(self.path).get('drying')

    def save(self):
        write_state(self.path, 'drying', self.data)

    def start(self, profile, temp, minutes, now, humidity=None):
        self.data = {'start': now, 'minutes': int(minutes), 'temp': int(temp),
                     'profile': profile, 'hum_start': humidity}
        self._target_zero_since = None
        self.save()

    def extend(self, minutes):
        if self.data:
            self.data['minutes'] = int(self.data['minutes']) + int(minutes)
            self.save()

    def remaining_minutes(self, now):
        if not self.data:
            return 0
        end = self.data['start'] + self.data['minutes'] * 60
        return max(0, int((end - now) // 60))

    def stop(self):
        self.data = None
        self.save()

    def update(self, target, now):
        """Aufräumen, wenn die Heizung aus ist (fertig/abgebrochen)."""
        if not self.data:
            return
        end = self.data['start'] + self.data['minutes'] * 60
        if target > 0:
            self._target_zero_since = None
            return
        if self._target_zero_since is None:
            self._target_zero_since = now
        if now - self.data['start'] > 90 and (now - self._target_zero_since > 30 or now > end):
            self.stop()

    def view(self, climate, now):
        temp, target, hum, heating = climate
        if not heating:
            return DryingView(False, bool(self.data), None, 0, temp, hum, None, None,
                              None, None, 0.0)
        if not self.data:
            return DryingView(True, False, None, target, temp, hum, None, None, None,
                              None, 0.0)
        start = self.data['start']
        total = self.data['minutes'] * 60.0
        end = start + total
        remaining = max(0.0, end - now)
        frac = 1.0 - remaining / total if total > 0 else 0.0
        return DryingView(True, True, self.data.get('profile'), target, temp, hum,
                          self.data.get('hum_start'), start, end, remaining, frac)


# ---------------------------------------------------------------------------
# Formatierung
# ---------------------------------------------------------------------------
def fmt_duration(seconds, style='hm'):
    """'1 h 38 min' (hm) | '7:42 h' (clock) | '1:35 min' (ms)."""
    if seconds is None:
        return '–'
    s = int(round(max(0, seconds)))
    if style == 'clock':
        return '%d:%02d h' % (s // 3600, (s % 3600) // 60)
    if style == 'ms':
        return '%d:%02d min' % (s // 60, s % 60)
    h, m = s // 3600, (s % 3600) // 60
    if h:
        return '%d h %02d min' % (h, m)
    return '%d min' % max(1, m) if s >= 60 else '%d s' % s


def fmt_clock(ts, now=None):
    """Uhrzeit, mit 'morgen' falls am Folgetag (Texte in der aktiven Sprache)."""
    if ts is None:
        return '–'
    now = now or time.time()
    lt, ln = time.localtime(ts), time.localtime(now)
    hhmm = '%02d:%02d' % (lt.tm_hour, lt.tm_min)
    days = (time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
            - time.mktime((ln.tm_year, ln.tm_mon, ln.tm_mday, 0, 0, 0, 0, 0, -1)))
    days = int(round(days / 86400.0))
    if days == 1:
        return _('morgen %s') % hhmm
    if days > 1:
        return _('%02d.%02d. %s') % (lt.tm_mday, lt.tm_mon, hhmm)
    return hhmm


def fmt_temp(v):
    return '–' if v is None else '%d' % int(round(v))


def short_filename(name):
    base = os.path.basename(name or '')
    return re.sub(r'\.gcode$', '.gcode', base)
