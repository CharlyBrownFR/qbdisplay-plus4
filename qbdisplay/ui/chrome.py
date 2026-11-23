# qbdisplay – Statusleiste, Navigation, Seitenbasis
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Feste Zonen: Statusleiste 40 px oben, Navigation 88 px links,
Inhaltsfläche 712 × 440 px (mit Rand: x 100..784, y 52..468)."""

import time

from .. import fonts as F
from .. import model
from ..i18n import _, N_
from ..canvas import Rect
from . import widgets as W

STATUS_H = 40
NAV_W = 88
CONTENT = Rect(100, 52, 684, 416)

NAV_ITEMS = [
    ('home', 'home', N_('Start')),
    ('filament', 'spool', N_('Filament')),
    ('move', 'move', N_('Bewegen')),
    ('files', 'folder', N_('Dateien')),
    ('system', 'sliders', N_('System')),
]


def state_pill(ctx):
    """-> (Text, Art) für die Zustandspille."""
    ps = ctx.pstate
    if ps == 'offline':
        return _('Keine Verbindung'), 'err'
    if ps == 'startup':
        return _('Startet ...'), 'info'
    if ps == 'error':
        return _('Fehler'), 'err'
    if ps == 'paused_error':
        return _('Pausiert · Fehler'), 'err'
    if ps == 'paused':
        return _('Pausiert'), 'warn'
    if ps == 'printing':
        return _('Druckt · %d %%') % int(model.progress(ctx.st) * 100), 'run'
    dv = ctx.drying
    if dv.active and ctx.has_box:
        if dv.known:
            return _('Trocknet · %s') % model.fmt_duration(dv.remaining, 'clock'), 'run'
        return _('Trocknet'), 'run'
    return _('Bereit'), 'ok'


def build_statusbar(frame, ctx, title):
    def paint_bg(c, r):
        c.fill(0, 0, 800, STATUS_H - 1, 'bar')
        c.fill(0, STATUS_H - 1, 800, 1, 'line')
    frame.region('sb.bg', Rect(0, 0, 800, STATUS_H), 'bg', paint_bg, opaque=True)

    text, kind = state_pill(ctx)

    def paint_left(c, r):
        c.fill(14, 12, 3, 16, 'accent')
        x = c.label(24, 11, W.caps(title), F.LBL, 'text', 'bar', max_w=220)
        W.pill_state(c, x + 12, 7, text, kind)
    left = Rect(0, 0, 420, STATUS_H - 1)
    frame.region('sb.left', left, (title, text, kind), paint_left, clear='bar', parent='sb.bg',
                 gaps=True)
    if ctx.pstate in ('paused_error', 'error'):
        frame.target('sb.pill', left, ctx.show_error)

    # rechts: Uhr, Netzwerk, Nur LAN, Box-Klima (von rechts nach links)
    clock = time.strftime('%H:%M', time.localtime(ctx.now))

    def paint_clock(c, r):
        c.label_right(784, 10, clock, F.LBL, 'text', 'bar', h=20)
    frame.region('sb.clock', Rect(730, 0, 56, STATUS_H - 1), clock, paint_clock,
                 clear='bar', parent='sb.bg', gaps=True)

    net = ctx.net
    wicon = 'wifi' if net.get('iface_kind') == 'wifi' else (
        'ethernet' if net.get('iface_kind') == 'ethernet' else 'wifioff')
    wfg = 'err' if wicon == 'wifioff' else 'text2'

    def paint_wifi(c, r):
        c.icon(wicon, 700, 11, 18, wfg, 'bar')
    frame.region('sb.wifi', Rect(694, 0, 30, STATUS_H - 1), (wicon, wfg), paint_wifi,
                 clear='bar', parent='sb.bg')

    lan = net.get('lan_only')

    def paint_lan(c, r):
        if lan:
            x = c.label_right(682, 10, W.caps(_('Nur LAN')), F.LBL, 'ok', 'bar', h=20)
            c.icon('shield', x - 24, 11, 18, 'ok', 'bar')
        else:
            x = c.label_right(682, 10, W.caps(_('Cloud an')), F.LBL, 'warn', 'bar', h=20)
            c.icon('cloudoff', x - 24, 11, 18, 'warn', 'bar')
    frame.region('sb.lan', Rect(580, 0, 110, STATUS_H - 1), lan, paint_lan, clear='bar',
                 parent='sb.bg')

    temp, target, hum, heating = ctx.climate
    has_box = ctx.has_box
    ctext = '%s °C · %s %%' % (model.fmt_temp(temp), model.fmt_temp(hum)) if has_box else ''
    fg = 'heat' if heating else 'text2'

    def paint_climate(c, r):
        if not has_box:
            return       # ohne Box kein Box-Klima
        x = c.label_right(566, 10, ctext, F.LBL, fg, 'bar', h=20)
        c.icon('sun' if heating else 'box', x - 24, 11, 18, fg, 'bar')
    frame.region('sb.climate', Rect(420, 0, 156, STATUS_H - 1), (ctext, fg), paint_climate,
                 clear='bar', parent='sb.bg', gaps=True)


def build_nav(frame, ctx, section):
    def paint_line(c, r):
        c.fill(0, STATUS_H, NAV_W - 1, 480 - STATUS_H, 'bar')
        c.fill(NAV_W - 1, STATUS_H, 1, 480 - STATUS_H, 'line')
    frame.region('nav.bg', Rect(0, STATUS_H, NAV_W, 480 - STATUS_H), 'bg', paint_line, opaque=True)
    for i, (sec, icon, label) in enumerate(NAV_ITEMS):
        rect = Rect(0, STATUS_H + i * 88, NAV_W - 1, 88)
        on = sec == section
        pressed = ctx.pressed == 'nav.' + sec

        def paint(c, r, icon=icon, label=label, on=on, pressed=pressed):
            c.fill_rect(r, 'bar')
            pill = Rect(r.x + 8, r.y + 6, r.w - 16, r.h - 12)
            face = 'bar'
            if on:
                W.glow_box(c, pill, 14, 'surface', 'white' if pressed else 'accent', 'bar',
                           halo=2, bw=1)
                face = 'surface'
            elif pressed:
                c.rr(pill, 14, 'surface2')
                face = 'surface2'
            fg = 'accent' if on else 'text3'
            c.icon(icon, r.cx - 15, r.y + 17, 30, fg, face)
            c.text(pill.x + 4, r.y + 53, pill.w - 8, 18, W.caps(_(label)), F.CAP,
                   'accent' if on else 'text3', face, 'center')
        frame.region('nav.' + sec, rect, (on, pressed), paint, clear='bar', parent='nav.bg',
                     opaque=True)
        frame.target('nav.' + sec, rect, (lambda s=sec: ctx.go(s)))


def build_toast(frame, ctx):
    toast = ctx.toast
    if not toast:
        return
    text, kind = toast
    rect = Rect(CONTENT.x + 60, 416, CONTENT.w - 120, 48)

    def paint(c, r):
        border = {'err': 'err', 'ok': 'ok', 'info': 'info'}.get(kind, 'accent')
        W.glow_box(c, r, 14, 'surface2', border, 'bg', halo=2, bw=1, inner=False)
        c.text(r.x + 16, r.y + 14, r.w - 32, 20, text, F.TEXT, 'text', 'surface2', 'center')
    frame.region('toast', rect, (text, kind), paint, clear='bg', opaque=True)
    frame.target('toast', rect, ctx.clear_toast)


class Page(object):
    """Basisklasse: Statusleiste + Navigation + Inhalt."""
    section = 'home'
    title = ''

    def __init__(self, ctx):
        self.ctx = ctx

    def page_title(self):
        return _(self.title)

    def build(self, frame):
        build_statusbar(frame, self.ctx, self.page_title())
        build_nav(frame, self.ctx, self.section)
        self.build_content(frame)
        build_toast(frame, self.ctx)

    def build_content(self, frame):   # pragma: no cover - in Unterklassen
        raise NotImplementedError

    def on_show(self):
        pass
