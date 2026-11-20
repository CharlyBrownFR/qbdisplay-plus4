# qbdisplay – Fehlertexte in Klartext
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Übersetzt QIDI-Fehlercodes (QDE_004_xxx) und Happy-Hare-Pausegründe
(``mmu.reason_for_pause``) in einen Titel (aktive Sprache, siehe i18n), nummerierte Schritte und
die passende Alternativ-Aktion. Dazu der Filamentweg mit Sensorstatus.

Eigene Formulierungen; die englischen Kurztexte der Codes stehen in
docs/findings.md.
"""

import collections
import re

from .i18n import _, N_

ErrorInfo = collections.namedtuple('ErrorInfo', 'code title steps alt')
# alt: 'unload' (Slot/Extruder entladen) | 'load' | 'none'

QDE = {
    '001': (N_('Filament lädt nicht in den Slot'),
            [N_('Spule prüfen: Ist das Filamentende frei und nicht verhakt?'),
             N_('Filamentende gerade abschneiden und bis zum Widerstand einschieben.'),
             N_('»Erneut versuchen« – der Slot zieht das Filament neu ein.')], 'unload'),
    '002': (N_('Im Extruder steckt schon Filament'),
            [N_('Zuerst das geladene Filament entladen.'),
             N_('Danach den gewünschten Slot erneut laden.')], 'unload'),
    '003': (N_('Filament lässt sich nicht aus dem Slot ziehen'),
            [N_('Spule auf Verhaken oder Knoten prüfen.'),
             N_('Filament an der Box vorsichtig von Hand zurückziehen.'),
             N_('»Erneut versuchen«.')], 'none'),
    '004': (N_('Bitte zuerst den Extruder entladen'),
            [N_('Im Extruder steckt noch Filament eines anderen Slots.'),
             N_('»Entladen« wählen, danach erneut laden.')], 'unload'),
    '005': (N_('Slot ist leer'),
            [N_('Filament in den Slot einlegen, bis es greift.'),
             N_('Danach »Erneut versuchen«.')], 'none'),
    '006': (N_('Filament erreicht den Extruder nicht'),
            [N_('Schlauch am Druckkopf auf Knick oder lose Kupplung prüfen.'),
             N_('Filament am Slot zurückziehen, Ende gerade abschneiden.'),
             N_('»Erneut versuchen« – das Filament wird neu eingezogen.')], 'unload'),
    '007': (N_('Extruder ist nicht geladen'),
            [N_('Es steckt kein Filament im Druckkopf.'),
             N_('Einen Slot auswählen und laden.')], 'none'),
    '009': (N_('Filament lässt sich nicht aus dem Extruder ziehen'),
            [N_('Düse auf Drucktemperatur bringen (Bewegen › Temperaturen).'),
             N_('Prüfen, ob das Filament abgeschnitten wurde.'),
             N_('»Erneut versuchen«.')], 'none'),
    '010': (N_('Filamentzustand unplausibel'),
            [N_('Sensoren zeigen einen Zustand, der nicht passt.'),
             N_('Filamentweg prüfen und ggf. Filament entladen.'),
             N_('»Erneut versuchen«.')], 'unload'),
    '011': (N_('Filament ist bereits geladen'), [N_('Keine Aktion nötig.')], 'none'),
    '013': (N_('Filament hat sich aufgewickelt'),
            [N_('Spule in der Box prüfen – Filament hat sich um die Rolle gewickelt.'),
             N_('Wicklung lösen, Filament straff aufspulen.'),
             N_('»Erneut versuchen«.')], 'none'),
    '015': (N_('Selbsttest der Box fehlgeschlagen'),
            [N_('USB-Kabel der Box prüfen.'),
             N_('Drucker neu starten (System › Info).')], 'none'),
    '016': (N_('Filament aufgebraucht'),
            [N_('Neue Spule in den Slot einlegen oder anderen Slot zuordnen.'),
             N_('»Erneut versuchen« setzt den Druck fort.')], 'load'),
    '017': (N_('Spülen fehlgeschlagen'),
            [N_('Abfallschacht und Düse prüfen.'),
             N_('»Erneut versuchen«.')], 'none'),
    '018': (N_('Kein Ersatz-Filament festgelegt'),
            [N_('Für das automatische Nachladen ist kein passender Slot zugeordnet.'),
             N_('Slot mit gleichem Material belegen (Filament › Slot bearbeiten).')], 'none'),
    '019': (N_('PTFE-Schlauch geknickt'),
            [N_('Schlauch zwischen Box und Druckkopf auf Knicke prüfen.'),
             N_('Verlegung korrigieren, dann »Erneut versuchen«.')], 'none'),
    '020': (N_('Filament wurde entladen – bitte neu laden'),
            [N_('Slot erneut in die Düse laden.')], 'load'),
    '021': (N_('Filament nicht erkannt'),
            [N_('RFID-Etikett nicht lesbar – Material von Hand zuordnen.')], 'none'),
    '022': (N_('Kein passender Ersatz-Slot'),
            [N_('Keine Spule mit gleichem Material und gleicher Farbe vorhanden.'),
             N_('Spule nachlegen oder Zuordnung ändern.')], 'none'),
    '023': (N_('Automatisches Nachladen fehlgeschlagen'),
            [N_('Ersatz-Slot prüfen (Filamentende frei?).'),
             N_('»Erneut versuchen«.')], 'load'),
}

# Happy-Hare-Gründe (englisch) -> nächster QDE-Fall
HH_PATTERNS = [
    (r'(load|homing).*(extruder|toolhead|nozzle)|extruder.*(sensor|entry)', '006'),
    (r'unload.*(extruder|toolhead)|extruder.*unload', '009'),
    (r'(gate|pre.?gate).*(load|home|sensor)|load.*gate', '001'),
    (r'unload.*gate|gate.*unload', '003'),
    (r'runout|empty|exhaust', '016'),
    (r'clog|tangle|jam', '013'),
    (r'bowden', '019'),
    (r'endless spool|no alternative', '022'),
]


def _info(code, t):
    """Tabelleneintrag -> ErrorInfo in der aktiven Sprache."""
    return ErrorInfo(code, _(t[0]), [_(x) for x in t[1]], t[2])


def classify(text):
    """Fehlertext -> ErrorInfo (Texte in der aktiven Sprache)."""
    text = text or ''
    m = re.search(r'QDE_(\d{3})_(\d{3})', text)
    if m:
        code = 'QDE_%s_%s' % m.groups()
        t = QDE.get(m.group(2))
        if t:
            return _info(code, t)
        return ErrorInfo(code, _('Box meldet Fehler %s') % m.group(2),
                         [_('Filamentweg prüfen.'), _('»Erneut versuchen«.')], 'none')
    low = text.lower()
    for pat, key in HH_PATTERNS:
        if re.search(pat, low):
            return _info('', QDE[key])
    first = text.strip().splitlines()[0] if text.strip() else _('Unbekannter Fehler')
    return ErrorInfo('', _('Box angehalten'), [first, _('Filamentweg prüfen.'),
                                               _('»Erneut versuchen«.')], 'none')


# ---------------------------------------------------------------------------
# Filamentweg
# ---------------------------------------------------------------------------
PathNode = collections.namedtuple('PathNode', 'key label state')
# state je Verbindung: 'ok' | 'bad' | 'unknown'


def filament_path(sensors, gate, cfg_pre='mmu_entry_%d', cfg_gate='mmu_shared_exit',
                  cfg_extruder='extruder', cfg_toolhead='toolhead'):
    """-> (knoten, verbindungen). Knoten: Slot, Box-Ausgang, Schlauch, Extruder.
    Verbindungs-Zustand aus den HH-Sensoren (True/False/None)."""
    sensors = sensors or {}

    def val(name):
        return sensors.get(name)
    slot_s = val(cfg_pre % gate) if gate is not None and gate >= 0 else None
    gate_s = val(cfg_gate)
    ext_s = val(cfg_extruder)
    if ext_s is None:
        ext_s = val(cfg_toolhead)
    # Zielsensor jeder Verbindung: Slot->Box und Box->Schlauch = Box-Ausgang,
    # Schlauch->Extruder = Extruder-Sensor. Nach der ersten Lücke: unbekannt.
    out = []
    broken = False
    for s in (gate_s, gate_s, ext_s):
        if broken:
            out.append('unknown')
        elif s is True:
            out.append('ok')
        elif s is False:
            out.append('bad')
            broken = True
        else:
            out.append('unknown')
    nodes = [PathNode('slot', _('Slot'), 'ok' if slot_s else ('bad' if slot_s is False else 'unknown')),
             PathNode('gate', _('Box-Ausgang'), 'ok' if gate_s else ('bad' if gate_s is False else 'unknown')),
             PathNode('tube', _('Schlauch'), 'unknown'),
             PathNode('extruder', _('Extruder'), 'ok' if ext_s else ('bad' if ext_s is False else 'unknown'))]
    return nodes, out
