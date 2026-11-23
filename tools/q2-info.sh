#!/bin/bash
# qbdisplay – collect information about a QIDI printer (Q2, Max4, Plus4, ...), read only
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
#
# Only READS information, changes nothing, needs no sudo.
# Run on the printer as user mks:
#     bash printer-info.sh
# Result: ~/printer-info.txt  (please have a look at it before you send it)
# No IP addresses, Wi-Fi names, host names, passwords or serial numbers are collected.

NAME="$(basename "${0%.sh}")"
case "$NAME" in bash|sh|-bash) NAME=printer-info ;; esac
OUT="${OUT:-$HOME/$NAME.txt}"
API="http://127.0.0.1:7125"

sec() { printf '\n===== %s =====\n' "$1"; }
get() { curl -s --max-time 5 "$API$1" || echo "(no answer from Moonraker)"; }

{
echo "printer-info $(date -u '+%Y-%m-%d %H:%M UTC')"

sec "System"
uname -srm
tr -d '\0' < /proc/device-tree/model 2>/dev/null; echo
grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release 2>/dev/null
python3 --version 2>&1
dpkg-query -W -f='${Package} ${Version}\n' 'qidi*' 2>/dev/null
ls /home/mks 2>/dev/null | grep -iE 'QD_|xindi|tjc|qbdisplay|screen|client|klipper|moonraker|fluidd|mainsail' | tr '\n' ' '; echo

sec "Display (framebuffer)"
ls -l /dev/fb* 2>/dev/null || echo "(no /dev/fb*)"
for fb in /sys/class/graphics/fb*; do
    [ -e "$fb/name" ] || continue
    echo "-- $fb"
    for f in name virtual_size bits_per_pixel stride rotate modes blank; do
        printf '%-15s %s\n' "$f" "$(cat "$fb/$f" 2>/dev/null | tr '\n' ' ')"
    done
done
ls /sys/class/drm 2>/dev/null | tr '\n' ' '; echo
cat /sys/class/backlight/*/max_brightness 2>/dev/null | sed 's/^/backlight max: /'

sec "Touch / input devices"
grep -E '^(N:|H:)' /proc/bus/input/devices 2>/dev/null
ls -l /dev/input/ 2>/dev/null
python3 - <<'PY' 2>&1
import fcntl, glob, struct
for dev in sorted(glob.glob('/dev/input/event*')):
    try:
        with open(dev, 'rb') as f:
            for code, name in ((0, 'X'), (1, 'Y'), (0x35, 'MT_X'), (0x36, 'MT_Y')):
                buf = bytearray(24)
                try:
                    fcntl.ioctl(f, 0x80184540 + code, buf)
                    v = struct.unpack('6i', bytes(buf))
                    print('%s %-5s min=%d max=%d' % (dev, name, v[1], v[2]))
                except OSError:
                    pass
    except OSError as e:
        print('%s: %s' % (dev, e.strerror))
PY

sec "Serial ports"
ls -l /dev/ttyS* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

sec "Display program and services"
# QIDI's screen program: xindi (TJC display) on the Plus4, QD_*/bin/client (LVGL) on the Q2
ps -eo pid,user,args \
    | grep -E 'xindi|QD_|/client|qbdisplay|lvgl|screen|/home/mks/[^ ]*/bin/|^ *[0-9]+ +root +/root/' \
    | grep -vE 'grep|klippy|moonraker|sshd|nginx|crowsnest|ustreamer'
for pid in $(pgrep -f 'xindi|QD_|/client|qbdisplay'); do
    echo "cgroup of $pid: $(grep -o 'system.slice/[^ ]*' /proc/$pid/cgroup 2>/dev/null | head -1)"
done
systemctl list-units --type=service --no-pager --no-legend 2>/dev/null \
    | grep -iE 'client|makerbase|klipper|moonraker|qidi|xindi|algo|screen|display|qbdisplay'
for u in $(systemctl list-units --type=service --no-pager --no-legend 2>/dev/null \
        | grep -ioE '[a-z0-9_.@-]*(client|makerbase|xindi|screen|display)[a-z0-9_.@-]*\.service'); do
    echo "-- $u"
    systemctl show -p ExecStart -p User -p WorkingDirectory "$u" 2>/dev/null
done

sec "Klipper / Moonraker"
get /printer/info | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    d.get("result", {}).pop("hostname", None)
    print(json.dumps(d))
except Exception as e:
    print("(not readable: %s)" % e)
'
get /server/info | head -c 1500
echo

sec "Klipper objects"
OBJS="$(get /printer/objects/list)"
echo "$OBJS"

sec "Box state"
Q="$(echo "$OBJS" | python3 -c '
import json, sys, urllib.parse
try:
    objs = json.load(sys.stdin)["result"]["objects"]
except Exception:
    objs = []
keys = ("box", "multi_color", "aht20", "slot", "buffer", "print_stats")
print("&".join(urllib.parse.quote(o) for o in objs if any(k in o for k in keys)
               and not o.startswith(("mcu", "gcode_macro"))))
')"
[ -n "$Q" ] && get "/printer/objects/query?$Q"
echo
echo "save_variables (box/slot/filament related only):"
get "/printer/objects/query?save_variables" | python3 -c '
import json, sys
try:
    v = json.load(sys.stdin)["result"]["status"]["save_variables"]["variables"]
except Exception as e:
    sys.exit("  (not readable: %s)" % e)
for k in sorted(v):
    if any(s in k for s in ("box", "slot", "filament", "color", "vendor", "tool")):
        print("  %s = %s" % (k, v[k]))
'

sec "Config files (section names only)"
ls ~/printer_data/config 2>/dev/null | tr '\n' ' '; echo
for f in printer.cfg box.cfg box1.cfg; do
    echo "-- $f"
    grep -E '^\[' ~/printer_data/config/$f 2>/dev/null | tr '\n' ' '; echo
done
} > "$OUT" 2>&1

echo "Done: $OUT"
echo "Please check the file, then send it (e.g. copy it with WinSCP / scp)."
