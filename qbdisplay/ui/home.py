# qbdisplay – Startseite (Leerlauf und Druck)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Entwurf 1 (Leerlauf) und 2 (Druck läuft, Farbwechsel aktiv).

Gestaltungsregel: Was gerade *lebt* (laufender Druck, laufender
Farbwechsel), bekommt einen leuchtenden Rahmen – Cyan für den Druck,
Violett für Box-Vorgänge, Bernstein für Pause, Rot für Fehler-Pause.
"""

from .. import colors
from .. import fonts as F
from .. import model
from ..i18n import _, N_
from ..canvas import Rect
from . import widgets as W
from .chrome import Page

HEATERS = [
    ('extruder', 'nozzle', N_('Düse')),
    ('heater_bed', 'bed', N_('Bett')),
    ('chamber', 'chamber', N_('Kammer')),
]


def paint_thumb(c, r, mosaic, under='surface'):
    """Vorschaubild als Mosaik aus Füllflächen (Lauflängen je Zeile)."""
    c.rr(r, 12, 'surface2')
    if not mosaic:
        c.icon('layers', r.cx - 15, r.cy - 15, 30, 'text3', 'surface2')
        return
    n = len(mosaic)
    block = min(r.w, r.h) // n
    ox = r.x + (r.w - block * n) // 2
    oy = r.y + (r.h - block * n) // 2
    for yi, row in enumerate(mosaic):
        xi = 0
        while xi < len(row):
            col = row[xi]
            run = 1
            while xi + run < len(row) and row[xi + run] == col:
                run += 1
            if col:
                c.fill(ox + xi * block, oy + yi * block, run * block, block, col)
            xi += run


def mini_spool(c, cx, cy, r, color, active, under):
    """Kleine Spule für Übersichten (3–5 Zeichenbefehle)."""
    if not color:
        c.dashed_circle(cx, cy, r - 1, 'text3', width=2, dashes=8)
        return
    if active:
        c.disc(cx, cy, r + 3, colors.mix(under, 'accent', 0.3))
        c.disc(cx, cy, r, 'accent')
        c.disc(cx, cy, r - 3, color)
    else:
        c.disc(cx, cy, r, colors.ring_on(under))
        c.disc(cx, cy, r - 2, color)
    c.disc(cx, cy, max(3, r // 3), 'surface3')


class HomePage(Page):
    section = 'home'

    def page_title(self):
        return self.ctx.cfg.get('printer', 'name')

    def build_content(self, frame):
        if self.ctx.pstate in ('printing', 'paused', 'paused_error'):
            self.build_print(frame)
        else:
            self.build_idle(frame)

    # ------------------------------------------------------------------
    def heater_obj(self, key):
        return self.ctx.cfg.get('printer', 'chamber') if key == 'chamber' else key

    def build_idle(self, frame):
        ctx = self.ctx
        st = ctx.st
        # --- Temperaturkacheln -------------------------------------------
        for i, (key, icon, label) in enumerate(HEATERS):
            rect = Rect(100 + i * 232, 52, 220, 128)
            obj = self.heater_obj(key)
            temp = st.get(obj, 'temperature')
            target = st.get(obj, 'target', 0) or 0
            tid = 'temp.' + key
            pressed = ctx.pressed == tid
            heating = target > 0

            def paint_tile(c, r, icon=icon, label=label, pressed=pressed, heating=heating):
                W.tile(c, r, border='accent' if pressed else 'line', bw=2 if pressed else 1)
                W.header(c, r, icon, _(label), icon_fg='heat' if heating else 'accent')
            frame.region(tid, rect, ('tile', label, pressed, heating), paint_tile)
            vtxt = model.fmt_temp(temp)

            def paint_val(c, r, vtxt=vtxt):
                W.value_unit(c, r.x, r.y, 64, vtxt, '°C', F.HUGE, F.BTN, 'text', 'surface')
            frame.region(tid + '.v', Rect(rect.x + 16, rect.y + 48, 120, 64), vtxt, paint_val,
                         clear='surface')

            def paint_chip(c, r, heating=heating, target=target):
                if heating:
                    W.chip(c, r.x2, r.y, _('Soll %d°') % target, 'heat', 'surface', right=True)
                else:
                    W.chip(c, r.x2, r.y, _('aus'), 'off', 'surface', right=True)
            frame.region(tid + '.c', Rect(rect.x2 - 16 - 84, rect.y + 14, 84, 26),
                         (heating, target), paint_chip, clear='surface')
            frac = 0.0
            if heating and temp is not None:
                frac = max(0.0, min(1.0, float(temp) / float(target)))

            def paint_heat(c, r, frac=frac, heating=heating):
                if heating:
                    W.bar(c, r, frac, 'heat', 'surface3')
            frame.region(tid + '.h', Rect(rect.x + 16, rect.y2 - 16, rect.w - 32, 6),
                         (heating, int(frac * 40)), paint_heat, clear='surface')
            frame.target(tid, rect, (lambda k=key: ctx.open_temp(k)))

        # --- Zuletzt gedruckt --------------------------------------------
        last = ctx.last_print or {}
        fname = last.get('filename') or ''
        tile = Rect(100, 192, 436, 276)
        meta = last.get('metadata') or {}
        layers = meta.get('layer_count')
        fcolors = [col for col in (meta.get('filament_colors') or []) if col][:8]
        tools = last.get('tools') or []
        mosaic = ctx.thumb(fname, 164) if fname else None

        def paint_last(c, r):
            W.tile(c, r)
            paint_thumb(c, Rect(r.x + 14, r.y + 14, 164, 164), mosaic)
            x = r.x + 14 + 164 + 18
            w = r.x2 - 16 - x
            if not fname:
                W.caption(c, x, r.y + 18, _('Noch nichts gedruckt'), 'surface')
                return
            W.caption(c, x, r.y + 16, _('Zuletzt gedruckt'), 'surface')
            c.text(x, r.y + 40, w, 32, model.short_filename(fname), F.VAL, 'text', 'surface')
            info = []
            if layers:
                info.append(_('%d Schichten') % int(layers))
            if fcolors:
                info.append((_('%d Farbe') if len(fcolors) == 1 else _('%d Farben')) % len(fcolors))
            yy = r.y + 80
            if info:
                W.icon_text(c, x, yy, 24, 'layers', ' · '.join(info), 'text2',
                            'surface', fid=F.LBL, max_w=w - 30)
            status = last.get('status')
            if status and status != 'completed':
                W.chip(c, x, yy + 34, {'cancelled': _('abgebrochen'), 'error': _('Fehler'),
                                       'klippy_shutdown': _('Abbruch')}.get(status, status),
                       'err', 'surface')
            elif status == 'completed':
                W.chip(c, x, yy + 34, _('fertig'), 'ready', 'surface', icon='check')
            if fcolors:
                cx = x + 13
                cy = r.y + 162
                for col in fcolors:
                    W.color_dot(c, cx, cy, 11, col, 'surface')
                    cx += 30
                if tools:
                    c.text(cx - 4, cy - 10, r.x2 - cx - 10, 20, ' + '.join(tools), F.CAP,
                           'text3', 'surface')
        frame.region('last', tile, (fname, layers, tuple(fcolors), tuple(tools),
                                    last.get('status'), mosaic is not None), paint_last)
        if fname:
            br = Rect(tile.x + 14, tile.y2 - 14 - 64, tile.w - 28 - 72, 64)
            pressed = ctx.pressed == 'reprint'

            def paint_reprint(c, r, pressed=pressed):
                W.button(c, r, _('Erneut drucken'), 'primary', 'retry', 'surface', pressed=pressed)
            frame.region('reprint', br, pressed, paint_reprint, clear='surface')
            frame.target('reprint', br, (lambda: ctx.confirm_print(fname)))
        fr = Rect(tile.x2 - 14 - 64, tile.y2 - 14 - 64, 64, 64)
        pressed = ctx.pressed == 'files'

        def paint_files(c, r, pressed=pressed):
            W.button(c, r, '', 'secondary', 'folder', 'surface', pressed=pressed)
        frame.region('filesbtn', fr, pressed, paint_files, clear='surface')
        frame.target('files', fr, (lambda: ctx.go('files')))

        # --- Filament-Kurzstatus -----------------------------------------
        fil = Rect(548, 192, 236, 200)
        slots = ctx.slots
        lg = ctx.loaded_gate
        has_box = ctx.has_box
        rack = ctx.rack
        key = (has_box, tuple(rack)) + tuple((s.state, s.color) for s in slots) + (
            lg, ctx.climate[0] is None and -1 or
                                                          int(round(ctx.climate[0])),
                                                          ctx.climate[2] is None and -1 or
                                                          int(round(ctx.climate[2])))
        pressed = ctx.pressed == 'filtile'

        def paint_fil(c, r, pressed=pressed):
            W.tile(c, r, border='accent' if pressed else 'line', bw=2 if pressed else 1)
            W.header(c, r, 'spool', _('Filament'), x=r.x + 14)
            c.icon('chev', r.x2 - 14 - 20, r.y + 15, 20, 'text3', 'surface')
            n = len(slots)
            if not has_box:
                # ohne Box: die externe Spule
                act = lg == model.HH_GATE_BYPASS
                mini_spool(c, r.x + 14 + 22, r.y + 74, 20, rack.color, act, 'surface')
                c.text(r.x + 72, r.y + 56, r.w - 86, 22, rack.name, F.BTN, 'text', 'surface')
                c.text(r.x + 72, r.y + 82, r.w - 86, 18, _('Externe Spule'), F.CAP, 'text3',
                       'surface')
            span = r.w - 28 - 36
            rad = 16 if n <= 4 else max(7, span // max(1, n - 1) // 2 - 1)
            for i, s in enumerate(slots):
                cx = r.x + 14 + 18 + (span * i // max(1, n - 1))
                cy = r.y + 70
                act = lg == s.index
                empty = s.state in ('empty', 'unknown') or not s.color
                mini_spool(c, cx, cy, rad, None if empty else s.color, act, 'surface')
                fg = 'accent' if act else ('text3' if s.state == 'empty' else 'text2')
                c.text(cx - 15, cy + 23, 30, 18, s.letter, F.LBL if n <= 4 else F.CAP, fg,
                       'surface', 'center')
            c.fill(r.x + 14, r.y + 122, r.w - 28, 1, 'line')
            c.text(r.x + 14, r.y + 132, r.w - 28, 18, W.caps(_('In der Düse')), F.CAP, 'text3',
                   'surface')
            if lg is not None and lg >= 0 and lg < n:
                s = slots[lg]
                txt = '%s · %s' % (s.letter, s.name or s.material or '?')
            elif lg == model.HH_GATE_BYPASS:
                txt = _('Rack (extern)') if not rack.material else _('Extern · %s') % rack.name
            else:
                txt = _('leer')
            c.text(r.x + 14, r.y + 150, r.w - 28, 22, txt, F.LBL, 'text', 'surface')
            if has_box:
                t, _t, h, heating = ctx.climate
                c.text(r.x + 14, r.y + 174, r.w - 28, 18, _('Box %s °C · %s %% rF') % (
                    model.fmt_temp(t), model.fmt_temp(h)), F.CAP, 'text3', 'surface')
            else:
                c.text(r.x + 14, r.y + 174, r.w - 28, 18, _('Keine QIDI Box verbunden'), F.CAP,
                       'text3', 'surface')
        frame.region('filtile', fil, key + (pressed,), paint_fil)
        frame.target('filtile', fil, (lambda: ctx.go('filament')))

        # --- Licht ---------------------------------------------------------
        lr = Rect(548, 404, 236, 64)
        light = bool(st.get('output_pin ' + ctx.cfg.get('printer', 'light_pin'), 'value', 0))

        def paint_light(c, r):
            W.tile(c, r)
            c.icon('light', r.x + 14, r.cy - 12, 24, 'warn' if light else 'text3', 'surface')
            c.text(r.x + 48, r.cy - 9, 100, 18, W.caps(_('Licht')), F.LBL,
                   'text' if light else 'text2', 'surface')
            W.toggle(c, r.x2 - 12 - 72, r.cy - 20, light, 'surface')
        frame.region('light', lr, light, paint_light)
        frame.target('light', lr, ctx.toggle_light)

    # ------------------------------------------------------------------
    def build_print(self, frame):
        ctx = self.ctx
        st = ctx.st
        pv = model.print_view(st, (ctx.current_meta or {}), ctx.now)
        top = Rect(100, 52, 684, 152)
        mosaic = ctx.thumb(pv.filename, 128) if pv.filename else None
        tc = ctx.toolchange
        live = {'printing': 'accent', 'paused': 'warn', 'paused_error': 'err'}.get(ctx.pstate)
        if tc.active and ctx.pstate == 'printing':
            live = None      # der Farbwechsel ist gerade das Wichtigste
        pct_fg = {'paused': 'warn', 'paused_error': 'err'}.get(ctx.pstate, 'accent')

        def paint_top(c, r):
            W.tile(c, r, glow=live)
            paint_thumb(c, Rect(r.x + 12, r.y + 12, 128, 128), mosaic)
        frame.region('ptop', top, (pv.filename, mosaic is not None, live), paint_top)
        x0 = top.x + 12 + 128 + 18
        w0 = top.x2 - 18 - x0
        pct = int(pv.progress * 100)

        def paint_name(c, r):
            c.text(r.x, r.y, r.w - 110, 32, model.short_filename(pv.filename), F.VAL, 'text',
                   'surface')
            c.label_right(r.x2, r.y - 6, '%d %%' % pct, F.BIG, pct_fg, 'surface')
            W.bar(c, Rect(r.x, r.y + 44, r.w, 8), pv.progress, pct_fg, knob=True)
        frame.region('pname', Rect(x0, top.y + 14, w0, 58), (pv.filename, pct, pct_fg,
                                                             int(pv.progress * 500)),
                     paint_name, clear='surface')
        cols = [(_('Schicht'), ('%s' % (pv.layer if pv.layer is not None else '–'),
                             '/ %s' % pv.total_layers if pv.total_layers else '')),
                (_('Restzeit'), (model.fmt_duration(pv.remaining), '')),
                (_('Fertig ca.'), (model.fmt_clock(pv.eta, ctx.now), ''))]
        cw = (w0 - 20) // 3
        for i, (cap, (val, extra)) in enumerate(cols):
            rr = Rect(x0 + i * (cw + 10), top.y + 80, cw, 60)

            def paint_stat(c, r, cap=cap, val=val, extra=extra, i=i):
                if i:
                    c.fill(r.x - 6, r.y + 4, 1, r.h - 8, 'line')
                c.text(r.x + (6 if i else 0), r.y, r.w, 18, W.caps(cap), F.CAP, 'text3',
                       'surface')
                x = c.label(r.x + (6 if i else 0), r.y + 22, val, F.VAL, 'text', 'surface',
                            max_w=r.w - 6)
                if extra:
                    c.label(x + 4, r.y + 22, extra, F.VAL, 'text3', 'surface', max_w=r.x2 - x - 4)
            frame.region('pstat%d' % i, rr, (val, extra), paint_stat, clear='surface')

        # --- Farbwechsel-Panel --------------------------------------------
        panel = Rect(100, 216, 684, 128)
        slots = ctx.slots
        if tc.active:
            self.build_toolchange(frame, panel, tc, slots)
        else:
            self.build_filament_panel(frame, panel, slots)

        # --- untere Leiste ------------------------------------------------
        x = 100
        for i, (key, icon, label) in enumerate(HEATERS):
            rect = Rect(x, 356, 120, 112)
            x += 128
            obj = self.heater_obj(key)
            temp = st.get(obj, 'temperature')
            target = st.get(obj, 'target', 0) or 0
            tid = 'ptemp.' + key
            pressed = ctx.pressed == tid

            def paint_t(c, r, icon=icon, label=label, temp=temp, target=target, pressed=pressed):
                W.tile(c, r, border='accent' if pressed else 'line', bw=2 if pressed else 1)
                c.icon(icon, r.x + 12, r.y + 12, 18, 'heat' if target > 0 else 'accent',
                       'surface')
                c.text(r.x + 36, r.y + 12, r.w - 44, 18, W.caps(_(label)), F.CAP, 'text2',
                       'surface')
                xx = c.label(r.x + 12, r.y + 42, model.fmt_temp(temp), F.VAL, 'text', 'surface')
                unit = (' / %d°' % target) if target > 0 else ' °C'
                c.label(xx, r.y + 51, unit, F.LBL, 'text3', 'surface', max_w=r.x2 - xx - 6)
                if target > 0 and temp is not None:
                    W.bar(c, Rect(r.x + 12, r.y2 - 16, r.w - 24, 4),
                          max(0.0, min(1.0, float(temp) / float(target))), 'heat')
            frame.region(tid, rect, (model.fmt_temp(temp), target, pressed), paint_t)
            frame.target(tid, rect, (lambda k=key: ctx.open_temp(k)))
        paused = ctx.pstate in ('paused', 'paused_error')
        btns = [
            ('pause', Rect(484, 356, 88, 112), _('Weiter') if paused else _('Pause'),
             'play' if paused else 'pause', 'primary' if paused else 'secondary',
             ctx.resume if paused else ctx.pause),
            ('tune', Rect(580, 356, 96, 112), _('Anpassen'), 'sliders', 'secondary', ctx.open_tune),
            ('cancel', Rect(684, 356, 100, 112), _('Abbrechen'), 'stop', 'danger', ctx.confirm_cancel),
        ]
        for tid, rect, label, icon, kind, action in btns:
            pressed = ctx.pressed == tid

            def paint_b(c, r, label=label, icon=icon, kind=kind, pressed=pressed):
                W.button(c, r, label, kind, icon, 'bg', fid=F.LBL, pressed=pressed, stack=True,
                         isize=28)
            frame.region('b.' + tid, rect, (label, kind, pressed), paint_b)
            frame.target(tid, rect, action)

    def build_toolchange(self, frame, panel, tc, slots):
        ctx = self.ctx

        def sl(g):
            if g is None:
                return None
            if g == model.HH_GATE_BYPASS:
                return model.rack_view(ctx.st)
            return slots[g] if 0 <= g < len(slots) else None
        src, dst = sl(tc.from_gate), sl(tc.to_gate)
        head = _('Farbwechsel %d von %d') % (tc.number, tc.total) if tc.total else \
            _('Farbwechsel %d') % tc.number
        remaining = model.fmt_duration(tc.remaining, 'ms')
        live = ctx.pstate == 'printing'

        def paint_panel(c, r):
            W.tile(c, r, border='info_line', glow='info' if live else None)
            c.icon('swap', r.x + 16, r.y + 13, 24, 'info', 'surface')
            x = c.label(r.x + 50, r.y + 13, head, F.BTN, 'text', 'surface', h=24)
            x += 14
            if src is not None:
                W.color_dot(c, x + 10, r.y + 25, 9, src.color or '#444C58', 'surface')
                x = c.label(x + 24, r.y + 16, src.letter, F.LBL, 'text2', 'surface')
            c.icon('right', x + 4, r.y + 16, 18, 'text2', 'surface')
            x += 26
            if dst is not None:
                W.color_dot(c, x + 10, r.y + 25, 9, dst.color or '#444C58', 'surface')
                c.label(x + 24, r.y + 16, '%s · %s' % (dst.letter, dst.name or dst.material),
                        F.LBL, 'text2', 'surface', max_w=r.x2 - 190 - x)
        frame.region('tc', panel, (head, src and src.letter, dst and dst.letter,
                                   dst and dst.name, live), paint_panel)

        def paint_rest(c, r):
            c.label_right(r.x2, r.y, _('noch ca. %s') % remaining, F.LBL, 'info', 'surface')
        frame.region('tc.rest', Rect(panel.x2 - 16 - 160, panel.y + 16, 160, 18), remaining,
                     paint_rest, clear='surface')
        names = [('cut', _('Schneiden')),
                 ('unload', _('%s entladen') % (src.letter if src else _('Alt'))),
                 ('load', _('%s laden') % (dst.letter if dst else _('Neu'))),
                 ('purge', _('Spülen')),
                 ('resume', _('Weiterdrucken'))]
        cur = model.PHASES.index(tc.phase)
        inner = panel.inset(16, 0)
        sw = (inner.w - 4 * 6) // 5
        for i, (ph, label) in enumerate(names):
            rect = Rect(inner.x + i * (sw + 6), panel.y + 50, sw, 36)
            st_ = 'done' if i < cur else ('now' if i == cur else 'next')
            if ph == 'purge' and st_ == 'now':
                label = _('Spülen %d %%') % int(tc.purge_frac * 100)

            def paint_step(c, r, label=label, st_=st_):
                if st_ == 'now':
                    c.rr(r, 10, colors.mix('surface', 'info', 0.4))
                    c.rr(r.inset(1), 9, 'info')
                    c.text(r.x + 4, r.cy - 9, r.w - 8, 18, label, F.LBL, 'on_info', 'info', 'center')
                elif st_ == 'done':
                    c.rr(r, 10, 'ok_bg')
                    tw = F.measure(label, F.LBL) + 22
                    x = r.cx - tw // 2
                    c.icon('check', x, r.cy - 8, 16, 'ok', 'ok_bg')
                    c.text(x + 22, r.cy - 9, r.x2 - x - 26, 18, label, F.LBL, 'ok', 'ok_bg')
                else:
                    c.dashed_box(r, 10, 'line', bw=1, dash=5, gap=4, fill='surface')
                    c.text(r.x + 4, r.cy - 9, r.w - 8, 18, label, F.LBL, 'text3', 'surface',
                           'center')
            frame.region('tc.s%d' % i, rect, (label, st_), paint_step, clear='surface')
        frac = tc.purge_frac if tc.phase == 'purge' else (cur / 4.0)

        def paint_bar(c, r):
            W.bar(c, r, frac, 'info', knob=True)
        frame.region('tc.bar', Rect(inner.x, panel.y + 100, inner.w, 8), int(frac * 100),
                     paint_bar, clear='surface')

    def build_filament_panel(self, frame, panel, slots):
        ctx = self.ctx
        lg = ctx.loaded_gate
        s = slots[lg] if lg is not None and 0 <= lg < len(slots) else None
        if lg == model.HH_GATE_BYPASS:
            s = ctx.rack
        mmu = ctx.st.mmu
        done = int(mmu.get('num_toolchanges') or 0)
        total = int((mmu.get('slicer_tool_map') or {}).get('total_toolchanges') or 0)
        line2 = (_('Farbwechsel: %d von %d erledigt') % (done, total)) if total else \
            (_('Farbwechsel bisher: %d') % done if done else _('Kein Farbwechsel geplant'))
        key = (lg, s and s.name, s and s.color, line2, tuple((x.state, x.color) for x in slots))

        def paint(c, r):
            W.tile(c, r)
            W.header(c, r, 'spool', _('Filament im Druck'))
            if s is not None:
                W.spool(c, r.x + 52, r.y + 82, 26, s.color, 'loaded', 'surface', accent_ring=True)
                head = (s.name if s.index == model.HH_GATE_BYPASS else
                        '%s · %s' % (s.letter, s.name or s.material))
                c.text(r.x + 96, r.y + 58, r.w - 330, 26, head, F.BTN, 'text', 'surface')
                c.text(r.x + 96, r.y + 88, r.w - 330, 20, line2, F.TEXT, 'text2', 'surface')
            else:
                c.text(r.x + 16, r.y + 60, r.w - 32, 20, line2, F.TEXT, 'text2', 'surface')
            # rechts: Belegung der Box
            n = len(slots)
            step, rad = (52, 16) if n <= 4 else (30, 11)
            x = r.x2 - 16 - n * step + 8
            for i, sl in enumerate(slots):
                cx = x + i * step + 22
                empty = sl.state in ('empty', 'unknown') or not sl.color
                mini_spool(c, cx, r.y + 70, rad, None if empty else sl.color, lg == sl.index,
                           'surface')
                c.text(cx - 15, r.y + 92, 30, 18, sl.letter, F.LBL,
                       'accent' if lg == sl.index else 'text3', 'surface', 'center')
        frame.region('fpanel', panel, key, paint)
