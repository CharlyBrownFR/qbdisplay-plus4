# qbdisplay – eigene Display-Software für das TJC-Touch-Display des QIDI Plus4
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""qbdisplay ersetzt QIDIs geschlossenes Display-Programm ``xindi``.

Aufbau:
  tjc.py        Treiber für das TJC/Nextion-Display (Befehle, Events, Flusskontrolle)
  canvas.py     Zeichenfläche: Primitive -> TJC-Befehle
  sim.py        Simulator: führt TJC-Befehle mit Pillow aus (nur PC)
  moonraker.py  JSON-RPC-Client (Unix-Socket, HTTP-Fallback)
  model.py      Zustandsmodell (Moonraker-Status -> Anzeige-Daten)
  ui/           Seiten und Bausteine
  app.py        Hauptschleife, Seitenwechsel, Befehle

Muss mit Python 3.7 (Debian 10 auf dem Drucker) laufen, nur Standardbibliothek
(+ optional pyserial).
"""

__version__ = "0.4.2"
