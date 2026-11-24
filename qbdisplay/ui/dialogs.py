# qbdisplay – Dialoge (Bestätigung, Hinweis, Fehler, Temperatur, Anpassen)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Dialoge liegen über der abgedunkelten Seite (Farben mit dem Scrim
gemischt, siehe Canvas.dim). Gefährliche Aktionen laufen immer über
:class:`ConfirmDialog`."""

from .. import colors
from .. import errors
from .. import fonts as F
from .. import model
from ..i18n import _, N_, decimal
from ..canvas import Rect
from . import widgets as W


# Farbe unter dem Dialog (abgedunkelte Seite) – für den Lichthof des Rahmens
UNDER_DIALOG = colors.mix('bg', 'scrim', 0.8)
SHADOW = 6          # dunkler Rand um schwebende Dialoge


def shadow_area(frame):
    """Fläche aller Dialog-Regionen plus Schattenrand (auf den Bildschirm begrenzt)."""
    rs = [r.rect for r in frame.regions]
    x0 = max(0, min(r.x for r in rs) - SHADOW)
    y0 = max(0, min(r.y for r in rs) - SHADOW)
    x1 = min(800, max(r.x + r.w for r in rs) + SHADOW)
    y1 = min(480, max(r.y + r.h for r in rs) + SHADOW)
    return Rect(x0, y0, x1 - x0, y1 - y0)


def paint_shadow(c, r):
    """Nur der Rand (das Innere übermalt der Dialog): hebt ihn von der Seite ab."""
    s = SHADOW
    c.fill(r.x, r.y, r.w, s, UNDER_DIALOG)
    c.fill(r.x, r.y + r.h - s, r.w, s, UNDER_DIALOG)
    c.fill(r.x, r.y + s, s, r.h - 2 * s, UNDER_DIALOG)
    c.fill(r.x + r.w - s, r.y + s, s, r.h - 2 * s, UNDER_DIALOG)
    # Ecken des abgerundeten Kastens: Lücken zwischen Rand und Rundung füllen
    c.fill(r.x + s, r.y + s, 18, 18, UNDER_DIALOG)
    c.fill(r.x + r.w - s - 18, r.y + s, 18, 18, UNDER_DIALOG)
    c.fill(r.x + s, r.y + r.h - s - 18, 18, 18, UNDER_DIALOG)
    c.fill(r.x + r.w - s - 18, r.y + r.h - s - 18, 18, 18, UNDER_DIALOG)


def kicker(c, x, y, text, tick='accent'):
    """Kleine Überzeile über Dialogtiteln (Akzentstrich + Großbuchstaben)."""
    W.caption(c, x, y, text, 'surface', fg=tick if tick != 'accent' else 'text3', tick=tick)


class Dialog(object):
    box = Rect(140, 110, 520, 260)
    border = 'accent'
    layer = 'dialog'

    def __init__(self, ctx):
        self.ctx = ctx

    def frame_box(self, frame, key=0):
        b = self.box

        def paint(c, r):
            W.glow_box(c, r, 18, 'surface', self.border, UNDER_DIALOG, halo=3, bw=1,
                       inner=False)
        frame.region('dlg.box', b, (self.border, key), paint, opaque=True)

    def buttons(self, frame, items, y=None, under='surface'):
        """items: [(tid, label, kind, icon, action, weight)]"""
        b = self.box
        y = y if y is not None else b.y2 - 20 - 64
        x0, w = b.x + 20, b.w - 40
        total_w = sum(it[5] for it in items)
        gap = 10
        avail = w - gap * (len(items) - 1)
        x = x0
        for i, (tid, label, kind, icon, action, weight) in enumerate(items):
            bw = int(avail * weight / total_w) if i < len(items) - 1 else x0 + w - x
            rr = Rect(x, y, bw, 64)
            pr = self.ctx.pressed == tid

            def paint(c, r, label=label, kind=kind, icon=icon, pr=pr):
                W.button(c, r, label, kind, icon, under, pressed=pr)
            frame.region('dlg.' + tid, rr, (label, kind, pr), paint, clear=under)
            if action is not None and kind != 'disabled':
                frame.target(tid, rr, action)
            x += bw + gap

    def build(self, frame):   # pragma: no cover
        raise NotImplementedError


class ConfirmDialog(Dialog):
    def __init__(self, ctx, title, text, ok_label, on_ok, danger=True, ok_icon=None):
        Dialog.__init__(self, ctx)
        self.title, self.text, self.ok_label, self.on_ok = title, text, ok_label, on_ok
        self.danger = danger
        self.ok_icon = ok_icon
        self.border = 'err' if danger else 'accent'
        self.layer = ('confirm', title, text)

    def build(self, frame):
        b = self.box
        self.frame_box(frame)

        def paint(c, r):
            kicker(c, r.x, r.y, _('Bitte bestätigen'), 'err' if self.danger else 'accent')
            c.text(r.x, r.y + 24, r.w, 30, self.title, F.TITLE, 'text', 'surface')
            W.text_lines(c, r.x, r.y + 64, r.w, self.text, F.TEXT, 'text2', 'surface', max_lines=3)
        frame.region('dlg.body', Rect(b.x + 28, b.y + 22, b.w - 56, 136), 0, paint,
                     clear='surface')
        self.buttons(frame, [
            ('no', _('Abbrechen'), 'secondary', None, self.ctx.close_dialog, 1),
            ('yes', self.ok_label, 'danger' if self.danger else 'primary', self.ok_icon,
             self._ok, 1)])

    def _ok(self):
        self.ctx.close_dialog()
        self.on_ok()


class InfoDialog(Dialog):
    def __init__(self, ctx, title, text):
        Dialog.__init__(self, ctx)
        self.title, self.text = title, text
        self.layer = ('info', title, text)

    def build(self, frame):
        b = self.box
        self.frame_box(frame)

        def paint(c, r):
            c.icon('info', r.x, r.y + 3, 24, 'accent', 'surface')
            c.text(r.x + 36, r.y, r.w - 36, 30, self.title, F.TITLE, 'text', 'surface')
            W.text_lines(c, r.x, r.y + 44, r.w, self.text, F.TEXT, 'text2', 'surface', max_lines=4)
        frame.region('dlg.body', Rect(b.x + 28, b.y + 22, b.w - 56, 140), 0, paint,
                     clear='surface')
        self.buttons(frame, [('ok', 'OK', 'primary', None, self.ctx.close_dialog, 1)])


class ErrorDialog(Dialog):
    """Entwurf 6: Klartext-Titel, Code klein rechts, Filamentweg mit
    Sensorstatus, nummerierte Schritte, genau drei Aktionen."""
    box = Rect(64, 52, 672, 404)
    border = 'err'

    def __init__(self, ctx, err):
        Dialog.__init__(self, ctx)
        self.err = err    # dict: info(ErrorInfo), subtitle, gate, sensors, kind, raw
        self.layer = ('error', err.get('raw'))

    def build(self, frame):
        ctx = self.ctx
        b = self.box
        e = self.err
        info = e['info']
        self.frame_box(frame)

        def paint_head(c, r):
            c.fill(r.x, r.y + 16, r.w, r.h - 16, 'err_bg')
            c.rr(Rect(r.x, r.y, r.w, 34), 14, 'err_bg')
            c.fill(r.x, r.y2 - 1, r.w, 1, colors.mix('err_bg', 'err', 0.4))
            c.icon('alert', r.x + 18, r.cy - 17, 34, 'err', 'err_bg')
            c.text(r.x + 66, r.y + 8, r.w - 66 - 130, 30, info.title, F.TITLE, 'text', 'err_bg')
            c.text(r.x + 66, r.y + 40, r.w - 66 - 20, 18, e.get('subtitle', ''), F.CAP, 'text2',
                   'err_bg')
            if info.code:
                c.label_right(r.x2 - 18, r.y + 12, info.code, F.CAP, 'text3', 'err_bg')
        head = Rect(b.x + 4, b.y + 4, b.w - 8, 72)
        frame.region('dlg.head', head, (info.title, e.get('subtitle'), info.code), paint_head,
                     clear='surface', opaque=True)
        y = head.y2 + 12
        if e.get('kind') == 'mmu':
            self.build_path(frame, Rect(b.x + 20, y, b.w - 40, 84))
            y += 84 + 14
        steps = info.steps[:3]

        def paint_steps(c, r):
            yy = r.y
            for i, s in enumerate(steps):
                c.disc(r.x + 12, yy + 12, 12, 'line')
                c.disc(r.x + 12, yy + 12, 11, 'surface2')
                c.text(r.x + 4, yy + 3, 16, 18, str(i + 1), F.CAP, 'accent', 'surface2', 'center')
                lines = F.wrap(s, F.TEXT, r.w - 36, 2)
                for k, ln in enumerate(lines):
                    c.text(r.x + 36, yy + 2 + k * 22, r.w - 36, 20, ln, F.TEXT, 'text', 'surface')
                yy += 22 * len(lines) + 10
        frame.region('dlg.steps', Rect(b.x + 20, y, b.w - 40, b.y2 - 100 - y), tuple(steps),
                     paint_steps, clear='surface')
        self.buttons(frame, e['actions'])

    def build_path(self, frame, rect):
        e = self.err
        nodes, links = errors.filament_path(e.get('sensors'), e.get('gate'), *e.get('sensor_names', ()))
        gate = e.get('gate')
        color = e.get('color')
        nodes = list(nodes)
        if gate is not None:
            nodes[0] = nodes[0]._replace(label=_('Slot %s') % model.letter(gate))

        def paint(c, r):
            c.rr(r, 12, 'bg')
            n = len(nodes)
            nw = 96
            xs = [r.x + 14 + nw // 2 + i * (r.w - 28 - nw) // (n - 1) for i in range(n)]
            iy = r.y + 10
            for i, node in enumerate(nodes):
                cx = xs[i]
                bad = node.key == 'extruder' and links[-1] == 'bad'
                box = Rect(cx - 20, iy, 40, 40)
                if bad:
                    c.box(box, 10, 'surface2', 'err', 2)
                else:
                    c.rr(box, 10, 'surface2')
                if node.key == 'slot':
                    W.color_dot(c, box.cx, box.cy, 10, color or '#444C58', 'surface2')
                    c.disc(box.cx, box.cy, 4, 'surface2')
                else:
                    icon = {'gate': 'box', 'tube': 'tube', 'extruder': 'nozzle'}[node.key]
                    fg = 'err' if bad else ('ok' if node.state == 'ok' and node.key == 'gate'
                                            else 'text2')
                    c.icon(icon, box.cx - 12, box.cy - 12, 24, fg, 'surface2')
                c.text(cx - nw // 2, iy + 46, nw, 18, node.label, F.CAP,
                       'err' if bad else 'text2', 'bg', 'center')
            for i, state in enumerate(links):
                x0, x1 = xs[i] + 28, xs[i + 1] - 28
                ly = iy + 20
                col = {'ok': 'ok', 'bad': 'err'}.get(state, 'line')
                if state == 'bad' or state == 'unknown':
                    pos = x0
                    while pos < x1:
                        c.fill(pos, ly - 2, min(8, x1 - pos), 4, col)
                        pos += 14
                else:
                    c.fill(x0, ly - 2, x1 - x0, 4, col)
                mx = (x0 + x1) // 2
                if state in ('ok', 'bad'):
                    c.disc(mx, ly, 14, 'bg')
                    c.icon('check' if state == 'ok' else 'x', mx - 10, ly - 10, 20,
                           'ok' if state == 'ok' else 'err', 'bg')
        frame.region('dlg.path', rect, (tuple(nodes), tuple(links), color), paint,
                     clear='surface')


class TempDialog(Dialog):
    box = Rect(110, 64, 580, 352)
    PRESETS = {
        'extruder': [(N_('Aus'), 0), ('PLA', 210), ('PETG', 240), ('ABS', 260)],
        'heater_bed': [(N_('Aus'), 0), ('PLA', 55), ('PETG', 70), ('ABS', 100)],
        'chamber': [(N_('Aus'), 0), ('45 °C', 45), ('55 °C', 55), ('65 °C', 65)],
    }
    LIMITS = {'extruder': 350, 'heater_bed': 120, 'chamber': 65}
    NAMES = {'extruder': N_('Düse'), 'heater_bed': N_('Bett'), 'chamber': N_('Kammer')}

    def __init__(self, ctx, heater, current_target):
        Dialog.__init__(self, ctx)
        self.heater = heater
        self.value = int(current_target or 0)
        self.layer = ('temp', heater)

    def set(self, v):
        self.value = max(0, min(self.LIMITS[self.heater], int(v)))
        self.ctx.request_render()

    def build(self, frame):
        ctx = self.ctx
        b = self.box
        self.frame_box(frame)
        obj = ctx.heater_object(self.heater)
        cur = ctx.st.get(obj, 'temperature')
        title = _('%s · Ist %s °C') % (_(self.NAMES[self.heater]), model.fmt_temp(cur))

        def paint_t(c, r):
            c.text(r.x, r.y, r.w, 30, title, F.TITLE, 'text', 'surface')
        frame.region('dlg.title', Rect(b.x + 24, b.y + 18, b.w - 48, 30), title, paint_t,
                     clear='surface')
        val = _('Soll %d °C') % self.value if self.value else _('Soll: aus')
        row_y = b.y + 64
        for i, (d, label) in enumerate(((-10, '-10'), (-1, '-1'))):
            rr = Rect(b.x + 24 + i * 72, row_y, 64, 64)
            self._btn(frame, 'm%d' % i, rr, label, (lambda d=d: self.set(self.value + d)))
        for i, (d, label) in enumerate(((1, '+1'), (10, '+10'))):
            rr = Rect(b.x2 - 24 - 64 - (1 - i) * 72, row_y, 64, 64)
            self._btn(frame, 'p%d' % i, rr, label, (lambda d=d: self.set(self.value + d)))

        def paint_v(c, r):
            c.text(r.x, r.y, r.w, r.h, val, F.BIG, 'heat' if self.value else 'text2', 'surface',
                   'center')
        frame.region('dlg.val', Rect(b.x + 24 + 144, row_y + 12, b.w - 48 - 288, 40), val,
                     paint_v, clear='surface')
        presets = self.PRESETS[self.heater]
        pw = (b.w - 48 - 8 * (len(presets) - 1)) // len(presets)
        for i, (label, v) in enumerate(presets):
            rr = Rect(b.x + 24 + i * (pw + 8), row_y + 84, pw, 64)
            sub = '%d °C' % v if v else _('Heizung aus')
            label = label if v else _(label)
            tid = 'pre%d' % i
            pr = ctx.pressed == tid
            on = v == self.value

            def paint_p(c, r, label=label, sub=sub, pr=pr, on=on):
                W.button(c, r, label, 'selected' if on else 'secondary', None, 'surface',
                         sub=sub, pressed=pr)
            frame.region('dlg.' + tid, rr, (label, sub, on, pr), paint_p, clear='surface')
            frame.target(tid, rr, (lambda v=v: self.set(v)))
        self.buttons(frame, [
            ('no', _('Abbrechen'), 'secondary', None, ctx.close_dialog, 1),
            ('yes', _('Übernehmen'), 'primary', 'check', self._apply, 1)])

    def _btn(self, frame, tid, rr, label, act):
        pr = self.ctx.pressed == tid

        def paint(c, r):
            W.button(c, r, label, 'secondary', None, 'surface', fid=F.BTN, pressed=pr)
        frame.region('dlg.' + tid, rr, pr, paint, clear='surface')
        frame.target(tid, rr, act)

    def _apply(self):
        self.ctx.close_dialog()
        self.ctx.set_temperature(self.heater, self.value)


class TuneDialog(Dialog):
    """Anpassen während des Drucks: Geschwindigkeit, Fluss, Z-Versatz."""
    box = Rect(110, 52, 580, 400)
    layer = 'tune'

    def build(self, frame):
        ctx = self.ctx
        b = self.box
        st = ctx.st
        self.frame_box(frame)

        def paint_t(c, r):
            c.text(r.x, r.y, r.w, 30, _('Druck anpassen'), F.TITLE, 'text', 'surface')
        frame.region('dlg.title', Rect(b.x + 24, b.y + 18, b.w - 48, 30), 0, paint_t,
                     clear='surface')
        speed = int(round((st.get('gcode_move', 'speed_factor', 1.0) or 1.0) * 100))
        flow = int(round((st.get('gcode_move', 'extrude_factor', 1.0) or 1.0) * 100))
        zoff = (st.get('gcode_move', 'homing_origin') or [0, 0, 0, 0])[2]
        rows = [('speed', _('Geschwindigkeit'), '%d %%' % speed,
                 lambda: ctx.gcode('M220 S%d' % max(10, speed - 10)),
                 lambda: ctx.gcode('M220 S%d' % min(300, speed + 10))),
                ('flow', _('Fluss'), '%d %%' % flow,
                 lambda: ctx.gcode('M221 S%d' % max(50, flow - 2)),
                 lambda: ctx.gcode('M221 S%d' % min(150, flow + 2))),
                ('z', _('Z-Versatz (Babystep)'), decimal('%+.3f mm' % zoff),
                 lambda: ctx.gcode('SET_GCODE_OFFSET Z_ADJUST=-0.02 MOVE=1'),
                 lambda: ctx.gcode('SET_GCODE_OFFSET Z_ADJUST=0.02 MOVE=1'))]
        for i, (key, label, val, dec, inc) in enumerate(rows):
            y = b.y + 62 + i * 76
            rr = Rect(b.x + 24, y, b.w - 48, 64)

            def paint_r(c, r, label=label, val=val, i=i):
                if i:
                    c.fill(r.x, r.y - 6, r.w, 1, 'line')
                c.text(r.x, r.cy - 10, 210, 20, W.caps(label), F.LBL, 'text2', 'surface')
                c.text(r.x + 290, r.cy - 16, 136, 32, val, F.VAL, 'text', 'surface', 'center')
            frame.region('dlg.r' + key, rr, val, paint_r, clear='surface')
            for sign, x, act in (('-', rr.x + 220, dec), ('+', rr.x2 - 64, inc)):
                br = Rect(x, y, 64, 64)
                tid = '%s%s' % (key, sign)
                pr = ctx.pressed == tid

                def paint_pm(c, r, sign=sign, pr=pr):
                    W.plus_minus(c, r, sign, 'surface', pressed=pr)
                frame.region('dlg.' + tid, br, pr, paint_pm, clear='surface')
                frame.target(tid, br, act)
        self.buttons(frame, [('ok', _('Schließen'), 'primary', None, ctx.close_dialog, 1)])
