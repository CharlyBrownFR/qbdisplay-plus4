# qbdisplay – QIDI-Stock-Firmware (2.1.1): Box-Zustand -> Happy-Hare-artiges "mmu"
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Die Oberfläche liest den Box-Zustand aus einem Objekt in der Form von Happy Hares
``printer.mmu``. Auf der QIDI-Firmware gibt es das nicht; diese Datei baut es aus den
QIDI-Objekten nach (Stand 2.1.1, am Gerät gelesen 2026-11-20):

- ``box_extras``: ``loaded_slot`` ("slotN", "slot16" = externe Spule, "slot-1" = keins),
  ``boxes[b]`` mit ``box_inserted_i`` (Spule im Slot), ``filament_inserted_i``,
  ``filament_info[i]`` (``filament_str``, ``filament_type``, ``color_rgb_str``,
  ``vendor_str``, ``min_temp``/``max_temp``), ``dry_state``, ``end_time``,
  ``aht20_temp``/``aht20_humidity``
- ``multi_color_controller``: ``task`` (laufender Ablauf, sonst leer),
  ``operation`` (``operate_state``, ``active_slot``), ``box_warning_info``,
  ``auto_reload_detect``
- ``save_variables``: ``value_tN`` = "slotM" (Werkzeug -> Slot)

Ohne Box (USB abgezogen, am Gerät getestet 2026-11-21): QIDI kommentiert die Box in
``box.cfg`` aus und startet Klipper neu; dann ist ``boxes`` leer, ``loaded_slot`` leer und
``multi_color_controller.box_count`` 0. Die externe Spule steht in
``multi_color_controller.extra.filament_info`` (auch mit Box).

Slot-Nummern: Box b hat die Slots 4*b .. 4*b+3; ``slot16`` ist die externe Spule (Rack).
"""

import re

SLOT_EXTERNAL = 16
GATE_BYPASS = -2     # wie model.HH_GATE_BYPASS
GATE_UNKNOWN = -1
POS_UNLOADED = 0
POS_LOADED = 10


def slot_number(value):
    """'slot3' -> 3, 'slot-1' / '' / None -> None."""
    m = re.match(r'^slot(-?\d+)$', str(value or '').strip())
    if not m:
        return None
    n = int(m.group(1))
    return n if n >= 0 else None


def _boxes(st):
    boxes = st.obj('box_extras').get('boxes') or []
    return [b for b in boxes if isinstance(b, dict)]


def _flag(v):
    return str(v) in ('1', 'True', 'true')


def units_online(st):
    """Indizes der angeschlossenen Boxen (leer = ohne Box)."""
    boxes = _boxes(st)
    online = [i for i, b in enumerate(boxes) if _flag(b.get('is_online', 1))]
    count = st.obj('multi_color_controller').get('box_count')
    if count is not None and not boxes:
        return list(range(int(count))) if str(count).isdigit() else []
    return online


def external_info(st):
    """Externe Spule (Rack) -> dict wie ein Slot (name, material, color, vendor, temps)."""
    extra = st.obj('multi_color_controller').get('extra') or {}
    info = extra.get('filament_info') or {}
    if not isinstance(info, dict):
        return {}
    cols = info.get('color_rgb_str') or []
    lo, hi = info.get('min_temp'), info.get('max_temp')
    return {
        'name': info.get('filament_str') or '',
        'material': info.get('filament_type') or '',
        'color': (cols[0] if isinstance(cols, list) and cols else cols or '') or '',
        'vendor': info.get('vendor_str') or '',
        'temps': (int(lo), int(hi)) if lo and hi else None,
    }


def _action(mcc):
    """Laufender Box-Ablauf als Happy-Hare-Aktion. Das Format von ``task`` ist noch nicht
    im Betrieb mitgeschnitten [prüfen]; erkannt wird alles, was nach Laden/Entladen/
    Auswerfen/Schneiden aussieht, sonst bei aktivem Ablauf 'Loading'."""
    task = mcc.get('task') or {}
    op = mcc.get('operation') or {}
    if not task and not op.get('operate_state'):
        return 'Idle'
    text = ' '.join(str(v) for v in (list(task.keys()) + list(task.values())
                                     if isinstance(task, dict) else [task])).lower()
    if 'unload' in text or 'eject' in text:
        return 'Unloading'
    if 'cut' in text:
        return 'Cutting Filament'
    if 'flush' in text or 'purge' in text or 'wipe' in text:
        return 'Purging'
    return 'Loading'


def synth_mmu(st, num_slots=4):
    """Happy-Hare-ähnliches ``mmu``-Objekt aus dem QIDI-Status (leeres dict ohne Box)."""
    be = st.obj('box_extras')
    mcc = st.obj('multi_color_controller')
    if not be and not mcc:
        return {}
    # ohne Box entfernt QIDI box_extras ganz aus der Config; dann bleibt nur mcc
    boxes = _boxes(st)
    num_slots = max(num_slots, 4 * len(boxes))
    gate_status, material, name, color, vendor, temps = [], [], [], [], [], []
    for i in range(num_slots):
        b = boxes[i // 4] if i // 4 < len(boxes) else {}
        k = i % 4
        online = _flag(b.get('is_online', 1))
        present = online and _flag(b.get('box_inserted_%d' % k))
        gate_status.append(1 if present else 0)
        infos = b.get('filament_info') or []
        info = infos[k] if k < len(infos) and isinstance(infos[k], dict) else {}
        material.append(info.get('filament_type') or '')
        name.append(info.get('filament_str') or '')
        cols = info.get('color_rgb_str') or []
        color.append((cols[0] if isinstance(cols, list) and cols else cols or '') or '')
        vendor.append(info.get('vendor_str') or '')
        lo, hi = info.get('min_temp'), info.get('max_temp')
        temps.append((int(lo), int(hi)) if lo and hi else None)
    units = units_online(st)
    loaded = slot_number(be.get('loaded_slot'))
    if loaded is None and not units and be.get('loaded_slot', '') == '':
        # ohne Box bleibt loaded_slot leer; zuletzt aktiv ist dann die externe Spule
        loaded = slot_number((mcc.get('operation') or {}).get('active_slot'))
        if loaded is not None and loaded != SLOT_EXTERNAL:
            loaded = None
    if loaded is None:
        gate, pos = GATE_UNKNOWN, POS_UNLOADED
    elif loaded == SLOT_EXTERNAL:
        gate, pos = GATE_BYPASS, POS_LOADED
    else:
        gate, pos = loaded, POS_LOADED
    action = _action(mcc)
    active = slot_number((mcc.get('operation') or {}).get('active_slot'))
    if action != 'Idle' and active is not None and active != SLOT_EXTERNAL:
        gate = active
        pos = 5 if action == 'Loading' else pos
    ttg = []
    variables = st.variables
    for t in range(num_slots):
        ttg.append(slot_number(variables.get('value_t%d' % t)))
    drying = ['active' if _flag(b.get('dry_state')) else 'inactive' for b in boxes[:max(1, (num_slots + 3) // 4)]]
    warnings = mcc.get('box_warning_info') or []
    return {
        'gate': gate,
        'filament_pos': pos,
        'action': action,
        'gate_status': gate_status,
        'gate_material': material,
        'gate_filament_name': name,
        'gate_color': color,
        'gate_vendor': vendor,
        'gate_temps': temps,
        'ttg_map': ttg,
        'drying_state': drying,
        'drying_end': [int(b.get('end_time') or 0) for b in boxes],
        'endless_spool_enabled': 1 if _flag(mcc.get('auto_reload_detect')) else 0,
        'reason_for_pause': '; '.join(str(w) for w in warnings) if warnings else '',
        'units_online': units,
        'bypass_info': external_info(st),
        'source': 'qidi',
    }
