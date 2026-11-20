# qbdisplay – Dateien
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""G-Code-Dateien (neueste zuerst), Antippen -> Druck starten (mit Rückfrage)."""

import time

from .. import fonts as F
from .. import model
from ..i18n import _, N_, decimal
from ..canvas import Rect
from . import widgets as W
from .chrome import Page

PER_PAGE = 5


def fmt_size(n):
    n = float(n or 0)
    if n >= 1024 * 1024:
        return decimal('%.1f MB' % (n / 1048576.0))
    return '%d KB' % max(1, int(n / 1024))


class FilesPage(Page):
    section = 'files'
    title = N_('Dateien')

    def build_content(self, frame):
        ctx = self.ctx
        files = ctx.files or []
        pages = max(1, (len(files) + PER_PAGE - 1) // PER_PAGE)
        page = min(ctx.ui.get('files_page', 0), pages - 1)
        busy = ctx.pstate in ('printing', 'paused', 'paused_error')
        head = _('%d Dateien · neueste zuerst') % len(files) if files else \
            _('Keine Dateien gefunden')
        if busy:
            head += ' · ' + _('Druck läuft (Start gesperrt)')

        def paint_head(c, r):
            c.fill_rect(r, 'bg')
            W.caption(c, r.x, r.y + 1, head, 'bg', w=r.w)
        frame.region('head', Rect(100, 56, 608, 20), head, paint_head, opaque=True)
        for i in range(PER_PAGE):
            k = page * PER_PAGE + i
            rect = Rect(100, 88 + i * 76, 608, 68)
            tid = 'row.%d' % i
            if k >= len(files):
                frame.region(tid, rect, None, lambda c, r: None)
                continue
            f = files[k]
            meta = ctx.file_meta(f['path'])
            sub = [time.strftime(_('%d.%m. %H:%M'), time.localtime(f.get('modified', 0))),
                   fmt_size(f.get('size'))]
            if meta.get('estimated_time'):
                sub.append(model.fmt_duration(meta['estimated_time']))
            if meta.get('filament_colors'):
                n = len(meta['filament_colors'])
                sub.append((_('%d Farbe') if n == 1 else _('%d Farben')) % n)
            subtxt = ' · '.join(sub)
            pr = ctx.pressed == tid
            cols = tuple(meta.get('filament_colors') or [])[:6]

            def paint(c, r, name=f['path'], subtxt=subtxt, pr=pr, cols=cols):
                face = 'tint' if pr else 'surface'
                if pr:
                    W.glow_box(c, r, 14, face, 'accent', 'bg', halo=2, bw=1, inner=False)
                else:
                    W.tile(c, r)
                ib = Rect(r.x + 12, r.y + 12, 44, 44)
                c.rr(ib, 10, 'surface2')
                c.icon('layers', ib.cx - 12, ib.cy - 12, 24, 'accent', 'surface2')
                tx = ib.x2 + 14
                c.text(tx, r.y + 10, r.x2 - 150 - tx, 26, model.short_filename(name), F.BTN,
                       'text', face)
                c.text(tx, r.y + 40, r.x2 - 150 - tx, 18, subtxt, F.CAP, 'text3', face)
                x = r.x2 - 16 - 10
                for col in reversed(cols):
                    W.color_dot(c, x, r.cy, 9, col, face)
                    x -= 26
            frame.region(tid, rect, (f['path'], subtxt, pr, cols), paint)
            if not busy:
                frame.target(tid, rect, (lambda p=f['path']: ctx.confirm_print(p)))
        # Blättern
        for tid, y, icon, ok, delta in (('pg.up', 88, 'chevup', page > 0, -1),
                                         ('pg.dn', 392, 'chevdown', page < pages - 1, 1)):
            rr = Rect(720, y, 64, 64)
            pr = ctx.pressed == tid

            def paint_p(c, r, icon=icon, ok=ok, pr=pr):
                if ok:
                    W.button(c, r, '', 'secondary', icon, 'bg', pressed=pr)
                else:
                    W.button(c, r, '', 'disabled', None, 'bg')
                    c.icon(icon, r.cx - 12, r.cy - 12, 24, 'text3', 'surface')
            frame.region(tid, rr, (ok, pr), paint_p)
            if ok:
                frame.target(tid, rr, (lambda d=delta: ctx.set_ui(files_page=page + d)))
        ptxt = '%d / %d' % (page + 1, pages)

        def paint_pt(c, r):
            c.fill_rect(r, 'bg')
            c.text(r.x, r.y, r.w, 18, W.caps(_('Seite')), F.CAP, 'text3', 'bg', 'center')
            c.text(r.x, r.y + 20, r.w, 30, ptxt, F.BTN, 'text', 'bg', 'center')
            # Bildlaufleiste: Spur + leuchtender Anzeiger der aktuellen Seite
            tr = Rect(r.cx - 2, r.y + 62, 4, r.h - 66)
            c.rr(tr, 2, 'surface3')
            seg_h = max(16, tr.h // pages)
            y = tr.y + (tr.h - seg_h) * page // max(1, pages - 1)
            c.rr(Rect(tr.x - 1, y, 6, seg_h), 3, 'accent')
        frame.region('pgtxt', Rect(720, 168, 64, 210), (ptxt, page, pages), paint_pt,
                     opaque=True)
