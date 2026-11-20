# Minimale TJC-Datei für qbdisplay erstellen und aufspielen

qbdisplay zeichnet **alles zur Laufzeit** (Flächen, Kreise, Text, Icons) über
serielle Befehle. Die `.tft`-Datei auf dem Display enthält deshalb nur:

- **eine leere Seite** (`page0`),
- **8 Schriften** (Font-ID 0–7, Tabelle unten),
- **138 Icons** als Bilder (Bild-ID 0–137, Dateien in `icons/`). Nach Farbänderungen immer **alle** neu importieren.
- Ohne Klickarbeit: `python tools/build_tjc_project.py` baut das komplette Projekt (Seite, Schriften, Icons); danach nur noch „输出生产文件“ im Editor.

Diese Datei wird einmal erstellt. Design-Änderungen erfolgen danach im
Python-Code. Neu kompilieren muss man nur, wenn sich Schriften oder Icons
ändern.

> Getestet ist das bisher nur im Simulator. Alles, was hier mit **[prüfen]**
> markiert ist, muss am echten Display bestätigt werden.

---

## 1. Vorbereitung (Windows-PC)

1. **TJC-Editor installieren:** „USART HMI“ von <http://www.tjc1688.com>
   (Downloads → USART HMI). Kostenlos, nur Windows. Die Oberfläche ist
   chinesisch; die Menüpunkte unten nennen den chinesischen Begriff mit.
2. **Schriften installieren:** Die vier TTF-Dateien aus `fonts/` (Barlow,
   SIL Open Font License, siehe `fonts/OFL.txt`) per Rechtsklick → „Für alle
   Benutzer installieren“ einrichten. Danach den Editor neu starten.
3. **Displaymodell klären [prüfen]:** Auf der Rückseite des Displays im Plus4
   steht die Modellnummer, erwartet wird `TJC8048X250_011C` (800 × 480,
   kapazitiv, Serie X2). Wenn eine andere Nummer dasteht, im Editor genau diese
   wählen. Mit dem falschen Modell lehnt das Display die Datei ab.

## 2. Projekt anlegen

1. *文件 / Datei → 新建 / Neu*, Projektname `qbdisplay`.
2. **Modell:** Serie *X2* und das Modell aus Schritt 1.3 wählen.
3. **Ausrichtung:** *横屏 / Querformat*, 0° (800 × 480).
   *[prüfen]:* Ist das Bild im Plus4 um 180° gedreht eingebaut, stattdessen
   180° wählen. Erkennbar daran, dass die Touch-Koordinaten gespiegelt sind.
4. **Zeichenkodierung (字符编码):** `iso-8859-1`. Bietet der Editor das nicht
   an, `utf-8` nehmen und in `qbdisplay.cfg` unter `[display]`
   `encoding: utf-8` setzen.

## 3. Die Seite `page0`

- Hintergrund *sta* = *单色 / Vollfarbe*, *bco* = **2178** (`#0D1117` als
  RGB565).
- **Keine** Komponenten (Buttons, Texte …) anlegen.
- Ins Ereignis *前初始化事件 / Preinitialize* von `page0` schreiben:

  ```
  sendxy=1
  bkcmd=3
  ```

  `sendxy=1` ist das Wichtigste: Ohne Komponenten meldet das Display jede
  Berührung als Koordinate (0x67, x/y je 2 Byte, 1 = gedrückt, 0 = los).
  qbdisplay sendet beides beim Start ebenfalls.
- In `program.s` (Startdatei, links im Projektbaum) die Zeile `baud=115200`
  stehen lassen bzw. eintragen. Schneller wird es später über `target_baud` in
  der Konfiguration, siehe Abschnitt 7.

## 4. Schriften erzeugen (Font-ID 0–7)

*工具 / Werkzeuge → 字库制作 / Schriftgenerator.* Für **jede Zeile** der
Tabelle eine `.zi`-Datei erzeugen und sie danach **in genau dieser Reihenfolge**
im Panel *字库 / Schriften* mit „+“ hinzufügen. Die Reihenfolge ergibt die
Font-ID, und der Code (`qbdisplay/fonts.py`) verlässt sich darauf.

| ID | Schrift (installiert) | Höhe (字高) | Zeichen | Verwendung |
|---|---|---|---|---|
| 0 | Barlow Medium | 16 | iso-8859-1, alle | Nebeninfo (≈14 px) |
| 1 | Barlow SemiBold | 18 | iso-8859-1, alle | Labels, Statusleiste, Chips |
| 2 | Barlow Medium | 20 | iso-8859-1, alle | Fließtext |
| 3 | Barlow Bold | 24 | iso-8859-1, alle | Buttons, Titel |
| 4 | Barlow Semi Condensed Bold | 32 | iso-8859-1, alle | Werte, Dateinamen |
| 5 | Barlow Semi Condensed Bold | 40 | iso-8859-1, alle | IP, Restzeit, Prozent |
| 6 | Barlow Semi Condensed Bold | 64 | nur `0123456789 .,:-/%°Ch` | große Messwerte |
| 7 | Barlow Bold | 28 | iso-8859-1, alle | Dialogtitel |

Einstellungen im Generator:
- **Kodierung:** dieselbe wie im Projekt (`iso-8859-1`). Darin sind ä ö ü Ä Ö
  Ü ß ° · » « enthalten. Gedankenstrich, „…“ und Pfeile ersetzt der Code
  selbst durch `-`, `...` und `>`.
- **Kantenglättung (抗锯齿) an.** Der Code zeichnet Text immer mit
  Vollfarb-Hintergrund (`xstr … sta=1`), deshalb wird korrekt gemischt.
- **Proportional (nicht festbreit) [prüfen]:** Wenn der Generator die Wahl
  bietet („等宽“ aus), proportional wählen. Gibt es nur festbreite Schriften
  (ASCII = halbe Höhe), in `qbdisplay.cfg` `monospace_fonts: yes` setzen.
  Dann kürzt der Code Texte entsprechend früher.
- Der Code rechnet mit den Zeichenbreiten aus `qbdisplay/fontmetrics.py`
  (erzeugt aus genau diesen TTF-Dateien). Wenn eine andere Schrift verwendet
  wird: Datei in `fonts/` ablegen, Namen in `qbdisplay/fonts.py` anpassen und
  `python tools/make_fontmetrics.py` ausführen.

## 5. Icons importieren (Bild-ID 0–99)

Panel *图片 / Bilder → „+“* und **alle 100 PNG-Dateien aus `icons/`
importieren, sortiert nach Dateiname** (`000_…` bis `099_…`). Der
Dateiname beginnt mit der Bild-ID, die der Code erwartet:

```
000_wifi_18_text2_bar.png    -> ID 0   (Icon wifi, 18 px, Farbe text2 auf Grund bar)
...
099_nozzle_24_text2_surface2.png -> ID 99
```

- Nach dem Import **prüfen**, dass die ID im Editor dem Präfix entspricht
  (erste = 0, letzte = 99). Werden die Dateien in falscher Reihenfolge
  übernommen, einzeln in der richtigen Reihenfolge hinzufügen.
- Kompression: *无损 / verlustfrei* (oder höchste Qualität).
- TJC-Bilder haben keine Transparenz. Deshalb gibt es jedes Icon genau in
  den Farb-/Hintergrund-Kombinationen, die die Oberfläche benutzt.
  Fehlt zur Laufzeit eine Kombination, nimmt der Code dasselbe Icon auf einem
  anderen Hintergrund und schreibt eine Warnung ins Log.
- **Neue Icons:** Vorlage in `tools/icon_svg.py` ergänzen,
  `python tools/make_icons.py` ausführen. Neue Kombinationen werden hinten
  angehängt (ID 100, 101 …), vorhandene IDs bleiben. Danach nur die neuen
  PNGs nachimportieren und neu kompilieren.

## 6. Kompilieren

*编译 / Kompilieren* (F5). Fehler gibt es nur bei falschem Modell oder
fehlenden Schriften. Dann *文件 → 输出生产文件 / Datei → TFT-Datei
ausgeben*, Ziel z. B. `qbdisplay.tft`. Die Größe liegt grob bei 2–4 MB, je nach
Schriften.

**Vorher sichern:** Die QIDI-Oberfläche liegt auf dem Drucker als
`/root/800_480.tft` (bzw. im Backup `~/qidi-backup-*/`). Diese Datei ist der
**Rückweg** und wird genauso aufgespielt wie unten beschrieben.

## 7. Aufspielen

### a) Über die serielle Leitung (ohne Öffnen, empfohlen)

Auf dem Drucker (SSH als `mks`):

```sh
sudo systemctl stop makerbase-client   # xindi darf die Leitung nicht belegen
sudo systemctl stop qbdisplay          # falls schon installiert
cd ~/qbdisplay
python3 -m qbdisplay.upload ~/qbdisplay.tft --port /dev/ttyS1 --baud 115200 --upload-baud 921600
```

Was passiert (Protokoll **`whmi-wri`**, in `qbdisplay/upload.py`):

1. Leerbefehl + `connect` mit 0xFF 0xFF 0xFF. Das Display antwortet mit
   `comok <…>,<Modell>,…`. Das Werkzeug probiert 115200, 9600, 921600,
   256000 und 512000 Baud durch.
2. `whmi-wri <Dateigröße>,<Upload-Baud>,0`. Das Display schaltet auf die
   Upload-Baudrate um und meldet `0x05`.
3. Die Datei geht in Blöcken zu **4096 Byte** raus. Nach jedem Block wartet das
   Werkzeug auf `0x05`.
4. Nach dem letzten Block startet das Display neu (0x00 0x00 0x00 FF FF FF,
   dann 0x88).

Bei 921600 Baud dauern 3 MB etwa 40 s. Schlägt 921600 fehl
**[prüfen]**, mit `--upload-baud 115200` wiederholen (≈ 5 min).
Bricht der Upload ab, bleibt das Display im Update-Modus. Dann den Befehl
einfach erneut starten.

### b) Per microSD-Karte

1. Karte (≤ 32 GB) als **FAT32** formatieren und **nur** die `.tft`-Datei
   ins Hauptverzeichnis kopieren.
2. Drucker ausschalten. Den Kartenschacht auf der Display-Rückseite
   erreicht man nur, wenn man die Display-Abdeckung löst **[prüfen]**.
3. Karte einstecken und einschalten. Das Display zeigt den Fortschritt und
   danach „Update successed“ / „升级成功“.
4. Ausschalten, Karte entfernen, wieder einschalten.

## 8. Erster Test

```sh
cd ~/qbdisplay
python3 -m qbdisplay -v            # Log in der Konsole, Strg+C beendet
```

Erwartet im Log: `Display antwortet mit 115200 Baud`, danach Moonraker-
Verbindung. Tippen auf die Navigation muss die Seite wechseln.

Typische Probleme:

| Symptom | Ursache / Abhilfe |
|---|---|
| „Display antwortet nicht“ | xindi läuft noch (`systemctl stop makerbase-client`), falscher Port, oder `.tft` noch nicht aufgespielt |
| Berührungen ohne Wirkung | `sendxy=1` fehlt in *Preinitialize*; im Log mit `-v` auf `TouchEvent` achten |
| Touch gespiegelt | Ausrichtung im Editor 180° statt 0° |
| Kästchen statt Umlaute | Kodierung von Projekt/Schrift ≠ `encoding` in `qbdisplay.cfg` |
| Texte überlappen/abgeschnitten | festbreite Schriften erzeugt → `monospace_fonts: yes` |
| magenta Rahmen statt Icon (nur Simulator) / leere Stelle | Bild-IDs verschoben → Import-Reihenfolge prüfen |
| langsamer Bildaufbau | `target_baud: 921600` in `qbdisplay.cfg` (Display stellt per `baud=` um) |
