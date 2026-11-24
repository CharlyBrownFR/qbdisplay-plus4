# qbdisplay – WLAN: Netzliste und Passwort-Tastatur
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""System › Netzwerk › Ändern: Netze in Reichweite, Antippen öffnet die
Bildschirmtastatur. Verbunden wird über das Hilfsskript; klappt es nicht, bleibt
das bisherige WLAN aktiv."""

from .. import fonts as F
from .. import i18n
from .. import wifi
from ..i18n import _, N_
from ..canvas import Rect
from . import widgets as W
from .chrome import Page
from .dialogs import Dialog

KIND_TEXT = {
    'psk': N_('Passwort'),
    'open': N_('Offen, ohne Passwort'),
    'wep': N_('WEP - veraltet, nicht unterstützt'),
    'sae': N_('Nur WPA3 - vom WLAN-Stick nicht unterstützt'),
    'eap': N_('Firmen-WLAN - nicht unterstützt'),
}
SUPPORTED = ('psk', 'open')
PER_PAGE = 5


def bars(c, x, y, n, on, under):
    """Signalstärke als 4 Balken (unten bündig, Höhe 20)."""
    for i in range(4):
        h = 6 + i * 5
        c.fill(x + i * 7, y + 20 - h, 5, h, on if i < n else 'line')


class WifiPage(Page):
    section = 'system'
    title = N_('WLAN')

    def build_content(self, frame):
        ctx = self.ctx
        ws = ctx.wifi
        net = ctx.net
        top = Rect(100, 52, 684, 72)
        conn = ws.get('connecting')
        if conn:
            l1, l2, tone = _('Verbinde mit %s ...') % conn, _('Dauert bis zu 1 min'), 'warn'
        elif net.get('iface_kind') == 'wifi':
            cur = ws.get('current') or ''
            l1 = (_('Verbunden mit %s') % cur) if cur else _('WLAN verbunden')
            l2, tone = 'IP %s' % (net.get('ip') or '-'), 'ok'
        elif net.get('iface_kind') == 'ethernet':
            l1, l2, tone = _('Über Kabel verbunden'), 'IP %s' % (net.get('ip') or '-'), 'ok'
        else:
            l1, l2, tone = _('Nicht verbunden'), '', 'err'
        b_back = Rect(top.x2 - 12 - 112, top.y + 12, 112, 48)
        b_scan = Rect(b_back.x - 8 - 112, top.y + 12, 112, 48)

        def paint_top(c, r):
            W.tile(c, r)
            if tone != 'err':     # das Icon gibt es nur in Grün
                c.icon('wifi', r.x + 16, r.y + 14, 22, 'ok', 'surface')
            tw = b_scan.x - r.x - 64
            c.text(r.x + 48, r.y + 12, tw, 24, l1, F.BTN, 'text', 'surface')
            c.text(r.x + 48, r.y + 42, tw, 18, l2, F.CAP, 'text3', 'surface')
        frame.region('w.top', top, (l1, l2, tone), paint_top)
        busy = bool(conn) or ws.get('state') == 'scanning'
        for tid, rr, label, act in (('w.scan', b_scan, _('Suchen'), ctx.wifi_scan),
                                    ('w.back', b_back, _('Zurück'),
                                     (lambda: ctx.go('system', sys_sub='network')))):
            dis = busy and tid == 'w.scan'
            pr = ctx.pressed == tid
            kind = 'disabled' if dis else 'secondary'

            def paint_b(c, r, label=label, kind=kind, pr=pr):
                W.button(c, r, label, kind, None, 'surface', fid=F.LBL, pressed=pr)
            frame.region(tid, rr, (label, kind, pr), paint_b, clear='surface')
            if not dis:
                frame.target(tid, rr, act)

        area = Rect(100, 136, 684, 332)
        state = ws.get('state')
        nets = ws.get('nets') or []
        msg = None
        if ws.get('error') == 'old_helper':
            msg = (_('Hilfsskript veraltet'),
                   _('Bitte einmal ./install.sh von Hand ausführen (wie bei der Installation), '
                     'danach geht WLAN am Display.'))
        elif state == 'scanning' and not nets:
            msg = (_('Suche Netze ...'), _('Dauert ein paar Sekunden.'))
        elif ws.get('error'):
            msg = (_('Suche fehlgeschlagen'), _('Bitte später erneut versuchen.'))
        elif state == 'done' and not nets:
            msg = (_('Keine Netze gefunden'), _('Der WLAN-Stick empfängt nur 2,4 GHz.'))
        if msg:
            def paint_msg(c, r):
                W.tile(c, r)
                c.text(r.x + 20, r.y + 20, r.w - 40, 28, msg[0], F.TITLE, 'text', 'surface')
                W.text_lines(c, r.x + 20, r.y + 60, r.w - 40, msg[1], F.TEXT, 'text2', 'surface',
                             max_lines=3)
            frame.region('w.msg', Rect(area.x, area.y, area.w, 140), msg, paint_msg)
            return

        page = ws.get('page', 0)
        if len(nets) > PER_PAGE:
            n = PER_PAGE - 1
            pages = (len(nets) + n - 1) // n
            page %= pages
            shown = nets[page * n:(page + 1) * n]
            more = (page, pages)
        else:
            shown, more = nets, None
        for i, nw in enumerate(shown):
            self._row(frame, i, Rect(area.x, area.y + i * 66, area.w, 58), nw, bool(conn))
        if more:
            rr = Rect(area.x, area.y + (PER_PAGE - 1) * 66, area.w, 58)
            pr = ctx.pressed == 'w.more'
            label = _('Weitere Netze (Seite %d von %d)') % (more[0] + 1, more[1])

            def paint_more(c, r):
                W.button(c, r, label, 'secondary', None, 'bg', fid=F.LBL, pressed=pr,
                         label_fg='text2')
            frame.region('w.more', rr, (label, pr), paint_more)
            frame.target('w.more', rr, (lambda: ctx.wifi_set(page=more[0] + 1)))

    def _row(self, frame, i, rect, nw, busy):
        ctx = self.ctx
        tid = 'w.n%d' % i
        pr = ctx.pressed == tid
        ok = nw.get('kind') in SUPPORTED
        cur = bool(nw.get('current'))
        n = wifi.signal_bars(nw.get('signal'))
        ghz = '5 GHz' if (nw.get('freq') or 0) > 4000 else '2.4 GHz'
        sub = '%s · %s' % (_(KIND_TEXT.get(nw.get('kind'), KIND_TEXT['psk'])),
                           i18n.decimal(ghz))
        name = nw.get('ssid', '')

        def paint(c, r):
            W.tile(c, r, border='accent' if pr else ('ok' if cur else 'line'), bw=2 if pr else 1)
            bars(c, r.x + 16, r.cy - 10, n, 'ok' if cur else ('accent' if ok else 'text3'),
                 'surface')
            tw = r.w - 64 - 150
            c.text(r.x + 60, r.y + 8, tw, 24, name, F.BTN, 'text' if ok else 'text2', 'surface')
            c.text(r.x + 60, r.y + 34, tw, 18, sub, F.CAP, 'text3', 'surface')
            if cur:
                W.chip(c, r.x2 - 16, r.cy - 13, _('verbunden'), 'ready', 'surface', right=True)
            elif ok:
                c.icon('chev', r.x2 - 36, r.cy - 10, 20, 'text3', 'surface')
        frame.region(tid, rect, (name, sub, n, ok, cur, pr), paint)
        if not busy:
            frame.target(tid, rect, (lambda: ctx.wifi_pick(nw)))


# ---------------------------------------------------------------------------
# Bildschirmtastatur
LAYOUTS = {
    'qwertz': ['1234567890', 'qwertzuiop', 'asdfghjkl-', 'yxcvbnm_.@'],
    'qwerty': ['1234567890', 'qwertyuiop', 'asdfghjkl-', 'zxcvbnm_.@'],
}
SYMBOLS = ['1234567890', '!"#$%&\'()*', '+,-./:;<=>', '?@[\\]^_`{|']
SYMBOLS_EXTRA = '}~'
# Zeichen, die als TJC-Text nicht gesendet werden können -> als Linien zeichnen
DRAWN = '"\\'


def draw_text(c, x, y, h, text, fid, fg, bg):
    """Text 1:1 (auch '"' und '\\', die der TJC-Befehl nicht transportiert). -> rechte Kante"""
    seg = ''
    for ch in text + '\0':
        if ch in DRAWN or ch == '\0':
            if seg:
                w = F.measure(seg, fid)
                c.text(x, y, w + 2, h, seg, fid, fg, bg, 'left', ellipsis=False)
                x += w
                seg = ''
            if ch == '\0':
                break
            w = F.char_width(ch, fid)
            th = F.height(fid)
            top = y + (h - th) // 2 + th // 5
            if ch == '"':
                c.fill(x + w // 2 - 3, top, 2, th // 4, fg)
                c.fill(x + w // 2 + 1, top, 2, th // 4, fg)
            else:
                c.thick_line(x + 1, top, x + w - 2, top + th * 3 // 5, 2, fg)
            x += w
        else:
            seg += ch
    return x


def text_width(text, fid):
    return sum(F.char_width(ch, fid) for ch in text)


class PasswordDialog(Dialog):
    box = Rect(0, 0, 800, 480)
    fullscreen = True
    MAXLEN = 63

    def __init__(self, ctx, ssid):
        Dialog.__init__(self, ctx)
        self.ssid = ssid
        self.text = ''
        self.shift = 'off'      # off | once | lock
        self.sym = False
        self.show = True
        self.layer = ('wifi_pw', ssid)

    # --- Eingabe ---------------------------------------------------------
    def type(self, ch):
        if len(self.text) < self.MAXLEN:
            self.text += ch
        if self.shift == 'once':
            self.shift = 'off'
        self.ctx.request_render()

    def backspace(self):
        self.text = self.text[:-1]
        self.ctx.request_render()

    def toggle_shift(self):
        self.shift = {'off': 'once', 'once': 'lock', 'lock': 'off'}[self.shift]
        self.sym = False
        self.ctx.request_render()

    def toggle_sym(self):
        self.sym = not self.sym
        self.ctx.request_render()

    def toggle_show(self):
        self.show = not self.show
        self.ctx.request_render()

    def rows(self):
        if self.sym:
            return SYMBOLS
        layout = LAYOUTS['qwertz' if i18n.get_language() == 'de' else 'qwerty']
        if self.shift != 'off':
            return [r if k == 0 else r.upper() for k, r in enumerate(layout)]
        return layout

    def submit(self):
        if not wifi.valid_psk(self.text):
            return
        self.ctx.close_dialog()
        self.ctx.wifi_connect(self.ssid, self.text)

    # --- Zeichnen --------------------------------------------------------
    def build(self, frame):
        ctx = self.ctx
        b = self.box
        valid = wifi.valid_psk(self.text)

        def paint_t(c, r):
            c.text(r.x, r.y, r.w, 22, W.caps(_('WLAN-Passwort')), F.CAP, 'text3', 'surface')
            c.text(r.x, r.y + 20, r.w, 30, self.ssid, F.TITLE, 'text', 'surface')
        bx = b.x2 - 20
        r_ok = Rect(bx - 156, b.y + 16, 156, 52)
        r_no = Rect(r_ok.x - 8 - 136, b.y + 16, 136, 52)
        frame.region('dlg.title', Rect(b.x + 24, b.y + 16, r_no.x - b.x - 36, 52), self.ssid,
                     paint_t, clear='surface')
        self._key(frame, 'no', r_no, _('Abbrechen'), ctx.close_dialog, F.LBL)
        self._key(frame, 'ok', r_ok, _('Verbinden'), self.submit, F.LBL,
                  kind='primary' if valid else 'disabled')

        field = Rect(b.x + 20, b.y + 80, b.w - 40 - 136, 56)
        shown = self.text if self.show else '*' * len(self.text)
        n = len(self.text)
        hint = ('%d' % n) if n >= 8 else (_('noch %d Zeichen') % (8 - n))

        def paint_f(c, r):
            c.box(r, 12, 'bg', 'accent', 2)
            fid = F.VAL
            hw = F.measure(hint, F.CAP) + 8
            avail = r.w - 32 - hw - 8
            s = shown
            pre = ''
            while s and text_width(s, fid) > avail - (F.measure('...', fid) if pre else 0):
                s = s[1:]
                pre = '...'
            x = r.x + 16
            if pre:
                x = c.label(x, r.y + 12, pre, fid, 'text3', 'bg', h=32)
            x = draw_text(c, x, r.y + 12, 32, s, fid, 'text', 'bg')
            c.fill(x + 2, r.y + 14, 2, 28, 'accent')
            c.label_right(r.x2 - 14, r.y + 19, hint, F.CAP, 'ok' if valid else 'text3', 'bg')
        frame.region('dlg.field', field, (shown, hint, valid), paint_f, clear='surface',
                     gaps=True)
        self._key(frame, 'show', Rect(field.x2 + 8, field.y, 128, 56),
                  _('Verbergen') if self.show else _('Zeigen'), self.toggle_show, F.LBL)

        # Tasten
        gap = 6
        kw = (b.w - 40 - 9 * gap) // 10
        x0 = b.x + 20 + (b.w - 40 - 10 * kw - 9 * gap) // 2
        y0 = field.y2 + 14
        kh = 56
        for ri, row in enumerate(self.rows()):
            for ci, ch in enumerate(row):
                rr = Rect(x0 + ci * (kw + gap), y0 + ri * (kh + gap), kw, kh)
                self._ckey(frame, 'k%d_%d' % (ri, ci), rr, ch, (lambda ch=ch: self.type(ch)),
                           F.BTN)
        y = y0 + 4 * (kh + gap)
        u = kw + gap
        x = x0
        if self.sym:
            items = [('sym', 2, 'abc', self.toggle_sym, False),
                     ('space', 4, _('Leer'), (lambda: self.type(' ')), False)]
            items += [('x%d' % i, 1, ch, (lambda ch=ch: self.type(ch)), False)
                      for i, ch in enumerate(SYMBOLS_EXTRA)]
        else:
            items = [('shift', 2, 'ABC' if self.shift == 'off' else 'abc', self.toggle_shift,
                      self.shift == 'lock'),
                     ('sym', 2, '#+=', self.toggle_sym, False),
                     ('space', 4, _('Leer'), (lambda: self.type(' ')), False)]
        items += [('bs', 2, '', self.backspace, False)]
        for tid, units, label, act, on in items:
            rr = Rect(x, y, units * u - gap, kh)
            self._ckey(frame, tid, rr, label, act, F.LBL if len(label) > 1 else F.BTN, on=on,
                       arrow=tid == 'bs')
            x += units * u

    def _key(self, frame, tid, rr, label, act, fid, kind='secondary'):
        pr = self.ctx.pressed == tid

        def paint(c, r):
            W.button(c, r, label, kind, None, 'surface', fid=fid, pressed=pr)
        frame.region('dlg.' + tid, rr, (label, kind, pr), paint, clear='surface')
        if kind != 'disabled':
            frame.target(tid, rr, act)

    def _ckey(self, frame, tid, rr, label, act, fid, on=False, arrow=False):
        """Taste der Tastatur: bewusst schlicht (3 Flächen + Text), damit das Öffnen
        und Umschalten bei 115200 Baud schnell geht."""
        pr = self.ctx.pressed == tid
        face = 'accent' if pr else ('tint' if on else 'surface2')
        fg = 'on_accent' if pr else ('accent' if on else 'text')

        def paint(c, r):
            c.fill(r.x + 3, r.y, r.w - 6, r.h, face)
            c.fill(r.x + 1, r.y + 1, r.w - 2, r.h - 2, face)
            c.fill(r.x, r.y + 3, r.w, r.h - 6, face)
            if arrow:
                c.thick_line(r.cx - 11, r.cy, r.cx + 11, r.cy, 3, fg)
                c.thick_line(r.cx - 11, r.cy, r.cx - 3, r.cy - 8, 3, fg)
                c.thick_line(r.cx - 11, r.cy, r.cx - 3, r.cy + 8, 3, fg)
                return
            w = text_width(label, fid)
            draw_text(c, r.cx - w // 2, r.cy - F.height(fid) // 2, F.height(fid), label, fid,
                      fg, face)
        # deckt bis auf die Eckpixel alles ab; darunter liegt immer die Dialogfläche
        frame.region('dlg.' + tid, rr, (label, face, fg), paint, opaque=True)
        frame.target(tid, rr, act)
