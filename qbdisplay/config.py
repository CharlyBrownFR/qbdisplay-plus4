# qbdisplay – Einstellungen
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Einstellungen aus ``~/printer_data/config/qbdisplay.cfg`` (INI-Format).
Alle Werte haben Vorgaben für den QIDI Plus4 mit einer QIDI Box."""

import configparser
import os

DEFAULT_PATH = '~/printer_data/config/qbdisplay.cfg'

DEFAULTS = {
    'display': {
        'port': '/dev/ttyS1',
        'baud': '115200',          # Startwert; wird bei Bedarf automatisch gesucht
        'target_baud': '0',        # z. B. 921600: nach dem Start umschalten (0 = aus)
        'encoding': 'iso-8859-1',  # Zeichensatz der TJC-Schriften
        'monospace_fonts': 'no',   # yes, falls die TJC-Fonts festbreit erzeugt wurden
        'window': '6',             # max. unquittierte Befehle
        'sleep_after': '600',      # Sekunden ohne Berührung bis Display schläft (0 = nie)
        'brightness': '100',
        'thumbnails': 'yes',       # Vorschaubild als Mosaik zeichnen
        'thumb_block': 'auto',     # Mosaik: auto oder Blockgröße in Pixel (Vorgabe für System > Anzeige)
        # Sprache der Oberfläche: de | en. Nur Vorgabe – die Auswahl unter
        # System › Sprache wird in [state] file gespeichert und hat Vorrang.
        'language': 'de',
    },
    'moonraker': {
        'socket': '~/printer_data/comms/moonraker.sock',
        'http': 'http://127.0.0.1:7125',
    },
    'printer': {
        'name': 'Plus4',
        'chamber': 'heater_generic chamber',
        'light_pin': 'caselight',
        'fan_part': 'cooling_fan',
        'fan_aux': 'auxiliary_cooling_fan',
        'fan_chamber': 'chamber_circulation_fan',
        'gcode_dir': '~/printer_data/gcodes',
        'min_extrude_temp': '170',
    },
    'box': {
        # happyhare = eigenes System (firmware/); qidi = QIDI-Stock-Firmware 2.1.1, dann
        # gelten die Vorgaben aus QIDI_BOX für alle nicht gesetzten Werte
        'backend': 'happyhare',
        'num_slots': '4',
        # Happy-Hare-v4-Objekte (Unit "unit0"). Stock+Kompatibilitaetsschicht:
        # heater_generic heater_box1 / aht20_f heater_box1 (siehe qbdisplay.example.cfg)
        'heater': 'heater_generic unit0_heater',
        'climate_sensor': 'temperature_sensor unit0_Env',
        'filament_list': '~/printer_data/config/filament_list.cfg',
        'dry_max_temp': '65',
        'purge_seconds': '150',
        'pre_gate_sensor': 'mmu_entry_%d',
        'gate_sensor': 'mmu_shared_exit',
        'extruder_sensor': 'extruder',
        'toolhead_sensor': 'toolhead',
        # Befehle an Klipper; Platzhalter {gate} {temp} {minutes}; "\n" trennt Befehle.
        # Vorgabe = Happy Hare nativ. Mit QIDI-Kompatibilitaetsmakros: E_LOAD SLOT=slot{gate} usw.
        'cmd_load': 'MMU_SELECT GATE={gate}\\nMMU_LOAD',
        'cmd_unload': 'MMU_UNLOAD',
        'cmd_eject': 'MMU_EJECT GATE={gate}',
        'cmd_rfid': 'MMU_NFC_SCAN GATE={gate}',
        'cmd_dry_start': 'MMU_HEATER DRY=1 TEMP={temp} TIMER={minutes}',
        'cmd_dry_stop': 'MMU_HEATER STOP=1',
        'cmd_retry': 'MMU_UNLOCK',
        'cmd_load_rack': 'MMU_SELECT BYPASS=1\\nMMU_LOAD',
        'cmd_endless': 'MMU_ENDLESS_SPOOL ENABLE={on}',
        'cmd_check': 'MMU_CHECK_GATE ALL=1',
        # yes: Slot-Zuordnung direkt per MMU_GATE_MAP; no: SAVE_VARIABLE filament_slotN (QIDI-Weg)
        'gate_map_direct': 'yes',
    },
    'drying': {
        # Name = Temperatur °C, Dauer h, Materialtypen
        'PLA': '55, 12, PLA PLA-CF PLA+',
        'PETG': '55, 12, PETG PETG-CF PET PCTG',
        'ABS/ASA': '60, 12, ABS ASA ABS-GF ASA-CF',
        'TPU': '60, 12, TPU TPE',
    },
    'network': {
        # optionale Befehle für den Nur-LAN-Schalter (z. B. sudo -n Skripte)
        'lan_only_on_cmd': '',
        'lan_only_off_cmd': '',
    },
    'update': {
        # GitHub-Repository, in dem nach neuen qbdisplay-Versionen gesucht wird (leer = aus)
        'repo': 'CharlyBrownFR/qbdisplay-plus4',
        # auch Vorabversionen (Testversionen) anbieten – nur für Testdrucker
        'prerelease': 'no',
    },
    'state': {
        'file': '~/printer_data/qbdisplay_state.json',
    },
}


# QIDI-Stock-Firmware 2.1.1: dieselben Befehle wie QIDIs Display-Programm xindi 2.1.1,
# am Gerät mitgeschnitten (2026-11-20): E_LOAD/E_BOX SLOT=<Zahl, ab 0>,
# ENABLE_BOX_DRY BOX=1 END_TIME=<Stunden> TEMP=<°C>. RFID_READ nutzt laut Binary SLOT=slotN.
# [prüfen] E_UNLOAD-Parameter und Befehl für die externe Spule (16).
QIDI_BOX = {
    'heater': 'heater_generic heater_box1',
    'climate_sensor': 'aht20_f heater_box1',
    'filament_list': '~/printer_data/config/officiall_filas_list.cfg',
    'cmd_load': 'E_LOAD SLOT={gate}',
    'cmd_unload': 'E_UNLOAD SLOT={gate}',
    'cmd_eject': 'E_BOX SLOT={gate}',
    'cmd_rfid': 'RFID_READ SLOT=slot{gate}',
    'cmd_dry_start': 'ENABLE_BOX_DRY BOX=1 END_TIME={hours} TEMP={temp}',
    'cmd_dry_stop': 'DISABLE_BOX_DRY BOX=1',
    'cmd_retry': 'TRY_MOVE_AGAIN',
    'cmd_load_rack': 'E_LOAD SLOT=16',
    'cmd_endless': 'SAVE_VARIABLE VARIABLE=auto_reload_detect VALUE={on}',
    'cmd_check': 'BOX_SELF_INSPECTION',
    'gate_map_direct': 'no',
}


class Config(object):
    def __init__(self, path=None):
        self.cp = configparser.ConfigParser(interpolation=None)
        self.cp.read_dict(DEFAULTS)
        self.path = os.path.expanduser(path or DEFAULT_PATH)
        user = configparser.ConfigParser(interpolation=None)
        if os.path.exists(self.path):
            user.read(self.path, encoding='utf-8')
        backend = user.get('box', 'backend', fallback=self.cp.get('box', 'backend'))
        if backend.strip().lower() == 'qidi':
            self.cp.read_dict({'box': QIDI_BOX})
        self.cp.read_dict(user)

    def get(self, section, key):
        return self.cp.get(section, key)

    def path_of(self, section, key):
        return os.path.expanduser(self.cp.get(section, key))

    def getint(self, section, key):
        return self.cp.getint(section, key)

    def getfloat(self, section, key):
        return self.cp.getfloat(section, key)

    def getbool(self, section, key):
        return self.cp.getboolean(section, key)

    def command(self, key, **values):
        """Befehlsvorlage aus [box] mit Platzhaltern fuellen; '\\n' wird zum Zeilenumbruch."""
        tpl = self.cp.get('box', key).replace('\\n', '\n')
        return tpl.format(**values)

    def drying_profiles(self):
        """[(name, temp, hours, [typen])] in Dateireihenfolge."""
        out = []
        for name, val in self.cp.items('drying'):
            parts = [p.strip() for p in val.split(',')]
            try:
                temp = int(float(parts[0]))
                hours = float(parts[1])
            except (IndexError, ValueError):
                continue
            types = parts[2].split() if len(parts) > 2 else [name]
            out.append((name.upper() if name.islower() else name, temp, hours,
                        [t.upper() for t in types]))
        return out
