#!/bin/bash
# qbdisplay – Installation auf einem QIDI Plus4 mit QIDI-Firmware (getestet: 2.1.1)
#
# Copyright (C) 2026  STRE – GNU GPLv3
#
# Aufruf auf dem Drucker (als Benutzer mks, im entpackten Verzeichnis):
#     ./install.sh            # nimmt ./qbdisplay.tft
#     ./install.sh pfad.tft
#
# Ablauf: Sicherung der QIDI-Display-Datei -> qbdisplay.tft über QIDIs eigenen
# Update-Mechanismus aufs Display spielen (ca. 2 min) -> QIDIs Display-Programm
# (makerbase-client/xindi) abschalten -> qbdisplay als Dienst starten.
# Rückweg: ./uninstall.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
TFT="${1:-$DIR/qbdisplay.tft}"
BACKUP="$HOME/qbdisplay-backup"
CFG="$HOME/printer_data/config/qbdisplay.cfg"
API="http://127.0.0.1:7125"

say()  { printf '\n== %s\n' "$*"; }
fail() { printf '\nFEHLER: %s\n' "$*" >&2; exit 1; }

# Ein schlafendes Display nimmt kein Update an (QIDIs Programm wartet dann endlos).
# Darum vorher wecken und den Ruhezustand abschalten. Die Leitung muss frei sein.
wake_display() {
  sudo systemctl stop makerbase-client qbdisplay 2>/dev/null || true
  python3 - <<'PY' || echo "Hinweis: Display antwortet nicht (läuft trotzdem weiter)"
import os, termios, time
fd = os.open('/dev/ttyS1', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
a = termios.tcgetattr(fd)
a[0] = a[1] = a[3] = 0
a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
a[4] = a[5] = termios.B115200
termios.tcsetattr(fd, termios.TCSANOW, a)
for cmd in (b'sleep=0', b'thsp=0'):
    os.write(fd, cmd + b'\xff\xff\xff')
    time.sleep(0.3)
os.close(fd)
PY
}

say "Prüfungen"
[ -f "$TFT" ] || fail "Display-Datei $TFT fehlt"
[ -d "$DIR/qbdisplay" ] || fail "Programmordner $DIR/qbdisplay fehlt (im entpackten Paket starten)"
command -v python3 >/dev/null || fail "python3 fehlt"
systemctl cat makerbase-client >/dev/null 2>&1 || fail "makerbase-client.service nicht gefunden – ist das ein QIDI Plus4 mit QIDI-Firmware?"
STATE="$(curl -s "$API/printer/objects/query?print_stats=state" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["status"]["print_stats"]["state"])' 2>/dev/null || echo unbekannt)"
case "$STATE" in
  printing|paused) fail "Es läuft gerade ein Druck ($STATE). Bitte nach dem Druck installieren." ;;
  unbekannt) fail "Moonraker antwortet nicht unter $API" ;;
esac
echo "Druckerzustand: $STATE"
sudo -v || fail "sudo-Rechte nötig"

say "Sicherung der QIDI-Display-Datei"
mkdir -p "$BACKUP"
if [ -f "$BACKUP/800_480-qidi.tft" ]; then
  echo "vorhanden: $BACKUP/800_480-qidi.tft"
else
  # QIDIs Datei ist ~20 MB, unsere ~6 MB: nur eine echte QIDI-Datei sichern
  SIZE="$(sudo stat -c %s /root/800_480.tft.bak 2>/dev/null || echo 0)"
  if [ "$SIZE" -gt 15000000 ]; then
    sudo cp /root/800_480.tft.bak "$BACKUP/800_480-qidi.tft"
    sudo chown "$(id -u):$(id -g)" "$BACKUP/800_480-qidi.tft"
    sudo cat /root/xindi/version > "$BACKUP/qidi-version.txt" 2>/dev/null || true
    echo "gesichert: $BACKUP/800_480-qidi.tft"
  else
    echo "WARNUNG: keine QIDI-Display-Datei in /root/800_480.tft.bak gefunden."
    echo "         Für den Rückweg wird sie später gebraucht (QIDI-Update-Paket, Datei QD_Plus4_UI)."
    read -r -p "Trotzdem fortfahren? [j/N] " a; [ "$a" = "j" ] || exit 1
  fi
fi

say "Programm und Konfiguration"
python3 -m compileall -q "$DIR/qbdisplay" || fail "qbdisplay lässt sich nicht übersetzen"
if [ ! -f "$CFG" ]; then
  cp "$DIR/qbdisplay.example.cfg" "$CFG"
  echo "Konfiguration angelegt: $CFG"
else
  echo "Konfiguration bleibt: $CFG"
fi

say "Display-Datei aufspielen (ca. 2 min, Display bleibt solange dunkel)"
wake_display
sudo cp "$TFT" /root/800_480.tft
sync
sudo systemctl restart makerbase-client
for i in $(seq 1 90); do
  sudo test -e /root/800_480.tft || break
  sleep 10
done
sudo test -e /root/800_480.tft && fail "Display-Update nach 15 min nicht abgeschlossen (journalctl -u makerbase-client)"
echo "Display-Datei aufgespielt"
# merken, welche Datei auf dem Display ist (Update am Display spielt sie nur bei Änderung neu auf)
sha256sum "$TFT" | cut -d' ' -f1 > "$BACKUP/installed-tft.sha256"

say "Hilfsskript (Version lesen, Wechsel zur QIDI-Oberfläche am Display)"
sed "s#@BACKUP@#$BACKUP#; s#@APPDIR@#$DIR#; s#@USER@#$(id -un)#" "$DIR/systemd/qbdisplay-helper"   | sudo tee /usr/local/sbin/qbdisplay-helper >/dev/null
sudo chown root:root /usr/local/sbin/qbdisplay-helper
sudo chmod 755 /usr/local/sbin/qbdisplay-helper
# Regel erst prüfen, dann einsetzen (QIDI verbietet "sudo visudo"; der Syntax-Check geht ohne sudo)
RULE="$(mktemp)"
echo "$(id -un) ALL=(root) NOPASSWD: /usr/local/sbin/qbdisplay-helper" > "$RULE"
/usr/sbin/visudo -cf "$RULE" >/dev/null || { rm -f "$RULE"; fail "sudoers-Regel ungültig – nicht eingerichtet"; }
sudo install -o root -g root -m 440 "$RULE" /etc/sudoers.d/qbdisplay
rm -f "$RULE"
# -k mit Befehl: gespeicherte Anmeldung ignorieren -> prüft wirklich die NOPASSWD-Regel
if sudo -k -n /usr/local/sbin/qbdisplay-helper version >/dev/null 2>&1; then
  echo "eingerichtet: /usr/local/sbin/qbdisplay-helper"
else
  echo "WARNUNG: Hilfsskript braucht doch ein Passwort – Versionsanzeige und „Zu QIDI“ am Display"
  echo "         funktionieren dann nicht. Der Rest von qbdisplay läuft normal."
fi

say "Dienst einrichten"
sudo systemctl disable --now makerbase-client
sed -e "s#^User=.*#User=$(id -un)#" \
    -e "s#^WorkingDirectory=.*#WorkingDirectory=$DIR#" \
    -e "s#^ExecStart=.*#ExecStart=/usr/bin/python3 -m qbdisplay -c $CFG#" \
    "$DIR/systemd/qbdisplay.service" | sudo tee /etc/systemd/system/qbdisplay.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now qbdisplay
sleep 5
systemctl is-active --quiet qbdisplay || fail "qbdisplay startet nicht (journalctl -u qbdisplay)"

say "Fertig"
echo "qbdisplay läuft und startet ab jetzt automatisch."
echo "Protokoll:  journalctl -u qbdisplay -f"
echo "Rückweg:    $DIR/uninstall.sh"
