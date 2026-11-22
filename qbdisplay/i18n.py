# qbdisplay – Sprachen (Deutsch als Ausgangstext, Englisch)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Übersetzung mit dem deutschen Text als Schlüssel.

    from .i18n import _, N_
    label = _('Slot %s wird geladen ...') % letter    # erst übersetzen, dann formatieren

``N_('...')`` markiert Texte in Tabellen auf Modulebene (Fehlertexte,
Navigation ...). Sie bleiben deutsch gespeichert und werden erst beim Zeichnen
mit ``_(text)`` übersetzt – so wirkt eine Sprachumschaltung sofort.

Fehlt eine Übersetzung, erscheint der deutsche Text (einmalige Log-Warnung).
Texte für das Display nur im Zeichensatz ISO-8859-1 (siehe fonts.sanitize).
Test: tests/test_i18n.py prüft, dass jedes ``_('...')``/``N_('...')``-Literal im
Paket hier übersetzt ist und kein Eintrag verwaist.
"""

import logging

log = logging.getLogger(__name__)

DEFAULT = 'de'
LANGUAGES = (('de', 'Deutsch'), ('en', 'English'))

_lang = DEFAULT
_warned = set()


def N_(text):
    """Nur Markierung (für den Test); übersetzt wird später mit _()."""
    return text


def normalize(lang):
    """'EN', 'en_US', ' english ' -> 'en'; Unbekanntes -> None."""
    s = str(lang or '').strip().lower().replace('-', '_')
    if s.startswith('english'):
        s = 'en'
    elif s.startswith('deutsch') or s.startswith('german'):
        s = 'de'
    s = s.split('_')[0]
    return s if s in dict(LANGUAGES) else None


def set_language(lang):
    """Aktive Sprache setzen. Unbekannt -> Vorgabe 'de'. -> gesetzte Sprache."""
    global _lang
    code = normalize(lang)
    if code is None:
        if lang:
            log.warning('Unbekannte Sprache %r - nutze %s', lang, DEFAULT)
        code = DEFAULT
    _lang = code
    return code


def get_language():
    return _lang


def _(text):
    """Übersetzung von ``text`` (deutscher Ausgangstext) in die aktive Sprache."""
    if _lang == 'de' or not text or not any(ch.isalpha() for ch in text):
        return text
    table = TABLES.get(_lang) or {}
    t = table.get(text)
    if t is None:
        key = (_lang, text)
        if key not in _warned:
            _warned.add(key)
            log.warning('Übersetzung fehlt (%s): %r', _lang, text)
        return text
    return t


def decimal(text):
    """Dezimalzeichen der Sprache: '0.1' -> '0,1' (de) bzw. '0.1' (en)."""
    return text.replace('.', ',') if _lang == 'de' else text


# ---------------------------------------------------------------------------
# Englisch. Kurz halten: die Oberfläche kürzt sonst mit '...'
# (tools/render_all.py --lang en zeigt Kürzungen an).
# ---------------------------------------------------------------------------
EN = {
    # --- Navigation, Statusleiste --------------------------------------------
    'Start': 'Home',
    'Filament': 'Filament',
    'Bewegen': 'Move',
    'Dateien': 'Files',
    'System': 'System',
    'Bereit': 'Ready',
    'Keine Verbindung': 'No connection',
    'Startet ...': 'Starting ...',
    'Fehler': 'Error',
    'Pausiert · Fehler': 'Paused · error',
    'Pausiert': 'Paused',
    'Druckt · %d %%': 'Printing · %d %%',
    'Trocknet · %s': 'Drying · %s',
    'Trocknet': 'Drying',
    'Nur LAN': 'LAN only',
    'Cloud an': 'Cloud on',

    # --- Start ----------------------------------------------------------------
    'Düse': 'Nozzle',
    'Bett': 'Bed',
    'Kammer': 'Chamber',
    'Soll %d°': 'Set %d°',
    'aus': 'off',
    'Noch nichts gedruckt': 'Nothing printed yet',
    'Zuletzt gedruckt': 'Last print',
    '%d Schichten': '%d layers',
    '%d Farbe': '%d color',
    '%d Farben': '%d colors',
    'abgebrochen': 'cancelled',
    'Abbruch': 'aborted',
    'fertig': 'done',
    'Erneut drucken': 'Print again',
    'In der Düse': 'In the nozzle',
    'Rack (extern)': 'Rack (external)',
    'leer': 'empty',
    'Box %s °C · %s %% rF': 'Box %s °C · %s %% RH',
    'Licht': 'Light',
    'Schicht': 'Layer',
    'Restzeit': 'Time left',
    'Fertig ca.': 'ETA',
    'Weiter': 'Resume',
    'Pause': 'Pause',
    'Anpassen': 'Tune',
    'Abbrechen': 'Cancel',
    'Farbwechsel %d von %d': 'Color change %d of %d',
    'Farbwechsel %d': 'Color change %d',
    'noch ca. %s': 'approx. %s left',
    'Schneiden': 'Cut',
    '%s entladen': 'Unload %s',
    'Alt': 'old',
    '%s laden': 'Load %s',
    'Neu': 'new',
    'Spülen': 'Purge',
    'Weiterdrucken': 'Resume',
    'Spülen %d %%': 'Purge %d %%',
    'Farbwechsel: %d von %d erledigt': 'Color changes: %d of %d done',
    'Farbwechsel bisher: %d': 'Color changes so far: %d',
    'Kein Farbwechsel geplant': 'No color changes planned',
    'Filament im Druck': 'Filament in use',

    # --- Filament / Box ---------------------------------------------------------
    'In Düse': 'Loaded',            # Chip auf der Slot-Karte: max. ~74 px
    'Lädt ...': 'Loading',
    'Entlädt': 'Unload',
    'Leer': 'Empty',
    'Extern': 'External',
    'Spule hinten': 'Rear spool',
    'nicht belegt': 'not in use',
    'Spule einlegen': 'Insert spool',
    'wird erkannt': 'auto-detected',
    'Ohne Material': 'No material',
    'bitte zuordnen': 'please assign',
    'Zustand unbekannt': 'State unknown',
    '%s in Düse laden': 'Load %s to nozzle',
    'Während Druck gesperrt': 'Locked while printing',
    'Laden und Entladen sind gesperrt, solange ein Druck läuft.':
        'Loading and unloading are locked while a print is running.',
    'Läuft ...': 'Running ...',
    'Die Box arbeitet gerade. Bitte warten.': 'The box is busy. Please wait.',
    'Aus Düse entladen': 'Unload from nozzle',
    'Die Düse heizt auf, das Filament wird zurück in %s gezogen. Dauer ca. 1-2 min.':
        'The nozzle heats up and the filament is pulled back into %s. Takes about 1-2 min.',
    'Die Düse heizt auf, das Filament wird aus dem Extruder gezogen. Dauer ca. 1-2 min.':
        'The nozzle heats up, the filament is pulled out of the extruder. About 1-2 min.',
    'Rack in Düse laden': 'Load rack to nozzle',
    'Filament von der hinteren Spule bis zum Extruder einführen, dann laden.':
        'Feed filament from the rear spool up to the extruder, then load.',
    'Slot leer': 'Slot empty',
    'Filament in Slot %s einlegen - die Box zieht es automatisch ein.':
        'Insert filament into slot %s - the box pulls it in automatically.',
    '%s wird zuerst aus der Düse entladen, dann %s geladen und gespült. Dauer ca. 3-4 min.':
        '%s is unloaded first, then %s is loaded and purged. Takes about 3-4 min.',
    '%s wird bis in die Düse geladen und gespült. Dauer ca. 2 min.':
        '%s is loaded into the nozzle and purged. Takes about 2 min.',
    'Rack · externe Spule': 'Rack · external spool',
    'Slot %s · %s': 'Slot %s · %s',
    'ohne Material': 'no material',
    'Trocknet · noch %s': 'Drying · %s left',
    'Trocknung läuft': 'Drying in progress',
    'Trocknung aus': 'Drying off',
    'Box %d': 'Box %d',
    'Weiter: Box %d': 'Next: box %d',
    # Betrieb ohne Box (0.3.0)
    'Externe Spule': 'External spool',
    'Extern · %s': 'External · %s',
    'Keine QIDI Box verbunden': 'No QIDI Box connected',
    'Gedruckt wird von der Spule hinten am Drucker. Wird die Box angesteckt, erkennt QIDI sie '
    'selbst und hier erscheinen wieder ihre Slots.':
        'Printing uses the spool at the back of the printer. Plug in the box and QIDI detects '
        'it by itself; its slots then show up here again.',
    'Material und Farbe stellst du im Slicer oder in QIDIs Weboberfläche ein.':
        'Set material and colour in the slicer or in QIDI\'s web interface.',
    'Gedruckt wird von der externen Spule': 'Printing uses the external spool',
    'Box anstecken': 'Plug in the box',
    'QIDI erkennt sie selbst, Klipper startet dabei neu':
        'QIDI detects it by itself; Klipper restarts',
    'Trocknung': 'Drying',
    'Trocknen': 'Dry',
    'Slot %s bearbeiten': 'Edit slot %s',
    'Material': 'Material',
    'Weitere ...': 'More ...',
    'Farbe': 'Color',
    'Mehr': 'More',
    'Hersteller': 'Vendor',
    'Generisch': 'Generic',
    'Andere': 'Other',
    'Kein Material': 'No material',
    'Trocknen %d °C': 'Dry at %d °C',
    'Vorschau Slot %s': 'Preview slot %s',
    'RFID lesen': 'Read RFID',
    'Speichern': 'Save',

    # --- Trocknung ----------------------------------------------------------------
    'Box-Temperatur': 'Box temperature',
    'Heizung an': 'Heater on',
    'Heizung aus': 'Heater off',
    'Luftfeuchte': 'Humidity',
    'kein Sensorwert': 'no sensor value',
    'Profil': 'Profile',
    'Vorschlag aus der Belegung: Slot %s enthält %s.':
        'Suggested from the slots: slot %s holds %s.',
    'Vorschlag aus der Belegung: Slot %s enthalten %s.':
        'Suggested from the slots: slots %s hold %s.',
    'Bei gemischter Belegung gilt das Profil mit der niedrigsten Temperatur.':
        'With mixed materials, the profile with the lowest temperature applies.',
    'Spulen bleiben in der Box.': 'Spools stay in the box.',
    'Keine Slot-Belegung bekannt. Profil passend zum Material wählen.':
        'Slot contents unknown. Choose the profile that matches the material.',
    'Einstellung': 'Settings',
    'Temperatur': 'Temperature',
    'Dauer': 'Duration',
    'Übernehmen': 'Apply',
    'Trocknen starten': 'Start drying',
    'Manuell': 'Manual',
    'übrig · %d %%': 'left · %d %%',
    'Restzeit unbekannt': 'Time left unknown',
    'Läuft seit': 'Running for',
    '(Start %s)': '(started %s)',
    'Ändern': 'Change',
    'Heizung an · Lüfter an': 'Heater on · fan on',
    'beim Start %d %%': 'at start %d %%',
    'Startwert unbekannt': 'Start value unknown',

    # --- Bewegen ------------------------------------------------------------------
    'hinten': 'back',
    'vorne': 'front',
    'links': 'left',
    'rechts': 'right',
    'Bett hoch': 'bed up',
    'Bett runter': 'bed down',
    'Position': 'Position',
    'referenziert': 'homed',
    'nicht referenziert': 'not homed',
    'Schrittweite (mm)': 'Step (mm)',
    'Alle Achsen': 'Home all',
    'Motoren aus': 'Motors off',
    'Düse %s °C': 'Nozzle %s °C',
    'ab %d °C': 'min. %d °C',
    'Soll %d': 'set %d',
    'Extruder': 'Extruder',
    'Zurück %d': 'Retract %d',
    'Fördern %d': 'Extrude %d',
    'Lüfter': 'Fans',
    'Tippen: 0 / 50 / 100 %': 'Tap: 0 / 50 / 100 %',
    'Bauteil': 'Part',
    'Hilfslüfter': 'Aux',

    # --- Dateien ------------------------------------------------------------------
    '%d Dateien · neueste zuerst': '%d files · newest first',
    'Keine Dateien gefunden': 'No files found',
    'Druck läuft (Start gesperrt)': 'printing (start locked)',
    '%d.%m. %H:%M': '%d/%m %H:%M',
    'Seite': 'Page',

    # --- System -------------------------------------------------------------------
    'Netzwerk': 'Network',
    'Box': 'Box',
    'Kalibrieren': 'Calibrate',
    'Sprache': 'Language',
    'Info & Update': 'Info & update',
    'Nur LAN – Cloud aus': 'LAN only - cloud off',
    'Cloud-Dienste aktiv': 'Cloud services active',
    'Keine Verbindung zu QIDI-Servern. Zugriff nur aus dem eigenen Netz.':
        'No connection to QIDI servers. Access from your own network only.',
    'QIDI-Cloud oder Fernzugriff laufen noch. Antippen zum Abschalten.':
        'QIDI cloud or remote access still running. Tap to switch off.',
    'WLAN verbunden · Signal %s': 'Wi-Fi connected · signal %s',
    'unbekannt': 'unknown',
    'gut': 'good',
    'mittel': 'fair',
    'schwach': 'weak',
    'Kabel verbunden': 'Ethernet connected',
    'Nicht verbunden': 'Not connected',
    'QIDI-Cloud / App': 'QIDI cloud / app',
    'Fernzugriff (QIDI Link)': 'Remote access (QIDI Link)',
    'Slicer & Browser im LAN': 'Slicer & browser on LAN',
    'aktiv': 'active',
    'läuft': 'running',
    'blockiert': 'blocked',
    'Automatisch nachladen': 'Auto reload',
    'Leere Spule: gleiches Material aus anderem Slot':
        'Empty spool: same material from another slot',
    'Trocknung: max. %d °C': 'Drying: max. %d °C',
    'Schutz der Spulenkörper; einstellbar in qbdisplay.cfg':
        'Protects the spools; set in qbdisplay.cfg',
    'Materialliste': 'Material list',
    '%d Materialien, %d Farben, %d Hersteller': '%d materials, %d colors, %d vendors',
    'Slots prüfen': 'Check slots',
    'Box prüft, in welchen Slots Filament steckt':
        'Box checks which slots hold filament',
    'Prüfen': 'Check',
    'gesperrt': 'locked',
    'Bettvermessung': 'Bed mesh',
    'Bett wird abgetastet, ca. 5 min': 'Probes the bed, approx. 5 min',
    'Bettvermessung starten?': 'Start bed mesh?',
    'Input Shaping': 'Input shaping',
    'Resonanzmessung X/Y, laut, ca. 3 min': 'Resonance test X/Y, loud, approx. 3 min',
    'Resonanzmessung starten?': 'Start resonance test?',
    'Starten': 'Start',
    'Hinweis': 'Note',
    'Ergebnisse speichert Klipper erst nach SAVE_CONFIG (Weboberfläche).':
        'Klipper saves results only after SAVE_CONFIG (web UI).',
    'Antippen zum Wechseln': 'Tap to switch',
    'Gilt sofort und bleibt nach einem Neustart erhalten.':
        'Applies at once and is kept after a restart.',
    'Klipper neu': 'Restart Klipper',
    'Firmware neu': 'Restart firmware',
    'Neu zeichnen': 'Redraw',
    'Ausschalten': 'Shut down',
    'Suche nach Updates ...': 'Checking for updates ...',
    'Update-Prüfung fehlgeschlagen': 'Update check failed',
    'QIDI-Update: %s': 'QIDI update: %s',
    'QIDI aktuell (%s)': 'QIDI current (%s)',
    'QIDI-Server offline': 'QIDI server offline',
    'qbdisplay %s verfügbar': 'qbdisplay %s available',
    'Testversion %s verfügbar': 'Test version %s available',
    'Installieren': 'Install',
    'qbdisplay %s installieren?': 'Install qbdisplay %s?',
    'Wird von GitHub geladen und geprüft, dann startet qbdisplay neu (neue Display-Datei: ca. 2 min dunkel). Bei Problemen automatisch zurück.':
        'Downloaded from GitHub and verified, then qbdisplay restarts (new display file: about 2 min dark). Rolls back automatically if anything fails.',
    'Während eines Drucks nicht möglich': 'Not possible while printing',
    'Update auf %s läuft - qbdisplay startet gleich neu': 'Updating to %s - qbdisplay restarts shortly',
    'Update von Hand nötig': 'Manual update needed',
    'Diese Version ändert Teile mit Root-Rechten. Bitte das Paket wie bei der Erstinstallation mit ./install.sh einspielen (siehe README).':
        'This version changes parts that run as root. Please install the package with ./install.sh like the first time (see README).',
    'Update fehlgeschlagen: %s': 'Update failed: %s',
    'qbdisplay %s installiert': 'qbdisplay %s installed',
    'Update fehlgeschlagen': 'Update failed',
    'qbdisplay läuft weiter mit Version %s. Grund: %s': 'qbdisplay keeps running version %s. Reason: %s',
    'Update wird geladen und geprüft ...': 'Downloading and verifying update ...',
    'Update läuft, qbdisplay startet neu ...': 'Updating, qbdisplay restarts ...',
    'qbdisplay aktuell': 'qbdisplay up to date',
    'Suchen': 'Check',
    'Zu QIDI': 'To QIDI',
    'Zur QIDI-Oberfläche wechseln?': 'Switch to the QIDI UI?',
    'qbdisplay wird beendet und die QIDI-Oberfläche aufgespielt (ca. 7 min, Display solange '
    'dunkel). Danach sind QIDI-Updates und die QIDI-App wieder verfügbar. qbdisplay später per '
    './install.sh zurückholen.':
        'qbdisplay stops and the QIDI UI is flashed (about 7 min, screen stays dark). QIDI '
        'updates and the QIDI app are then available again. Bring qbdisplay back later with '
        './install.sh.',
    'Wechseln': 'Switch',
    'Wechsel zur QIDI-Oberfläche läuft (ca. 7 min)': 'Switching to the QIDI UI (about 7 min)',
    'Wechsel nicht möglich - install.sh erneut ausführen':
        'Switch not possible - run install.sh again',

    # --- Dialoge ------------------------------------------------------------------
    'Bitte bestätigen': 'Please confirm',
    'Slot %s': 'Slot %s',
    'Aus': 'Off',
    '%s · Ist %s °C': '%s · now %s °C',
    'Soll %d °C': 'Target %d °C',
    'Soll: aus': 'Target: off',
    'Druck anpassen': 'Tune print',
    'Geschwindigkeit': 'Speed',
    'Fluss': 'Flow',
    'Z-Versatz (Babystep)': 'Z offset (babystep)',
    'Schließen': 'Close',

    # --- Meldungen, Rückfragen (app.py) -----------------------------------------
    'Slot %s wird geladen ...': 'Loading slot %s ...',
    'Beim Laden von Slot %s': 'While loading slot %s',
    'Rack wird geladen ...': 'Loading rack ...',
    'Beim Laden vom Rack': 'While loading from rack',
    'Filament wird entladen ...': 'Unloading filament ...',
    'Beim Entladen von Slot %s': 'While unloading slot %s',
    'Beim Entladen': 'While unloading',
    'Slot %s auswerfen?': 'Eject slot %s?',
    'Das Filament wird ganz aus der Box geschoben (vorher ggf. aus der Düse entladen). '
    'Danach kann die Spule entnommen werden.':
        'The filament is pushed fully out of the box (unloaded from the nozzle first if '
        'needed). Then the spool can be removed.',
    'Auswerfen': 'Eject',
    'Slot %s wird ausgeworfen ...': 'Ejecting slot %s ...',
    'Beim Auswerfen von Slot %s': 'While ejecting slot %s',
    'Slot %s gespeichert': 'Slot %s saved',
    'RFID gelesen': 'RFID read',
    'RFID wird gelesen ...': 'Reading RFID ...',
    'Slots prüfen?': 'Check slots?',
    'Die Box bewegt jedes Filament kurz an, um zu prüfen, ob es da ist. Dauer ca. 1 min.':
        'The box briefly moves each filament to check that it is there. Takes about 1 min.',
    'Slots werden geprüft ...': 'Checking slots ...',
    'Trocknung %s gestartet': 'Drying %s started',
    'Restzeit unbekannt - bitte über »Ändern« neu starten':
        "Time left unknown - please restart via 'Change'",
    'Trocknung + 1 h': 'Drying + 1 h',
    'Trocknung beendet': 'Drying stopped',
    'Trocknung abbrechen?': 'Stop drying?',
    'Die Box-Heizung wird ausgeschaltet. Die bisherige Trocknungszeit geht nicht verloren, '
    'die Spulen kühlen ab.':
        'The box heater is switched off. The drying done so far is not lost; the spools '
        'cool down.',
    'Dauer laut Slicer: %s.': 'Slicer estimate: %s.',
    'Drucken?': 'Print?',
    'Bett und Düse heizen sofort auf.': 'Bed and nozzle start heating right away.',
    'Drucken': 'Print',
    'Druck wird gestartet ...': 'Starting print ...',
    'Druck abbrechen?': 'Cancel print?',
    'Der laufende Druck wird beendet und kann nicht fortgesetzt werden.':
        'The current print will be stopped and cannot be resumed.',
    'Druck abbrechen': 'Cancel print',
    'Druck wird abgebrochen ...': 'Cancelling print ...',
    'Druck wird pausiert ...': 'Pausing print ...',
    'Druck wird fortgesetzt ...': 'Resuming print ...',
    'Referenzfahrt ...': 'Homing ...',
    '%s läuft danach selbstständig. Der Drucker darf dabei nicht berührt werden.':
        '%s then runs on its own. Do not touch the printer meanwhile.',
    'Klipper neu starten?': 'Restart Klipper?',
    'Die Druckersoftware startet neu (ca. 20 s).': 'The printer software restarts (approx. 20 s).',
    'Neu starten': 'Restart',
    'Neustart ...': 'Restarting ...',
    'Firmware neu starten?': 'Restart firmware?',
    'Klipper und alle Controller (inkl. Box) werden neu gestartet.':
        'Klipper and all controllers (incl. the box) will restart.',
    'Drucker ausschalten?': 'Shut down printer?',
    'Das Linux-System fährt herunter. Danach kann der Netzschalter betätigt werden.':
        'The Linux system shuts down. You can then switch off the power.',
    'Fährt herunter ...': 'Shutting down ...',
    'qbdisplay ersetzt xindi und sendet selbst nichts an QIDI. Umschalten der übrigen '
    'Cloud-Teile (frpc, mqtt) ist nicht eingerichtet - siehe README.md.':
        'qbdisplay replaces xindi and sends nothing to QIDI itself. Switching the other '
        'cloud parts (frpc, mqtt) is not set up - see README.md.',
    'Wird umgeschaltet ...': 'Switching ...',
    'Fehler: %s': 'Error: %s',
    'WLAN ändern': 'Change Wi-Fi',
    'Das WLAN wird über die Weboberfläche oder per SSH (nmtui) eingerichtet. Am Display '
    'folgt das später.':
        'Set up Wi-Fi via the web UI or SSH (nmtui). Setup on the display will follow '
        'later.',
    'Klipper gestoppt': 'Klipper stopped',
    'Druckersoftware angehalten': 'Printer software halted',
    'Ursache beheben (z. B. Sensor, Kabel).': 'Fix the cause (e.g. sensor, cable).',
    '»Firmware neu« startet Klipper und alle Controller neu.':
        "'Restart firmware' restarts Klipper and all controllers.",
    'Klipper meldet einen Fehler': 'Klipper reports an error',
    'Druck pausiert': 'Print paused',
    'Beim Laden': 'While loading',
    'Box · Slot %s': 'Box · slot %s',
    'Düse hält %d °C': 'nozzle held at %d °C',
    'Neuer Versuch ...': 'Retrying ...',
    'Wird entladen ...': 'Unloading ...',
    'Erneut versuchen': 'Retry',
    'Entladen': 'Unload',
    'Druckfehler': 'Print error',
    'Druck abgebrochen': 'Print aborted',
    'Interner Fehler bei %s': 'Internal error in %s',

    # --- Fehler (errors.py) -------------------------------------------------------
    'Filament lädt nicht in den Slot': "Filament won't load into the slot",
    'Spule prüfen: Ist das Filamentende frei und nicht verhakt?':
        'Check the spool: is the filament end free and not snagged?',
    'Filamentende gerade abschneiden und bis zum Widerstand einschieben.':
        'Cut the filament end straight and push it in until it stops.',
    '»Erneut versuchen« – der Slot zieht das Filament neu ein.':
        "Tap 'Retry' - the slot feeds the filament in again.",
    'Im Extruder steckt schon Filament': 'Extruder already holds filament',
    'Zuerst das geladene Filament entladen.': 'Unload the loaded filament first.',
    'Danach den gewünschten Slot erneut laden.': 'Then load the desired slot again.',
    'Filament lässt sich nicht aus dem Slot ziehen': "Filament won't pull back from the slot",
    'Spule auf Verhaken oder Knoten prüfen.': 'Check the spool for snags or knots.',
    'Filament an der Box vorsichtig von Hand zurückziehen.':
        'Carefully pull the filament back by hand at the box.',
    '»Erneut versuchen«.': "Tap 'Retry'.",
    'Bitte zuerst den Extruder entladen': 'Unload the extruder first',
    'Im Extruder steckt noch Filament eines anderen Slots.':
        'The extruder still holds filament from another slot.',
    '»Entladen« wählen, danach erneut laden.': "Tap 'Unload', then load again.",
    'Slot ist leer': 'Slot is empty',
    'Filament in den Slot einlegen, bis es greift.': 'Insert filament into the slot until it grips.',
    'Danach »Erneut versuchen«.': "Then tap 'Retry'.",
    'Filament erreicht den Extruder nicht': 'Filament does not reach the extruder',
    'Schlauch am Druckkopf auf Knick oder lose Kupplung prüfen.':
        'Check the tube at the toolhead for kinks or a loose coupling.',
    'Filament am Slot zurückziehen, Ende gerade abschneiden.':
        'Pull the filament back at the slot and cut the end straight.',
    '»Erneut versuchen« – das Filament wird neu eingezogen.':
        "Tap 'Retry' - the filament is fed in again.",
    'Extruder ist nicht geladen': 'Extruder is not loaded',
    'Es steckt kein Filament im Druckkopf.': 'There is no filament in the toolhead.',
    'Einen Slot auswählen und laden.': 'Select a slot and load it.',
    'Filament lässt sich nicht aus dem Extruder ziehen': "Filament won't unload from the extruder",
    'Düse auf Drucktemperatur bringen (Bewegen › Temperaturen).':
        'Heat the nozzle to printing temperature (Move > Extruder).',
    'Prüfen, ob das Filament abgeschnitten wurde.': 'Check whether the filament was cut.',
    'Filamentzustand unplausibel': 'Filament state inconsistent',
    'Sensoren zeigen einen Zustand, der nicht passt.': 'The sensors report an inconsistent state.',
    'Filamentweg prüfen und ggf. Filament entladen.':
        'Check the filament path and unload if needed.',
    'Filament ist bereits geladen': 'Filament is already loaded',
    'Keine Aktion nötig.': 'No action needed.',
    'Filament hat sich aufgewickelt': 'Filament is tangled',
    'Spule in der Box prüfen – Filament hat sich um die Rolle gewickelt.':
        'Check the spool in the box - filament has wrapped around the roller.',
    'Wicklung lösen, Filament straff aufspulen.': 'Free the wrap and rewind the filament tightly.',
    'Selbsttest der Box fehlgeschlagen': 'Box self-test failed',
    'USB-Kabel der Box prüfen.': "Check the box's USB cable.",
    'Drucker neu starten (System › Info).': 'Restart the printer (System > Info).',
    'Filament aufgebraucht': 'Filament ran out',
    'Neue Spule in den Slot einlegen oder anderen Slot zuordnen.':
        'Insert a new spool or assign another slot.',
    '»Erneut versuchen« setzt den Druck fort.': "'Retry' resumes the print.",
    'Spülen fehlgeschlagen': 'Purge failed',
    'Abfallschacht und Düse prüfen.': 'Check the waste chute and the nozzle.',
    'Kein Ersatz-Filament festgelegt': 'No backup filament set',
    'Für das automatische Nachladen ist kein passender Slot zugeordnet.':
        'No matching slot is assigned for auto reload.',
    'Slot mit gleichem Material belegen (Filament › Slot bearbeiten).':
        'Load a slot with the same material (Filament > Edit slot).',
    'PTFE-Schlauch geknickt': 'PTFE tube kinked',
    'Schlauch zwischen Box und Druckkopf auf Knicke prüfen.':
        'Check the tube between box and toolhead for kinks.',
    'Verlegung korrigieren, dann »Erneut versuchen«.': "Fix the routing, then tap 'Retry'.",
    'Filament wurde entladen – bitte neu laden': 'Filament was unloaded - please reload',
    'Slot erneut in die Düse laden.': 'Load the slot into the nozzle again.',
    'Filament nicht erkannt': 'Filament not recognized',
    'RFID-Etikett nicht lesbar – Material von Hand zuordnen.':
        'RFID tag unreadable - assign the material by hand.',
    'Kein passender Ersatz-Slot': 'No matching backup slot',
    'Keine Spule mit gleichem Material und gleicher Farbe vorhanden.':
        'No spool with the same material and color.',
    'Spule nachlegen oder Zuordnung ändern.': 'Add a spool or change the assignment.',
    'Automatisches Nachladen fehlgeschlagen': 'Auto reload failed',
    'Ersatz-Slot prüfen (Filamentende frei?).': 'Check the backup slot (filament end free?).',
    'Box meldet Fehler %s': 'Box reports error %s',
    'Filamentweg prüfen.': 'Check the filament path.',
    'Unbekannter Fehler': 'Unknown error',
    'Box angehalten': 'Box stopped',
    'Slot': 'Slot',
    'Box-Ausgang': 'Box outlet',
    'Schlauch': 'Tube',

    # --- Zustände (model.py) ------------------------------------------------------
    'Feuchte unbekannt': 'Humidity unknown',
    'für %s ok': 'OK for %s',
    'für %s zu feucht': 'too humid for %s',
    'für %s viel zu feucht': 'far too humid for %s',
    'morgen %s': 'tomorrow %s',
    '%02d.%02d. %s': '%02d/%02d %s',

    # --- Farbnamen (colors.py) ----------------------------------------------------
    'Schwarz': 'Black',
    'Weiß': 'White',
    'Grau': 'Gray',
    'Silber': 'Silver',
    'Hellgrau': 'Light gray',
    'Rot': 'Red',
    'Hellrot': 'Light red',
    'Orange': 'Orange',
    'Gelb': 'Yellow',
    'Gelbgrün': 'Yellow-green',
    'Hellgrün': 'Light green',
    'Mintgrün': 'Mint green',
    'Grün': 'Green',
    'Petrol': 'Teal',
    'Blau': 'Blue',
    'Dunkelblau': 'Dark blue',
    'Hellblau': 'Light blue',
    'Himmelblau': 'Sky blue',
    'Lila': 'Purple',
    'Violett': 'Violet',
    'Flieder': 'Lilac',
    'Rosa': 'Rose',
    'Pink': 'Pink',
    'Holzbraun': 'Wood brown',
    'Braun': 'Brown',
    'Elfenbein': 'Ivory',
    'Beige': 'Beige',
}

TABLES = {'en': EN}
