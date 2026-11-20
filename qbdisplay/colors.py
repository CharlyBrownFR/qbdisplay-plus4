# qbdisplay – Farben (Designsystem aus docs/display-design-review.md)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Farb-Tokens und Umrechnung nach RGB565.

Intern werden Farben als ``'#RRGGBB'`` geführt. Erst beim Senden an das Display
wandelt :func:`rgb565` sie in den Dezimalwert um, den TJC-Befehle erwarten.
Keine Verläufe, keine Transparenz: abgedunkelte Flächen werden als fertige
Mischfarbe berechnet (:func:`mix`).
"""

from .i18n import _, N_

TOKENS = {
    # Grundflächen (kühles Fast-Schwarz; Stufen so gewählt, dass sie auch nach
    # RGB565-Quantisierung noch unterscheidbar sind)
    'bg': '#0D1117',          # Bildschirmgrund (= bco 2178 von page0 in der TJC-Datei)
    'bar': '#080A10',         # Statusleiste, Navigation
    'surface': '#111821',     # Kacheln
    'surface2': '#19222E',    # hervorgehobene Kachel, sekundärer Button
    'surface3': '#253142',    # gedrückt, Toggle aus, Badges
    'line': '#1F2A39',        # 1-px-Rahmen
    'text': '#F3F6FA',
    'text2': '#B4BFCD',
    'text3': '#7D8A9C',
    'accent': '#22D3EE',      # Cyan: Primäraktion, Auswahl, aktive Navigation, "in Düse"
    'on_accent': '#04242B',   # Text auf Akzent
    'tint': '#0C2730',        # Akzent-getönte Fläche (aktive Kachel, Auswahl)
    'tint2': '#124550',       # Badge auf getönter Fläche
    'ok': '#3DDC84',
    'ok_bg': '#11301F',       # Pille "Bereit", LAN-Karte
    'ok_line': '#1F5A3A',
    'run_bg': '#0B2B33',      # Pille "Druckt"
    'info': '#A08CFF',        # Violett: laufende Box-Vorgänge (Farbwechsel, Laden)
    'on_info': '#160E38',
    'info_bg': '#1C1838',
    'info_line': '#3E3478',
    'warn': '#FFB43F',
    'warn_bg': '#33260E',
    'err': '#FF5C5C',
    'err_bg': '#3A1418',
    'heat': '#FF8A3D',
    'heat_bg': '#3A2112',
    'ring': '#8B9097',        # heller Ring um Filamentfarben (#E8EDF3 zu ~55 % auf Grund)
    'scrim': '#020306',       # Abdunkelung hinter Dialogen
    'white': '#FFFFFF',
    'black': '#000000',
}


def hex_to_rgb(color):
    """'#RRGGBB' (oder 'RRGGBB') -> (r, g, b). Ungültig -> None."""
    if color is None:
        return None
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        return tuple(int(c) for c in color[:3])
    s = str(color).strip()
    if s in TOKENS:
        s = TOKENS[s]
    s = s.lstrip('#')
    if len(s) == 8:          # RRGGBBAA -> Alpha ignorieren
        s = s[:6]
    if len(s) == 3:
        s = ''.join(ch * 2 for ch in s)
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return None


def rgb_to_hex(rgb):
    return '#%02X%02X%02X' % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def resolve(color):
    """Token-Name oder Hex -> '#RRGGBB'."""
    if color in TOKENS:
        return TOKENS[color]
    rgb = hex_to_rgb(color)
    if rgb is None:
        raise ValueError('Unbekannte Farbe: %r' % (color,))
    return rgb_to_hex(rgb)


def rgb565(color):
    """Farbe -> RGB565 als Dezimalzahl (so erwartet es TJC, z. B. ``fill``)."""
    r, g, b = hex_to_rgb(resolve(color))
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def rgb565_to_rgb(value):
    """RGB565 -> (r, g, b) wie es das Display anzeigt (für den Simulator)."""
    value = int(value) & 0xFFFF
    r = (value >> 11) & 0x1F
    g = (value >> 5) & 0x3F
    b = value & 0x1F
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def mix(c1, c2, t):
    """Mischung c1*(1-t) + c2*t als '#RRGGBB'."""
    a = hex_to_rgb(resolve(c1))
    b = hex_to_rgb(resolve(c2))
    return rgb_to_hex(tuple(x * (1 - t) + y * t for x, y in zip(a, b)))


def luminance(color):
    r, g, b = (c / 255.0 for c in hex_to_rgb(resolve(color)))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# Ring um Filamentfarben: heller Ring (#E8EDF3, 55 %) über Kachelgrund
def ring_on(bg):
    return mix(bg, '#E8EDF3', 0.55)


# Benannte Filamentfarben (deutsch) für Anzeige "Schwarz", "Holzbraun", ...
# color_name() liefert sie in der aktiven Sprache (i18n).
COLOR_NAMES = [
    ('#060606', N_('Schwarz')), ('#151515', N_('Schwarz')), ('#000000', N_('Schwarz')),
    ('#FAFAFA', N_('Weiß')), ('#F2F2F2', N_('Weiß')), ('#FFFFFF', N_('Weiß')),
    ('#8C8C8C', N_('Grau')), ('#898F9B', N_('Grau')), ('#C0C0C0', N_('Silber')),
    ('#D9E3ED', N_('Hellgrau')), ('#C62828', N_('Rot')), ('#FF362D', N_('Rot')),
    ('#FE717A', N_('Hellrot')), ('#E8762B', N_('Orange')), ('#F28636', N_('Orange')),
    ('#F4C430', N_('Gelb')), ('#DFD628', N_('Gelb')), ('#CADE4B', N_('Gelbgrün')),
    ('#5CF30F', N_('Hellgrün')), ('#63E492', N_('Mintgrün')), ('#2E7D32', N_('Grün')),
    ('#228332', N_('Grün')), ('#00897B', N_('Petrol')), ('#1E5BB8', N_('Blau')),
    ('#2850FF', N_('Blau')), ('#1353AB', N_('Blau')), ('#1714B0', N_('Dunkelblau')),
    ('#5EA9FD', N_('Hellblau')), ('#90CAF9', N_('Hellblau')), ('#99DEFF', N_('Himmelblau')),
    ('#6A3FA0', N_('Lila')), ('#A878FF', N_('Violett')), ('#CEC0FE', N_('Flieder')),
    ('#E57BB0', N_('Rosa')), ('#FE98FE', N_('Pink')), ('#B87F2B', N_('Holzbraun')),
    ('#5D4037', N_('Braun')), ('#6E3812', N_('Braun')), ('#E2DFCD', N_('Elfenbein')),
    ('#CAC59F', N_('Beige')),
]


def color_name(color):
    """Nächstliegender Farbname zu '#RRGGBB' in der aktiven Sprache (leer bei unbekannt)."""
    rgb = hex_to_rgb(color)
    if rgb is None:
        return ''
    best, best_d = '', None
    for hx, name in COLOR_NAMES:
        o = hex_to_rgb(hx)
        d = sum((a - b) ** 2 for a, b in zip(rgb, o))
        if best_d is None or d < best_d:
            best, best_d = name, d
    return _(best)


# HH erlaubt in gate_color auch w3c-Farbnamen; die häufigsten hier
W3C = {
    'black': '#000000', 'white': '#FFFFFF', 'red': '#FF0000', 'green': '#008000',
    'blue': '#0000FF', 'yellow': '#FFFF00', 'orange': '#FFA500', 'purple': '#800080',
    'gray': '#808080', 'grey': '#808080', 'silver': '#C0C0C0', 'brown': '#A52A2A',
    'pink': '#FFC0CB', 'cyan': '#00FFFF', 'magenta': '#FF00FF', 'gold': '#FFD700',
}


def parse_filament_color(value):
    """HH-gate_color ('RRGGBB', '#RRGGBB', 'RRGGBBAA', 'red') -> '#RRGGBB' oder None."""
    if not value:
        return None
    s = str(value).strip()
    if s.lower() in W3C:
        return W3C[s.lower()]
    rgb = hex_to_rgb(s)
    return rgb_to_hex(rgb) if rgb else None
