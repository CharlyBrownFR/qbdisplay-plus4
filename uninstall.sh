#!/bin/bash
# qbdisplay – zurück zur QIDI-Oberfläche
#
# Copyright (C) 2026  STRE – GNU GPLv3
#
#     ./uninstall.sh                 # nimmt die Sicherung aus install.sh
#     ./uninstall.sh QD_Plus4_UI     # oder eine QIDI-Display-Datei aus dem Update-Paket
#
# Schaltet qbdisplay ab, spielt QIDIs Display-Datei auf (ca. 7 min) und startet QIDIs
# Display-Programm wieder. Programmdateien und Konfiguration bleiben liegen.
set -euo pipefail

BACKUP="$HOME/qbdisplay-backup"
TFT="${1:-$BACKUP/800_480-qidi.tft}"
API="http://127.0.0.1:7125"

say()  { printf '\n== %s\n' "$*"; }
fail() { printf '\nFEHLER: %s\n' "$*" >&2; exit 1; }

[ -f "$TFT" ] || fail "QIDI-Display-Datei $TFT fehlt (QIDI-Update-Paket: Datei QD_Plus4_UI)"
STATE="$(curl -s "$API/printer/objects/query?print_stats=state" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["status"]["print_stats"]["state"])' 2>/dev/null || echo unbekannt)"
case "$STATE" in
  printing|paused) fail "Es läuft gerade ein Druck ($STATE). Bitte danach zurückwechseln." ;;
esac
sudo -v || fail "sudo-Rechte nötig"

say "qbdisplay abschalten"
sudo systemctl disable --now qbdisplay 2>/dev/null || true
sudo rm -f /etc/systemd/system/qbdisplay.service
sudo systemctl daemon-reload

say "QIDI-Display-Datei aufspielen (ca. 7 min, Display bleibt solange dunkel)"
sudo cp "$TFT" /root/800_480.tft
sync
sudo systemctl enable makerbase-client
sudo systemctl restart makerbase-client
for i in $(seq 1 90); do
  sudo test -e /root/800_480.tft || break
  sleep 10
done
sudo test -e /root/800_480.tft && fail "Display-Update nach 15 min nicht abgeschlossen (journalctl -u makerbase-client)"

say "Fertig"
echo "Die QIDI-Oberfläche ist zurück. Online-Updates funktionieren wieder wie gewohnt."
