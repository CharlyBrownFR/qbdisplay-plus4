# qbdisplay – Vorschaubilder als Farbmosaik
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""TJC kann zur Laufzeit keine Bilder laden. Das Slicer-Vorschaubild
(PNG neben der G-Code-Datei, ``.thumbs/``) wird deshalb auf dem Host zu einem
groben Raster gemittelt und mit ``fill`` gezeichnet (Lauflängen je Zeile).

Kleiner PNG-Decoder (8 Bit, RGB/RGBA/Graustufen, ohne Interlace) nur mit
zlib – Pillow gibt es auf dem Drucker nicht.
"""

import os
import struct
import zlib


def decode_png(data):
    """-> (breite, höhe, pixel[y][x] = (r, g, b, a))"""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('kein PNG')
    pos = 8
    idat = []
    w = h = depth = ctype = interlace = None
    palette = None
    trns = None
    while pos < len(data):
        ln, typ = struct.unpack('>I4s', data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', chunk)
        elif typ == b'PLTE':
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif typ == b'tRNS':
            trns = chunk
        elif typ == b'IDAT':
            idat.append(chunk)
        elif typ == b'IEND':
            break
    if depth != 8 or interlace:
        raise ValueError('PNG-Format nicht unterstützt (Tiefe %s, Interlace %s)' % (depth, interlace))
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b''.join(idat))
    stride = w * bpp
    rows = []
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        ft = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        rows.append(line)
        prev = line
    pixels = []
    for line in rows:
        row = []
        for x in range(w):
            o = x * bpp
            if ctype == 6:
                row.append(tuple(line[o:o + 4]))
            elif ctype == 2:
                row.append((line[o], line[o + 1], line[o + 2], 255))
            elif ctype == 0:
                row.append((line[o], line[o], line[o], 255))
            elif ctype == 4:
                row.append((line[o], line[o], line[o], line[o + 1]))
            else:
                idx = line[o]
                r, g, b = palette[idx]
                a = trns[idx] if trns is not None and idx < len(trns) else 255
                row.append((r, g, b, a))
        pixels.append(row)
    return w, h, pixels


def mosaic(pixels, w, h, n, bg=(0x1F, 0x27, 0x33)):
    """Mittelt auf n × n Felder (mit Alpha über ``bg``). -> Liste von Zeilen
    mit '#RRGGBB' bzw. None für "leer/Hintergrund"."""
    out = []
    for gy in range(n):
        y0, y1 = gy * h // n, max(gy * h // n + 1, (gy + 1) * h // n)
        row = []
        for gx in range(n):
            x0, x1 = gx * w // n, max(gx * w // n + 1, (gx + 1) * w // n)
            sr = sg = sb = sa = 0
            cnt = 0
            for y in range(y0, y1, max(1, (y1 - y0) // 3)):
                for x in range(x0, x1, max(1, (x1 - x0) // 3)):
                    r, g, b, a = pixels[y][x]
                    sr += r * a
                    sg += g * a
                    sb += b * a
                    sa += a
                    cnt += 1
            alpha = sa / (255.0 * cnt) if cnt else 0
            if alpha < 0.25:
                row.append(None)
                continue
            r, g, b = sr / float(sa), sg / float(sa), sb / float(sa)
            r = r * alpha + bg[0] * (1 - alpha)
            g = g * alpha + bg[1] * (1 - alpha)
            b = b * alpha + bg[2] * (1 - alpha)
            # auf RGB565-Stufen runden -> mehr gleiche Nachbarn, kürzere Befehle
            row.append('#%02X%02X%02X' % (int(r) & 0xF8, int(g) & 0xFC, int(b) & 0xF8))
        out.append(row)
    return out


def pick_thumbnail(metadata, min_size=24):
    """Kleinstes Vorschaubild, das noch >= min_size ist."""
    thumbs = [t for t in (metadata or {}).get('thumbnails') or [] if t.get('relative_path')]
    if not thumbs:
        return None
    thumbs.sort(key=lambda t: t.get('width', 0))
    for t in thumbs:
        if t.get('width', 0) >= min_size:
            return t
    return thumbs[-1]


def load_mosaic(gcode_dir, filename, metadata, n):
    t = pick_thumbnail(metadata, n)
    if t is None:
        return None
    path = os.path.join(os.path.expanduser(gcode_dir), os.path.dirname(filename),
                        t['relative_path'])
    with open(path, 'rb') as f:
        w, h, px = decode_png(f.read())
    return mosaic(px, w, h, n)
