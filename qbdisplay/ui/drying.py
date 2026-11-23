# qbdisplay – Box-Trocknung (Profil wählen / läuft)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Entwurf 8 und 9. Start/Stopp über ENABLE_BOX_DRY TEMP= TIME= (Minuten) und
DISABLE_BOX_DRY (qidi_box_compat.cfg -> MMU_HEATER). Restzeit merkt sich
:class:`qbdisplay.model.DryingTracker`."""

import math

from .. import colors
from .. import fonts as F
from .. import model
from ..i18n import _, N_
from ..canvas import Rect
from . import widgets as W
from .chrome import Page


class DryingPage(Page):
    section = 'filament'
    title = N_('Trocknung')

    def build_content(self, frame):
        dv = self.ctx.drying
        if dv.active and not self.ctx.ui.get('dry_edit'):
            self.build_running(frame, dv)
        else:
            self.build_select(frame)

    # ------------------------------------------------------------------
    def build_select(self, frame):
        ctx = self.ctx
        profiles = ctx.profiles
        sel = ctx.dry_selection()
        temp, target, hum, heating = ctx.climate
        mats = [s.material for s in ctx.slots if s.state != 'empty' and s.material]
        level, rating = model.humidity_rating(hum, mats)
        hfg = {'ok': 'ok', 'warn': 'warn', 'err': 'err'}.get(level, 'text')

        clim = Rect(100, 52, 420, 140)

        half = (clim.w - 32) // 2
        cols = (('therm', _('Box-Temperatur'), model.fmt_temp(temp), ' °C', 'text',
                 _('Heizung an') if heating else _('Heizung aus')),
                ('drop', _('Luftfeuchte'), model.fmt_temp(hum), ' %', hfg,
                 rating if hum is not None else _('kein Sensorwert')))

        def paint_clim(c, r):
            W.tile(c, r)
            for k, (icon, label, _v, _u, fg, _c) in enumerate(cols):
                x = r.x + 16 + k * (half + 12)
                if k:
                    c.fill(x - 10, r.y + 16, 1, r.h - 32, 'line')
                W.header(c, r, icon, label, x=x, y=r.y + 12,
                         icon_fg=(fg if fg != 'text' else 'accent') if k else 'accent')
        frame.region('clim', clim, hfg, paint_clim)
        # Messwerte und Zeile darunter einzeln: nur sie ändern sich laufend
        for k, (_i, _l, val, unit, fg, capt) in enumerate(cols):
            x = clim.x + 16 + k * (half + 12)

            def paint_v(c, r, val=val, unit=unit, fg=fg):
                W.value_unit(c, r.x, r.y, 64, val, unit, F.HUGE, F.BTN, fg, 'surface')
            frame.region('clim.v%d' % k, Rect(x, clim.y + 42, half - 8, 64), (val, fg), paint_v,
                         clear='surface', gaps=True)
            cfg_ = 'warn' if (k and fg in ('warn', 'err')) else 'text3'

            def paint_c(c, r, capt=capt, cfg_=cfg_):
                c.text(r.x, r.y, r.w, r.h, capt, F.CAP, cfg_, 'surface')
            frame.region('clim.c%d' % k, Rect(x, clim.y + 110, half - 8, 18), (capt, cfg_),
                         paint_c, clear='surface', gaps=True)

        def paint_cap(c, r):
            c.fill_rect(r, 'bg')
            W.caption(c, r.x, r.y, _('Profil'), 'bg')
        frame.region('cap', Rect(100, 204, 200, 18), 0, paint_cap, opaque=True)
        n = max(1, len(profiles))
        pw = (420 - 8 * (n - 1)) // n
        for i, (name, ptemp, hours, types) in enumerate(profiles):
            rect = Rect(100 + i * (pw + 8), 226, pw, 76)
            on = i == sel['profile']
            tid = 'prof.%d' % i
            pr = ctx.pressed == tid
            sub = '%d °C · %d h' % (ptemp, hours)

            def paint(c, r, name=name, sub=sub, on=on, pr=pr):
                W.button(c, r, name, 'selected' if on else 'secondary', None, 'bg', sub=sub,
                         pressed=pr)
            frame.region(tid, rect, (name, sub, on, pr), paint)
            frame.target(tid, rect, (lambda i=i: ctx.dry_set_profile(i)))

        idx, why = model.suggest_profile(profiles, mats)
        if why:
            others = sorted(set(model.base_type(m) for m in mats))
            which = [s.letter for s in ctx.slots
                     if s.state != 'empty' and model.base_type(s.material) == why]
            hint = (_('Vorschlag aus der Belegung: Slot %s enthält %s.') if len(which) == 1
                    else _('Vorschlag aus der Belegung: Slot %s enthalten %s.')) % (
                ', '.join(which), why)
            if len(others) > 1:
                hint += ' ' + _('Bei gemischter Belegung gilt das Profil mit der niedrigsten '
                                'Temperatur.')
            hint += ' ' + _('Spulen bleiben in der Box.')
        else:
            hint = _('Keine Slot-Belegung bekannt. Profil passend zum Material wählen.') + \
                ' ' + _('Spulen bleiben in der Box.')
        info = Rect(100, 314, 420, 154)

        def paint_info(c, r):
            W.tile(c, r)
            lines = F.wrap(hint, F.TEXT, r.w - 68, 5)
            y = r.y + (r.h - 23 * len(lines)) // 2
            c.icon('info', r.x + 16, r.cy - 12, 24, 'info', 'surface')
            W.text_lines(c, r.x + 52, y, r.w - 68, lines, F.TEXT, 'text2', 'surface')
        frame.region('hint', info, hint, paint_info)

        # rechte Spalte
        right = Rect(532, 52, 252, 416)

        def paint_right(c, r):
            W.tile(c, r)
            W.header(c, r, 'sun', _('Einstellung'), x=r.x + 14, y=r.y + 12, icon_fg='heat')
            W.caption(c, r.x + 14, r.y + 48, _('Temperatur'), 'surface')
            W.caption(c, r.x + 14, r.y + 140, _('Dauer'), 'surface')
            c.fill(r.x + 14, r.y + 224, r.w - 28, 1, 'line')
            W.caption(c, r.x + 14, r.y + 239, _('Fertig ca.'), 'surface')
        frame.region('right', right, 0, paint_right)
        maxt = ctx.cfg.getint('box', 'dry_max_temp')
        rows = [('t', right.y + 70, '%d °C' % sel['temp'],
                 lambda: ctx.dry_adjust(temp=-5), lambda: ctx.dry_adjust(temp=+5),
                 sel['temp'] > 35, sel['temp'] < maxt),
                ('h', right.y + 162, '%d:00 h' % sel['hours'],
                 lambda: ctx.dry_adjust(hours=-1), lambda: ctx.dry_adjust(hours=+1),
                 sel['hours'] > 1, sel['hours'] < 48)]
        for key, y, val, dec, inc, can_dec, can_inc in rows:
            for sign, x, act, ok in (('-', right.x + 14, dec, can_dec),
                                     ('+', right.x2 - 14 - 56, inc, can_inc)):
                rr = Rect(x, y, 56, 56)
                tid = 'adj.%s%s' % (key, sign)
                pr = ctx.pressed == tid

                def paint_pm(c, r, sign=sign, ok=ok, pr=pr):
                    W.plus_minus(c, r, sign, 'surface', pressed=pr, enabled=ok)
                frame.region(tid, rr, (ok, pr), paint_pm, clear='surface')
                if ok:
                    frame.target(tid, rr, act)

            def paint_val(c, r, val=val):
                c.text(r.x, r.y, r.w, r.h, val, F.VAL, 'text', 'surface', 'center')
            frame.region('val.' + key, Rect(right.x + 74, y + 12, right.w - 148, 32), val,
                         paint_val, clear='surface', gaps=True)
        eta = model.fmt_clock(ctx.now + sel['hours'] * 3600, ctx.now)

        def paint_eta(c, r):
            c.label_right(r.x2, r.y, eta, F.BTN, 'text', 'surface', h=24)
        frame.region('eta', Rect(right.x + 100, right.y + 232, right.w - 114, 24), eta, paint_eta,
                     clear='surface', gaps=True)
        st = Rect(right.x + 14, right.y2 - 14 - 64, right.w - 28, 64)
        pr = ctx.pressed == 'start'
        label = _('Übernehmen') if ctx.drying.active else _('Trocknen starten')

        def paint_start(c, r):
            W.button(c, r, label, 'primary', 'sun' if not ctx.drying.active else 'check',
                     'surface', pressed=pr)
        frame.region('start', st, (label, pr), paint_start, clear='surface')
        frame.target('start', st, ctx.dry_start)

    # ------------------------------------------------------------------
    def build_running(self, frame, dv):
        ctx = self.ctx
        big = Rect(100, 52, 424, 340)
        prof = dv.profile or _('Manuell')
        target = int(round(dv.target or 0))
        total_h = ''
        if dv.known:
            total_h = ' · %d h' % int(round((dv.end - dv.start) / 3600.0))
        rem = model.fmt_duration(dv.remaining, 'clock') if dv.known else '?'
        pct = int(round(dv.frac * 100)) if dv.known else None

        def paint_big(c, r):
            W.tile(c, r, glow='accent')
            W.header(c, r, 'sun', _('Trocknung läuft'), x=r.x + 18, y=r.y + 16, icon_fg='heat',
                     fg='text')
        frame.region('big', big, 0, paint_big)
        ring = Rect(big.x + 18, big.y + 62, 204, 204)

        def paint_ring(c, r):
            frac = dv.frac if dv.known else 0.0
            c.circle(r.cx, r.cy, 97, 'line')
            c.arc_progress(r.cx, r.cy, 92, 14, frac, 'accent', 'surface3', 'surface')
            if frac > 0:
                a = math.radians(-90 + 360.0 * min(1.0, frac))
                kx, ky = r.cx + 85 * math.cos(a), r.cy + 85 * math.sin(a)
                c.disc(kx, ky, 12, colors.mix('surface', 'accent', 0.35))
                c.disc(kx, ky, 10, 'accent')
                c.disc(kx, ky, 4, 'white')
        frame.region('ring', ring, pct, paint_ring, clear='surface')

        def paint_rem(c, r):
            c.text(r.x, r.y, r.w, 40, rem, F.BIG, 'text', 'surface', 'center')
            c.text(r.x, r.y + 44, r.w, 20,
                   (_('übrig · %d %%') % pct) if pct is not None else _('Restzeit unbekannt'),
                   F.LBL, 'text2', 'surface', 'center')
        frame.region('ring.t', Rect(ring.cx - 64, ring.cy - 34, 128, 64), (rem, pct), paint_rem,
                     clear='surface', gaps=True)
        since = model.fmt_duration(ctx.now - dv.start, 'clock') if dv.known else '–'
        start_s = model.fmt_clock(dv.start, ctx.now) if dv.known else ''
        end_s = model.fmt_clock(dv.end, ctx.now) if dv.known else '–'
        info = Rect(big.x + 236, big.y + 70, big.w - 236 - 16, 210)

        def paint_info(c, r):
            c.text(r.x, r.y, r.w, 18, W.caps(_('Profil')), F.CAP, 'text3', 'surface')
            x = c.label(r.x, r.y + 20, prof, F.BTN, 'text', 'surface', h=26)
            c.label(x + 6, r.y + 24, '%d °C%s' % (target, total_h), F.LBL, 'text2',
                    'surface', max_w=r.x2 - x - 6)
            c.fill(r.x, r.y + 58, r.w, 1, 'line')
            c.text(r.x, r.y + 70, r.w, 18, W.caps(_('Läuft seit')), F.CAP, 'text3', 'surface')
            x = c.label(r.x, r.y + 90, since, F.BTN, 'text', 'surface', h=26)
            if start_s:
                c.label(x + 6, r.y + 94, _('(Start %s)') % start_s, F.LBL, 'text3', 'surface',
                        max_w=r.x2 - x - 6)
            c.fill(r.x, r.y + 128, r.w, 1, 'line')
            c.text(r.x, r.y + 140, r.w, 18, W.caps(_('Fertig ca.')), F.CAP, 'text3', 'surface')
            c.text(r.x, r.y + 160, r.w, 26, end_s, F.BTN, 'text', 'surface')
        frame.region('info', info, (prof, target, total_h, since, start_s, end_s), paint_info,
                     clear='surface', gaps=True)

        btns = [('plus1', '+ 1 h', None, 'secondary', ctx.dry_extend),
                ('change', _('Ändern'), 'sliders', 'secondary', ctx.dry_change),
                ('abort', _('Abbrechen'), 'stop', 'danger', ctx.confirm_dry_stop)]
        widths = (112, 136, 160)
        x = 100
        for i, (tid, label, icon, kind, act) in enumerate(btns):
            rr = Rect(x, 404, widths[i], 64)
            x += widths[i] + 8
            pr = ctx.pressed == tid

            def paint_b(c, r, label=label, icon=icon, kind=kind, pr=pr):
                W.button(c, r, label, kind, icon, 'bg', pressed=pr)
            frame.region('b.' + tid, rr, (label, pr), paint_b)
            frame.target(tid, rr, act)

        # rechte Spalte: Temperatur und Feuchte
        t_rect = Rect(536, 52, 248, 202)
        h_rect = Rect(536, 266, 248, 202)
        temp = model.fmt_temp(dv.temp)

        def paint_t(c, r):
            W.tile(c, r)
            W.header(c, r, 'therm', _('Box-Temperatur'), icon_fg='heat')
            c.text(r.x + 16, r.y2 - 34, r.w - 32, 18, _('Heizung an · Lüfter an'), F.CAP,
                   'text3', 'surface')
        frame.region('t', t_rect, 0, paint_t)

        def paint_tv(c, r):
            W.value_unit(c, r.x, r.y, 64, temp, '/ %d °C' % target, F.HUGE, F.BTN,
                         'text', 'surface', gap=6)
        frame.region('t.v', Rect(t_rect.x + 16, t_rect.y + 70, t_rect.w - 32, 64),
                     (temp, target), paint_tv, clear='surface', gaps=True)
        hum = dv.humidity
        mats = [s.material for s in ctx.slots if s.state != 'empty' and s.material]
        level, _r = model.humidity_rating(hum, mats)
        hfg = {'ok': 'ok', 'warn': 'warn', 'err': 'err'}.get(level, 'text')
        delta = None
        if hum is not None and dv.hum_start is not None:
            delta = int(round(hum - dv.hum_start))

        hs = dv.hum_start

        def paint_h(c, r):
            W.tile(c, r)
            W.header(c, r, 'drop', _('Luftfeuchte'), icon_fg=hfg if hfg != 'text' else 'accent')
            c.text(r.x + 16, r.y2 - 34, r.w - 32, 18,
                   (_('beim Start %d %%') % int(round(hs))) if hs is not None
                   else _('Startwert unbekannt'), F.CAP, 'text3', 'surface')
        frame.region('h', h_rect, (hfg, hs), paint_h)
        htxt = model.fmt_temp(hum)

        def paint_hv(c, r):
            W.value_unit(c, r.x, r.y, 64, htxt, '%', F.HUGE, F.BTN, hfg, 'surface', gap=4)
        frame.region('h.v', Rect(h_rect.x + 16, h_rect.y + 70, 120, 64), (htxt, hfg), paint_hv,
                     clear='surface', gaps=True)

        def paint_hd(c, r):
            if delta is not None and delta != 0:
                W.chip(c, r.x2, r.y + 2, '%+d %%' % delta,
                       'ready' if delta < 0 else 'warn', 'surface',
                       icon='down' if delta < 0 else 'up', right=True)
        frame.region('h.d', Rect(h_rect.x2 - 16 - 96, h_rect.y + 96, 96, 32), delta, paint_hd,
                     clear='surface')
