#!/bin/bash
# qbdisplay – collect information about a QIDI Q2 (read only)
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
#     bash q2-info.sh
# Result: ~/q2-info.txt  (please have a look at it before you send it)
# No IP addresses, Wi-Fi names, passwords or serial numbers are collected.

OUT="${OUT:-$HOME/q2-info.txt}"
API="http://127.0.0.1:7125"

sec() { printf '\n===== %s =====\n' "$1"; }
get() { curl -s --max-time 5 "$API$1" || echo "(no answer from Moonraker)"; }

{
echo "q2-info $(date -u '+%Y-%m-%d %H:%M UTC')"

sec "System"
uname -srm
grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release 2>/dev/null
python3 --version 2>&1
dpkg-query -W -f='${Package} ${Version}\n' 'qidi*' 2>/dev/null
ls /home/mks 2>/dev/null | tr '\n' ' '; echo

sec "Display (framebuffer)"
for f in name virtual_size bits_per_pixel stride rotate modes blank; do
    printf '%-15s %s\n' "$f" "$(cat /sys/class/graphics/fb0/$f 2>/dev/null | tr '\n' ' ')"
done
ls -l /dev/fb* 2>/dev/null
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
ps -eo pid,user,args | grep -E 'QD_Q2|xindi|qbdisplay' | grep -v grep
for pid in $(pgrep -f 'QD_Q2/bin/client'); do
    echo "cgroup of $pid: $(grep -o 'system.slice/[^ ]*' /proc/$pid/cgroup | head -1)"
done
systemctl list-units --type=service --no-pager --no-legend 2>/dev/null \
    | grep -iE 'client|makerbase|klipper|moonraker|qidi|algo|screen|display'
for u in makerbase-client; do systemctl cat "$u" 2>/dev/null; done

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
get /printer/objects/list
echo

sec "Box state"
get "/printer/objects/query?box_extras&multi_color_controller&print_stats=state&heater_generic%20heater_box1&aht20_f%20heater_box1"
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
