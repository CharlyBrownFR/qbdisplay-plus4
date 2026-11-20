# qbdisplay – System (Netzwerk, Box, Kalibrieren, Sprache, Info)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Entwurf 7 (System › Netzwerk) plus einfache Unterseiten."""

from .. import __version__
from .. import fonts as F
from .. import i18n
from ..i18n import _, N_
from ..canvas import Rect
from . import widgets as W
from .chrome import Page

SUBS = [
    ('network', 'wifi', N_('Netzwerk')),
    ('box', 'box', N_('Box')),
    ('calib', 'target', N_('Kalibrieren')),
    ('lang', 'globe', N_('Sprache')),
    ('info', 'info', N_('Info & Update')),
]

AREA = Rect(324, 52, 460, 416)


class SystemPage(Page):
    section = 'system'
    title = N_('System')

    def build_content(self, frame):
        ctx = self.ctx
        sub = ctx.ui.get('sys_sub', 'network')
        for i, (key, icon, label) in enumerate(SUBS):
            rect = Rect(100, 52 + i * 70, 212, 64)
            on = key == sub
            tid = 'sub.' + key
            pr = ctx.pressed == tid

            def paint(c, r, icon=icon, label=label, on=on, pr=pr):
                if on:
                    W.glow_box(c, r, 12, 'tint', 'white' if pr else 'accent', 'bg', halo=2,
                               bw=1)
                    face = 'tint'
                elif pr:
                    c.box(r, 12, 'surface2', 'accent', 2)
                    face = 'surface2'
                else:
                    W.tile(c, r, r=12)
                    face = 'surface'
                c.icon(icon, r.x + 16, r.cy - 12, 24, 'accent' if on else 'text2', face)
                c.text(r.x + 52, r.cy - 10, r.w - 86, 20, _(label), F.TEXT, 'text' if on else 'text2',
                       face)
                c.icon('chev', r.x2 - 32, r.cy - 10, 20, 'accent' if on else 'text3', face)
            frame.region(tid, rect, (on, pr), paint)
            frame.target(tid, rect, (lambda k=key: ctx.set_ui(sys_sub=k)))
        getattr(self, 'build_' + sub)(frame)

    # ------------------------------------------------------------------
    def build_network(self, frame):
        ctx = self.ctx
        net = ctx.net
        lan = bool(net.get('lan_only'))
        card = Rect(AREA.x, 52, AREA.w, 128)

        def paint_lan(c, r):
            W.tile(c, r, glow='ok' if lan else None)
            box = Rect(r.x + 18, r.cy - 28, 56, 56)
            c.rr(box, 14, 'ok_bg' if lan else 'surface2')
            c.icon('shield' if lan else 'cloudoff', box.cx - 16, box.cy - 16, 32,
                   'ok' if lan else 'warn', 'ok_bg' if lan else 'surface2')
            x = box.x2 + 14
            w = r.x2 - 16 - 72 - 12 - x
            c.text(x, r.y + 24, w, 28, _('Nur LAN – Cloud aus') if lan else _('Cloud-Dienste aktiv'),
                   F.TITLE, 'text', 'surface')
            W.text_lines(c, x, r.y + 58, w,
                         _('Keine Verbindung zu QIDI-Servern. Zugriff nur aus dem eigenen Netz.')
                         if lan else _('QIDI-Cloud oder Fernzugriff laufen noch. '
                                       'Antippen zum Abschalten.'), F.LBL, 'text2', 'surface',
                         max_lines=3)
            W.toggle(c, r.x2 - 16 - 72, r.cy - 20, lan, 'surface')
        frame.region('lan', card, lan, paint_lan)
        frame.target('lan', card, ctx.toggle_lan_only)

        wifi = Rect(AREA.x, 192, AREA.w, 120)
        kind = net.get('iface_kind')
        ip = net.get('ip') or '–'
        if kind == 'wifi':
            head = _('WLAN verbunden · Signal %s') % _(net.get('quality') or N_('unbekannt'))
            icon, fg = 'wifi', 'ok'
        elif kind == 'ethernet':
            head, icon, fg = _('Kabel verbunden'), 'ethernet', 'ok'
        else:
            head, icon, fg = _('Nicht verbunden'), 'wifioff', 'err'

        def paint_wifi(c, r):
            W.tile(c, r)
            W.header(c, r, icon, head, icon_fg=fg, max_w=r.w - 200)
            c.text(r.x + 16, r.y + 42, r.w - 170, 40, ip, F.BIG, 'text', 'surface')
            x = c.label(r.x + 16, r.y + 88, W.caps('Web'), F.CAP, 'text3', 'surface')
            c.text(x + 6, r.y + 88, r.x2 - 16 - x - 6, 18, 'http://%s' % ip, F.CAP, 'accent',
                   'surface')
        frame.region('wifi', wifi, (head, ip, kind), paint_wifi)
        br = Rect(wifi.x2 - 16 - 116, wifi.y + 32, 116, 56)
        pr = ctx.pressed == 'wifi.chg'

        def paint_b(c, r):
            W.button(c, r, _('Ändern'), 'secondary', None, 'surface', fid=F.BTN, pressed=pr)
        frame.region('wifi.chg', br, pr, paint_b, clear='surface')
        frame.target('wifi.chg', br, ctx.wifi_info)

        svc = Rect(AREA.x, 324, AREA.w, 144)
        services = net.get('services') or []

        def paint_svc(c, r):
            W.tile(c, r)
            y = r.y + 10
            for i, (icon, label, state) in enumerate(services[:3]):
                if i:
                    c.fill(r.x + 16, y - 3, r.w - 32, 1, 'line')
                kind = {'aktiv': 'ready', 'läuft': 'warn'}.get(state, 'off')
                fg = {'aktiv': 'ok', 'läuft': 'warn'}.get(state, 'text3')
                c.icon(icon, r.x + 16, y + 9, 20, fg, 'surface')
                c.text(r.x + 46, y + 8, r.w - 180, 22, _(label), F.TEXT, 'text', 'surface')
                W.chip(c, r.x2 - 16, y + 6, _(state), kind, 'surface', right=True)
                y += 42
        frame.region('svc', svc, tuple(services), paint_svc)

    # ------------------------------------------------------------------
    def _row(self, frame, rid, y, title, sub, right=None, action=None, toggle=None, kind='secondary',
             h=72):
        ctx = self.ctx
        rect = Rect(AREA.x, y, AREA.w, h)
        pr = ctx.pressed == rid

        def paint(c, r):
            W.tile(c, r, border='accent' if pr else 'line', bw=2 if pr else 1)
            tw = r.w - 32 - (88 if toggle is not None else (150 if right else 0))
            c.text(r.x + 16, r.y + 13, tw, 24, title, F.BTN, 'text', 'surface')
            c.text(r.x + 16, r.y + 41, tw, 18, sub, F.CAP, 'text3', 'surface')
            if toggle is not None:
                W.toggle(c, r.x2 - 16 - 72, r.cy - 20, toggle, 'surface')
            elif right:
                W.button(c, Rect(r.x2 - 12 - 136, r.cy - 26, 136, 52), right, kind, None,
                         'surface', fid=F.LBL)
        frame.region(rid, rect, (title, sub, right, toggle, kind, pr), paint)
        if action is not None:
            frame.target(rid, rect, action)

    def build_box(self, frame):
        ctx = self.ctx
        mmu = ctx.st.mmu
        es = bool(mmu.get('endless_spool_enabled', mmu.get('endless_spool', 0)))
        self._row(frame, 'r.es', 52, _('Automatisch nachladen'),
                  _('Leere Spule: gleiches Material aus anderem Slot'),
                  toggle=es, action=ctx.toggle_endless_spool)
        maxt = ctx.cfg.getint('box', 'dry_max_temp')
        self._row(frame, 'r.dry', 136, _('Trocknung: max. %d °C') % maxt,
                  _('Schutz der Spulenkörper; einstellbar in qbdisplay.cfg'))
        fl = ctx.flist
        self._row(frame, 'r.list', 220, _('Materialliste'),
                  _('%d Materialien, %d Farben, %d Hersteller') % (
                      len(fl.filaments), len(fl.colors), len(fl.vendors)))
        busy = ctx.pstate in ('printing', 'paused', 'paused_error')
        self._row(frame, 'r.check', 304, _('Slots prüfen'),
                  _('Box prüft, in welchen Slots Filament steckt'),
                  right=_('Prüfen') if not busy else _('gesperrt'),
                  kind='secondary' if not busy else 'disabled',
                  action=None if busy else ctx.confirm_check_gates)

    def build_calib(self, frame):
        ctx = self.ctx
        busy = ctx.pstate in ('printing', 'paused', 'paused_error')
        items = [
            ('r.mesh', _('Bettvermessung'), _('Bett wird abgetastet, ca. 5 min'), 'G29',
             _('Bettvermessung starten?')),
            ('r.shaper', _('Input Shaping'), _('Resonanzmessung X/Y, laut, ca. 3 min'),
             'SHAPER_CALIBRATE', _('Resonanzmessung starten?')),
        ]
        for i, (rid, title, sub, gcode, question) in enumerate(items):
            self._row(frame, rid, 52 + i * 84, title, sub,
                      right=_('Starten') if not busy else _('gesperrt'),
                      kind='secondary' if not busy else 'disabled',
                      action=None if busy else (lambda g=gcode, q=question, t=title:
                                                ctx.confirm_gcode(t, q, g)))
        self._row(frame, 'r.calnote', 220, _('Hinweis'),
                  _('Ergebnisse speichert Klipper erst nach SAVE_CONFIG (Weboberfläche).'))

    def build_lang(self, frame):
        ctx = self.ctx
        cur = i18n.get_language()
        for i, (code, name) in enumerate(i18n.LANGUAGES):
            on = code == cur
            # Sprachname in der eigenen Sprache, darunter der Zustand
            self._row(frame, 'r.lang.' + code, 52 + i * 84, name,
                      _('aktiv') if on else _('Antippen zum Wechseln'), toggle=on,
                      action=None if on else (lambda c=code: ctx.set_language(c)))
        self._row(frame, 'r.langnote', 220, _('Hinweis'),
                  _('Gilt sofort und bleibt nach einem Neustart erhalten.'))

    def build_info(self, frame):
        ctx = self.ctx
        vers = ctx.versions
        lines = [('qbdisplay', __version__), ('Klipper', vers.get('klipper', '–')),
                 ('Moonraker', vers.get('moonraker', '–')),
                 ('Display', vers.get('display', '–'))]
        rect = Rect(AREA.x, 52, AREA.w, 156)

        def paint(c, r):
            W.tile(c, r)
            y = r.y + 12
            for i, (k, v) in enumerate(lines):
                if i:
                    c.fill(r.x + 16, y - 5, r.w - 32, 1, 'line')
                c.text(r.x + 16, y + 1, 140, 20, W.caps(k), F.CAP, 'text3', 'surface')
                c.text(r.x + 160, y, r.w - 176, 20, v, F.LBL, 'text', 'surface')
                y += 34
        frame.region('vers', rect, tuple(lines), paint)
        busy = ctx.pstate in ('printing', 'paused', 'paused_error')
        btns = [('i.restart', _('Klipper neu'), 'retry', ctx.confirm_restart),
                ('i.fw', _('Firmware neu'), 'retry', ctx.confirm_fw_restart),
                ('i.redraw', _('Neu zeichnen'), 'monitor', ctx.redraw),
                ('i.shutdown', _('Ausschalten'), 'power', ctx.confirm_shutdown)]
        bw = (AREA.w - 8) // 2
        for i, (tid, label, icon, act) in enumerate(btns):
            rr = Rect(AREA.x + (i % 2) * (bw + 8), 222 + (i // 2) * 72, bw, 64)
            pr = ctx.pressed == tid
            dis = busy and tid != 'i.redraw'
            kind = 'disabled' if dis else ('danger' if tid == 'i.shutdown' else 'secondary')

            def paint_b(c, r, label=label, kind=kind, pr=pr, icon=icon):
                W.button(c, r, label, kind, icon if kind != 'disabled' else None, 'bg',
                         pressed=pr)
            frame.region('b.' + tid, rr, (label, kind, pr), paint_b)
            if not dis:
                frame.target(tid, rr, act)

        def paint_note(c, r):
            c.icon('info', r.x, r.y - 1, 20, 'text3', 'bg')
            c.text(r.x + 28, r.y, r.w - 28, 18, _('Updates: über die Weboberfläche bzw. git pull '
                                                  'im qbdisplay-Verzeichnis'), F.CAP, 'text3', 'bg')
        frame.region('note', Rect(AREA.x, 446, AREA.w, 20), 0, paint_note)
