# qbdisplay – Bewegen / Steuerung
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Entwurf 5. Beim Plus4 bewegt Z das Bett: Z- = Bett hoch (zur Düse)."""

from .. import colors
from .. import fonts as F
from .. import model
from ..i18n import _, N_, decimal
from ..canvas import Rect
from . import widgets as W
from .chrome import Page

STEPS = (0.1, 1.0, 10.0, 50.0)
PAD_C = (234, 186)          # Mitte des XY-Steuerkreuzes
PAD_R = 132
ZPAD = Rect(384, 54, 96, 264)


def step_label(v):
    return decimal('%g' % v)


class MovePage(Page):
    section = 'move'
    title = N_('Bewegen')

    def build_content(self, frame):
        ctx = self.ctx
        st = ctx.st
        printing = ctx.pstate in ('printing', 'paused', 'paused_error')
        step = ctx.ui.get('step', 10.0)
        homed = st.get('toolhead', 'homed_axes', '') or ''

        enabled = not printing
        free = ctx.free_move
        can_free = ctx.can_free_move()
        # Steuerkreuz: runde Scheibe, durch Diagonalen in vier Felder geteilt,
        # in der Mitte "Home XY". Daneben eine Kapsel für Z.
        pcx, pcy, prad = PAD_C[0], PAD_C[1], PAD_R

        def paint_pad(c, r):
            c.disc(pcx, pcy, prad, 'line')
            c.disc(pcx, pcy, prad - 1, 'surface')
            c.circle(pcx, pcy, 60, 'line')
            for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                c.line(pcx + sx * 43, pcy + sy * 43, pcx + sx * 91, pcy + sy * 91, 'line')
            zr = ZPAD
            c.box(zr, 26, 'surface', 'line', 1)
            for yy in (zr.y + 88, zr.y2 - 88):
                c.fill(zr.x + 18, yy, zr.w - 36, 1, 'line')
        frame.region('pad', Rect(PAD_C[0] - prad, PAD_C[1] - prad, ZPAD.x2 - PAD_C[0] + prad,
                                 2 * prad + 1), 0, paint_pad)

        def jog(tid, rect, icon, label, small, action, home=False):
            pr = ctx.pressed == tid
            enabled = not printing and not (home and free)

            def paint(c, r):
                face = 'surface'
                if home:
                    ring = 'white' if pr else ('accent' if enabled else 'line')
                    rad = min(r.w, r.h) // 2
                    c.disc(r.cx, r.cy, rad, colors.mix('surface', 'accent', 0.25)
                           if enabled else 'surface')
                    c.disc(r.cx, r.cy, rad - 2, ring)
                    c.disc(r.cx, r.cy, rad - 4, 'tint')
                    face = 'tint'
                elif pr:
                    c.rr(r.inset(2), 14, 'tint')
                    face = 'tint'
                fg = ('accent' if home or pr else 'text') if enabled else 'text3'
                ih = 28
                total = ih + (24 if label else 0) + 18
                y = r.y + (r.h - total) // 2
                if enabled or not home:     # gesperrtes Home: kein Icon (keine Farbvariante)
                    c.icon(icon, r.cx - 14, y, 28, fg, face)
                y += ih + 2
                if label:
                    c.text(r.x + 2, y, r.w - 4, 24, label, F.BTN, fg, face, 'center')
                    y += 22
                c.text(r.x - 6, y, r.w + 12, 18, W.caps(small), F.CAP,
                       'accent' if home and enabled else 'text3', face, 'center')
            frame.region(tid, rect, (pr, enabled), paint, clear='surface', parent='pad')
            if enabled:
                frame.target(tid, rect, action)

        s = step
        cx, cy = PAD_C
        jog('y+', Rect(cx - 40, cy - prad + 8, 80, 74), 'up', 'Y+', _('hinten'),
            lambda: ctx.jog('Y', s))
        jog('y-', Rect(cx - 40, cy + prad - 82, 80, 74), 'down', 'Y-', _('vorne'),
            lambda: ctx.jog('Y', -s))
        jog('x-', Rect(cx - prad + 6, cy - 40, 74, 80), 'left', 'X-', _('links'),
            lambda: ctx.jog('X', -s))
        jog('x+', Rect(cx + prad - 80, cy - 40, 74, 80), 'right', 'X+', _('rechts'),
            lambda: ctx.jog('X', s))
        jog('hxy', Rect(cx - 40, cy - 40, 80, 80), 'home', '', 'XY', lambda: ctx.home('X Y'),
            home=True)
        zr = ZPAD
        jog('z-', Rect(zr.x + 8, zr.y + 8, zr.w - 16, 78), 'up', 'Z-', _('Bett hoch'),
            lambda: ctx.jog('Z', -s))
        jog('hz', Rect(zr.cx - 40, zr.cy - 40, 80, 80), 'home', '', 'Z', lambda: ctx.home('Z'),
            home=True)
        jog('z+', Rect(zr.x + 8, zr.y2 - 86, zr.w - 16, 78), 'down', 'Z+', _('Bett runter'),
            lambda: ctx.jog('Z', s))

        # Position
        pos = st.get('gcode_move', 'gcode_position') or st.get('toolhead', 'position') or [0, 0, 0]
        ref = all(a in homed for a in 'xyz') and not free
        ptxt = (('%.1f' % pos[0], '%.1f' % pos[1],
                 ('%.2f' if abs(pos[2]) < 100 else '%.1f') % pos[2]) if len(pos) >= 3
                else ('', '', ''))
        pr_ = Rect(492, 52, 292, 92)

        def paint_pos(c, r):
            W.tile(c, r)
            W.header(c, r, 'target', _('Position'), x=r.x + 14, y=r.y + 12)
            if free:
                W.chip(c, r.x2 - 14, r.y + 12, _('Notbewegung'), 'warn', 'surface', right=True)
            elif ref:
                W.chip(c, r.x2 - 14, r.y + 12, _('referenziert'), 'ready', 'surface', icon='check',
                       right=True)
            else:
                W.chip(c, r.x2 - 14, r.y + 12, _('nicht referenziert'), 'warn', 'surface',
                       right=True)
        frame.region('pos', pr_, (ref, free), paint_pos)

        def paint_xyz(c, r):
            cw = r.w // 3
            for i, (ax, val) in enumerate(zip('XYZ', ptxt)):
                x = r.x + i * cw
                if i:
                    c.fill(x - 8, r.y + 2, 1, 28, 'line')
                x2 = c.label(x, r.y + 2, ax, F.LBL, 'accent', 'surface', h=32)
                c.label(x2 + 4, r.y, val, F.VAL, 'text', 'surface',
                        max_w=cw - (x2 + 4 - x) - 8)
        vr = Rect(pr_.x + 14, pr_.y + 50, pr_.w - 28, 34)
        if can_free:
            # nicht referenziert: Zahlen wären bedeutungslos -> Einstieg in die Notbewegung
            fpr = ctx.pressed == 'freemove'

            def paint_free(c, r):
                fg = 'text' if fpr else 'accent'
                x2 = c.label(r.x, r.y + 2, _('Ohne Referenzfahrt bewegen'), F.LBL, fg,
                             'surface', h=30)
                cx, cy = x2 + 10, r.y + 17
                c.thick_line(cx, cy - 6, cx + 6, cy, 2, fg)
                c.thick_line(cx + 6, cy, cx, cy + 6, 2, fg)
            frame.region('pos.v', vr, ('free', fpr), paint_free, clear='surface')
            frame.target('freemove', pr_, ctx.confirm_free_move)
        else:
            # nur die Zahlen neu zeichnen, nicht die ganze Kachel
            frame.region('pos.v', vr, ptxt, paint_xyz, clear='surface', gaps=True)

        def paint_cap(c, r):
            c.fill_rect(r, 'bg')
            W.caption(c, r.x, r.y, _('Schrittweite (mm)'), 'bg')
        frame.region('stepcap', Rect(492, 156, 292, 18), 0, paint_cap, opaque=True)
        seg_r = Rect(492, 178, 292, 62)
        sel = STEPS.index(step) if step in STEPS else 2

        def paint_seg(c, r):
            W.seg(c, r, [step_label(v) for v in STEPS], sel, fid=F.VAL)
        frame.region('seg', seg_r, sel, paint_seg)
        sw = (seg_r.w - 8 - 12) / 4.0
        for i, v in enumerate(STEPS):
            if free and v > model.FREE_STEP:
                act = (lambda: ctx.notify(_('Bei der Notbewegung höchstens %d mm')
                                          % model.FREE_STEP, 'warn'))
            else:
                act = (lambda v=v: ctx.set_ui(step=v))
            frame.target('step.%d' % i, Rect(seg_r.x + 4 + i * (sw + 4), seg_r.y, sw, seg_r.h),
                         act)

        for i, (tid, label, icon, act) in enumerate((
                ('homeall', _('Alle Achsen'), 'home', lambda: ctx.home('')),
                ('done', _('Fertig'), 'check', ctx.end_free_move) if free else
                ('motoff', _('Motoren aus'), 'power', ctx.motors_off))):
            rr = Rect(492 + i * 150, 264, 142, 56)
            pr = ctx.pressed == tid
            en = not printing and not (free and tid == 'homeall')
            kind = 'primary' if tid == 'done' else ('secondary' if en else 'disabled')

            def paint_b(c, r, label=label, icon=icon, pr=pr, en=en, kind=kind):
                W.button(c, r, label, kind, icon if en else None, 'bg', fid=F.LBL, pressed=pr)
            frame.region('b.%d' % i, rr, (label, pr, en), paint_b)
            if en:
                frame.target(tid, rr, act)

        # Extruder
        ex = Rect(100, 332, 336, 136)
        et = st.get('extruder', 'temperature')
        etarget = st.get('extruder', 'target', 0) or 0
        minimum = ctx.cfg.getint('printer', 'min_extrude_temp')
        can = et is not None and et >= minimum and not printing
        amount = int(max(1, min(50, step)))
        cap = _('Düse %s °C') % model.fmt_temp(et) + ((' · ' + _('ab %d °C') % minimum)
                                                      if not can else (' · ' + _('Soll %d') % etarget
                                                                       if etarget else ''))

        def paint_ex(c, r):
            W.tile(c, r)
            W.header(c, r, 'nozzle', _('Extruder'), x=r.x + 14, y=r.y + 12,
                     icon_fg='heat' if etarget > 0 else 'accent')
        frame.region('ex', ex, etarget > 0, paint_ex)

        def paint_cap(c, r):
            c.label_right(r.x2, r.y + 3, cap, F.CAP, 'text3', 'surface')
        frame.region('ex.cap', Rect(ex.x + 150, ex.y + 12, ex.w - 164, 22), cap, paint_cap,
                     clear='surface', gaps=True)
        frame.target('ex.temp', Rect(ex.x, ex.y, ex.w, 48), (lambda: ctx.open_temp('extruder')))
        bw = (ex.w - 28 - 8) // 2
        for i, (tid, label, icon, dist) in enumerate((
                ('retract', _('Zurück %d') % amount, 'up', -amount),
                ('extrude', _('Fördern %d') % amount, 'down', amount))):
            rr = Rect(ex.x + 14 + i * (bw + 8), ex.y2 - 12 - 56, bw, 56)
            pr = ctx.pressed == tid

            def paint_e(c, r, label=label, icon=icon, pr=pr):
                if can:
                    W.button(c, r, label, 'secondary', icon, 'surface', fid=F.LBL, pressed=pr)
                else:
                    W.button(c, r, label, 'disabled', icon, 'surface', fid=F.LBL)
            frame.region('e.' + tid, rr, (label, can, pr), paint_e, clear='surface')
            if can:
                frame.target(tid, rr, (lambda d=dist: ctx.extrude(d)))

        # Lüfter
        fan = Rect(448, 332, 336, 136)

        def paint_fan(c, r):
            W.tile(c, r)
            W.header(c, r, 'fan', _('Lüfter'), x=r.x + 14, y=r.y + 12)
            c.label_right(r.x2 - 14, r.y + 15, _('Tippen: 0 / 50 / 100 %'), F.CAP, 'text3',
                          'surface')
        frame.region('fan', fan, 0, paint_fan)
        fans = [('fan_part', N_('Bauteil')), ('fan_aux', N_('Hilfslüfter')), ('fan_chamber', N_('Kammer'))]
        fw = (fan.w - 28 - 16) // 3
        for i, (key, label) in enumerate(fans):
            name = ctx.cfg.get('printer', key)
            speed = st.get(model.fan_object(name), 'speed', 0) or 0
            rr = Rect(fan.x + 14 + i * (fw + 8), fan.y2 - 12 - 56, fw, 56)
            tid = 'f.' + key
            pr = ctx.pressed == tid
            pct = '%d %%' % int(round(speed * 100))

            def paint_f(c, r, label=label, pct=pct, pr=pr, on=speed > 0):
                W.button(c, r, pct, 'secondary', None, 'surface', fid=F.BTN, pressed=pr,
                         sub=_(label), label_fg='accent' if on else None)
            frame.region(tid, rr, (pct, pr), paint_f, clear='surface')
            frame.target(tid, rr, (lambda n=name, s=speed: ctx.cycle_fan(n, s)))
