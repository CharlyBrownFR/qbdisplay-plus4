# qbdisplay – Filament/QIDI Box und Slot bearbeiten
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Entwurf 3 (Box) und 4 (Slot bearbeiten).

Befehle (über qidi_box_compat.cfg auf Happy Hare abgebildet):
E_LOAD SLOT=slotN, E_UNLOAD, E_BOX SLOT=slotN, RFID_READ SLOT=slotN,
SAVE_VARIABLE VARIABLE=filament_slotN|color_slotN|vendor_slotN.
"""

from .. import colors
from .. import fonts as F
from .. import model
from ..i18n import _, N_
from ..canvas import Rect
from . import widgets as W
from .chrome import Page

STATE_CHIP = {
    'loaded': (N_('In Düse'), 'loaded'),
    'ready': (N_('Bereit'), 'ready'),
    'loading': (N_('Lädt ...'), 'loading'),
    'unloading': (N_('Entlädt'), 'loading'),
    'empty': (N_('Leer'), 'empty'),
    'unknown': ('?', 'off'),
}


def card_texts(s):
    """(Titel, Untertitel, Bereich, Titelfarbe) einer Slot-Karte."""
    if s.index == model.HH_GATE_BYPASS:
        if s.material:
            return (s.name, s.color_name or _('Spule hinten'),
                    _('In Düse') if s.state == 'loaded' else model.temp_range_text(s.temps),
                    'text')
        return (_('Extern'), _('Spule hinten'),
                _('In Düse') if s.state == 'loaded' else _('nicht belegt'), 'text2')
    if s.state == 'empty':
        return _('Leer'), _('Spule einlegen'), _('wird erkannt'), 'text2'
    if not (s.name or s.material):
        return _('Ohne Material'), _('bitte zuordnen'), '', 'text2'
    sub = s.color_name or (s.color or '')
    if s.state == 'unknown':
        sub = _('Zustand unbekannt')
    return s.name or s.material, sub, model.temp_range_text(s.temps), 'text'


def paint_card(c, r, s, selected, accent):
    empty = s.state == 'empty'
    face = 'tint' if selected else 'surface'
    if selected:
        W.glow_box(c, r, 14, face, 'accent', 'bg', halo=2, bw=2)
    elif empty:
        c.dashed_box(r, 14, 'line', bw=2, dash=8, gap=6, fill='surface')
    else:
        c.box(r, 14, face, 'line', 1)
    # Buchstabe
    is_rack = s.index == model.HH_GATE_BYPASS
    bw = (F.measure('RACK', F.CAP) + 16) if is_rack else 34
    badge = Rect(r.x + 10, r.y + 10, bw, 32)
    bfill = 'accent' if accent else ('surface3' if not selected else 'tint2')
    c.rr(badge, 9, bfill)
    c.text(badge.x, badge.y + (32 - (16 if is_rack else 24)) // 2, badge.w,
           16 if is_rack else 24, 'RACK' if is_rack else s.letter, F.CAP if is_rack else F.BTN,
           'on_accent' if accent else ('text3' if empty else 'text'), bfill, 'center')
    text, kind = STATE_CHIP.get(s.state, ('?', 'off'))
    W.chip(c, r.x2 - 10, r.y + 13, _(text), kind, face, fid=F.CAP, h=26, right=True)
    W.spool(c, r.cx, r.y + 90, 34, s.color, 'empty' if empty else s.state, face,
            accent_ring=accent, plus=(s.state == 'empty' and not is_rack))
    title, sub, rng, tfg = card_texts(s)
    c.text(r.x + 6, r.y + 132, r.w - 12, 24, title, F.BTN, tfg, face, 'center')
    c.text(r.x + 6, r.y + 158, r.w - 12, 20, sub, F.LBL, 'text2', face, 'center')
    c.text(r.x + 6, r.y + 182, r.w - 12, 18, rng, F.CAP, 'text3', face, 'center')


class BoxPage(Page):
    section = 'filament'
    title = N_('Filament')

    def build_content(self, frame):
        ctx = self.ctx
        if not ctx.has_box:
            self.build_external(frame)
            return
        units = ctx.box_units
        unit = ctx.ui.get('box_unit')
        if unit not in units:
            unit = units[0]
        lg = ctx.loaded_gate
        sel = ctx.ui.get('sel_slot')
        if sel is None:
            sel = lg if lg is not None else unit * 4
            if sel >= 0 and sel // 4 != unit:
                sel = unit * 4
        slots = [s for s in ctx.slots if s.index // 4 == unit]
        cards = [ctx.rack] + slots
        for i, s in enumerate(cards):
            rect = Rect(100 + i * 138, 52, 130, 216)
            selected = s.index == sel
            accent = lg == s.index and s.state == 'loaded'
            tid = 'card.%d' % s.index

            def paint(c, r, s=s, selected=selected, accent=accent):
                paint_card(c, r, s, selected, accent)
            frame.region(tid, rect, (tuple(s), selected, accent), paint)
            frame.target(tid, rect, (lambda g=s.index: ctx.set_ui(sel_slot=g)))
        cur = None
        for s in cards:
            if s.index == sel:
                cur = s
        if cur is None:
            cur = cards[1]
        self.build_actions(frame, cur, lg)
        self.build_climate(frame, unit, units)

    def build_external(self, frame):
        """Betrieb ohne QIDI Box: nur die externe Spule hinten am Drucker."""
        ctx = self.ctx
        s = ctx.rack
        lg = ctx.loaded_gate
        loaded = s.state == 'loaded'
        card = Rect(100, 52, 300, 416)
        title, sub, rng, tfg = card_texts(s)
        vendor = s.vendor or ''

        def paint_ext(c, r):
            if loaded:
                W.glow_box(c, r, 14, 'surface', 'accent', 'bg', halo=2, bw=2)
            else:
                W.tile(c, r)
            W.header(c, r, 'spool', _('Externe Spule'), x=r.x + 14)
            if loaded:
                W.chip(c, r.x2 - 14, r.y + 14, _('In Düse'), 'loaded', 'surface', fid=F.CAP,
                       h=26, right=True)
            W.spool(c, r.cx, r.y + 150, 64, s.color, 'loaded' if loaded else 'ready',
                    'surface', accent_ring=loaded)
            c.text(r.x + 10, r.y + 236, r.w - 20, 32, title, F.VAL, tfg, 'surface', 'center')
            c.text(r.x + 10, r.y + 274, r.w - 20, 20, ' · '.join(
                x for x in (sub, vendor) if x), F.LBL, 'text2', 'surface', 'center')
            c.text(r.x + 10, r.y + 300, r.w - 20, 18, model.temp_range_text(s.temps), F.CAP,
                   'text3', 'surface', 'center')
            c.fill(r.x + 14, r.y + 336, r.w - 28, 1, 'line')
            W.text_lines(c, r.x + 14, r.y + 350, r.w - 28,
                         _('Material und Farbe stellst du im Slicer oder in QIDIs '
                           'Weboberfläche ein.'), F.CAP, 'text3', 'surface', max_lines=3)
        frame.region('ext.card', card, (tuple(s), loaded), paint_ext)

        info = Rect(412, 52, 372, 196)

        def paint_info(c, r):
            W.tile(c, r)
            W.header(c, r, 'box', _('Keine QIDI Box verbunden'), x=r.x + 14)
            W.text_lines(c, r.x + 16, r.y + 54, r.w - 32,
                         _('Gedruckt wird von der Spule hinten am Drucker. Wird die Box '
                           'angesteckt, erkennt QIDI sie selbst und hier erscheinen '
                           'wieder ihre Slots.'), F.TEXT, 'text2', 'surface', max_lines=5)
        frame.region('ext.info', info, 'nobox', paint_info)
        self.build_actions(frame, s, lg, tile=Rect(412, 260, 372, 208), side=False)

    def build_actions(self, frame, s, lg, tile=None, side=True):
        ctx = self.ctx
        tile = tile or Rect(100, 280, 460, 188)
        printing = ctx.pstate in ('printing', 'paused', 'paused_error')
        is_rack = s.index == model.HH_GATE_BYPASS
        src = None
        if lg is not None and lg != s.index:
            src = ctx.rack if lg == model.HH_GATE_BYPASS else (
                ctx.slots[lg] if 0 <= lg < len(ctx.slots) else None)
        kind, label, icon, action = 'primary', _('%s in Düse laden') % s.letter, 'down', None
        if printing:
            kind, label, icon = 'disabled', _('Während Druck gesperrt'), None
            desc = _('Laden und Entladen sind gesperrt, solange ein Druck läuft.')
        elif s.state in ('loading', 'unloading'):
            kind, label, icon = 'disabled', _('Läuft ...'), None
            desc = _('Die Box arbeitet gerade. Bitte warten.')
        elif s.state == 'loaded':
            label, icon = _('Aus Düse entladen'), 'up'
            action = ctx.unload
            desc = (_('Die Düse heizt auf, das Filament wird aus dem Extruder gezogen. '
                      'Dauer ca. 1-2 min.') if is_rack else
                    _('Die Düse heizt auf, das Filament wird zurück in %s gezogen. '
                      'Dauer ca. 1-2 min.') % s.letter)
        elif is_rack:
            label = _('Rack in Düse laden')
            action = ctx.load_rack
            desc = _('Filament von der hinteren Spule bis zum Extruder einführen, dann laden.')
        elif s.state == 'empty':
            kind, label, icon = 'disabled', _('Slot leer'), None
            desc = _('Filament in Slot %s einlegen - die Box zieht es automatisch ein.') % s.letter
        else:
            action = (lambda: ctx.load_slot(s.index))
            if src is not None:
                desc = _('%s wird zuerst aus der Düse entladen, dann %s geladen und gespült. '
                         'Dauer ca. 3-4 min.') % (src.letter, s.letter)
            else:
                desc = _('%s wird bis in die Düse geladen und gespült. Dauer ca. 2 min.') % s.letter
        if is_rack:
            title = _('Rack · externe Spule')
        else:
            title = _('Slot %s · %s') % (s.letter, (('%s %s' % (s.name or s.material,
                                                                 s.color_name)).strip()
                                                    or _('ohne Material')))

        def paint_tile(c, r):
            W.tile(c, r)
            x = r.x + 16
            if s.color:
                W.color_dot(c, x + 11, r.y + 27, 11, s.color, 'surface')
                x += 32
            c.text(x, r.y + 15, r.x2 - 16 - x, 24, title, F.BTN, 'text', 'surface')
            W.text_lines(c, r.x + 16, r.y + 52, r.w - 32, desc, F.TEXT, 'text2', 'surface',
                         max_lines=2)
        frame.region('act', tile, (title, desc, s.color), paint_tile)
        can_edit = not is_rack
        can_eject = (not is_rack) and s.state in ('ready', 'loaded', 'unknown') and not printing
        pw = tile.w - 32 - (2 * 72 if side else 0)
        prim = Rect(tile.x + 16, tile.y2 - 14 - 64, pw, 64)
        pressed = ctx.pressed == 'act.main'

        def paint_prim(c, r):
            W.button(c, r, label, kind, icon, 'surface', pressed=pressed)
        frame.region('act.main', prim, (label, kind, pressed), paint_prim, clear='surface')
        if action is not None and kind != 'disabled':
            frame.target('act.main', prim, action)
        if not side:
            return
        for j, (tid, ic, ok, act) in enumerate((
                ('act.edit', 'edit', can_edit, lambda: ctx.open_slot_edit(s.index)),
                ('act.eject', 'eject', can_eject, lambda: ctx.confirm_eject(s.index)))):
            br = Rect(prim.x2 + 8 + j * 72, prim.y, 64, 64)
            pr = ctx.pressed == tid

            def paint_b(c, r, ic=ic, ok=ok, pr=pr):
                if ok:
                    W.button(c, r, '', 'secondary', ic, 'surface', pressed=pr)
                else:
                    W.button(c, r, '', 'disabled', None, 'surface')
                    c.icon(ic, r.cx - 12, r.cy - 12, 24, 'text3', 'surface')
            frame.region(tid, br, (ok, pr), paint_b, clear='surface')
            if ok:
                frame.target(tid, br, act)

    def build_climate(self, frame, unit=0, units=(0,)):
        ctx = self.ctx
        tile = Rect(572, 280, 212, 188)
        temp, target, hum, heating = ctx.unit_climate(unit)
        mats = [s.material for s in ctx.slots if s.state != 'empty' and s.index // 4 == unit]
        level, rating = model.humidity_rating(hum, mats)
        dv = ctx.drying
        multi = len(units) > 1
        can_dry = unit == 0     # Trocknung bisher nur für Box 1 (weitere ungetestet)
        if unit != 0:
            line = _('Trocknet') if heating else (rating if hum is not None else '')
        elif dv.active:
            line = _('Trocknet · noch %s') % model.fmt_duration(dv.remaining, 'clock') \
                if dv.known else _('Trocknung läuft')
        else:
            line = rating if hum is not None else _('Trocknung aus')
        hfg = {'ok': 'ok', 'warn': 'warn', 'err': 'err'}.get(level, 'text')

        btitle = _('Box %d') % (unit + 1)

        def paint(c, r):
            W.tile(c, r)
            W.header(c, r, 'box', btitle, x=r.x + 14)
            if multi:
                c.icon('chev', r.x2 - 14 - 20, r.y + 15, 20, 'accent', 'surface')
            x = W.value_unit(c, r.x + 14, r.y + 46, 32, model.fmt_temp(temp), ' °C', F.VAL,
                             F.LBL, 'text', 'surface')
            c.fill(x + 12, r.y + 52, 1, 24, 'line')
            W.value_unit(c, x + 26, r.y + 46, 32, model.fmt_temp(hum), ' %', F.VAL, F.LBL, hfg,
                         'surface')
            c.text(r.x + 14, r.y + 86, r.w - 28, 18, line, F.CAP,
                   'heat' if dv.active else ('warn' if level in ('warn', 'err') else 'text3'),
                   'surface')
        frame.region('clim', tile, (btitle, multi, model.fmt_temp(temp), model.fmt_temp(hum),
                                    line, hfg), paint)
        if multi:
            nxt = units[(units.index(unit) + 1) % len(units)]
            frame.target('clim.next', Rect(tile.x, tile.y, tile.w, 96),
                         (lambda u=nxt: ctx.set_ui(box_unit=u, sel_slot=None)))
        br = Rect(tile.x + 14, tile.y2 - 14 - 56, tile.w - 28, 56)
        if not can_dry and not multi:
            return
        if not can_dry:
            # weitere Boxen: statt Trocknen zur nächsten Box blättern
            prn = ctx.pressed == 'clim.next'

            def paint_n(c, r):
                W.button(c, r, _('Weiter: Box %d') % (nxt + 1), 'secondary', None, 'surface',
                         fid=F.BTN, pressed=prn)
            frame.region('dry', br, ('next', nxt, prn), paint_n, clear='surface')
            frame.target('clim.next', br, (lambda u=nxt: ctx.set_ui(box_unit=u, sel_slot=None)))
            return
        pr = ctx.pressed == 'dry'

        def paint_b(c, r):
            W.button(c, r, _('Trocknung') if dv.active else _('Trocknen'), 'secondary', 'sun', 'surface',
                     fid=F.BTN, pressed=pr, icon_fg='heat')
        frame.region('dry', br, (dv.active, pr), paint_b, clear='surface')
        frame.target('dry', br, (lambda: ctx.go('drying')))


# ---------------------------------------------------------------------------
class SlotEditPage(Page):
    section = 'filament'

    def page_title(self):
        e = self.ctx.ui.get('edit') or {}
        return _('Slot %s bearbeiten') % model.letter(e.get('slot', 0))

    @staticmethod
    def paged(ids, per_page, page):
        """-> (sichtbare ids, mehr-Kachel?) bei Platz für per_page Kacheln."""
        if len(ids) <= per_page:
            return ids, False
        n = per_page - 1
        pages = (len(ids) + n - 1) // n
        page %= pages
        return ids[page * n:(page + 1) * n], True

    def build_content(self, frame):
        ctx = self.ctx
        fl = ctx.flist
        e = ctx.ui.get('edit') or {}
        slot = e.get('slot', 0)
        fsel, csel, vsel = e.get('fil'), e.get('color'), e.get('vendor')

        def cap(rid, y, text):
            def paint(c, r):
                c.fill_rect(r, 'bg')
                W.caption(c, r.x, r.y, text, 'bg')
            frame.region(rid, Rect(100, y, 300, 18), text, paint, opaque=True)

        # Material
        cap('cap.mat', 52, _('Material'))
        fids, more = self.paged(fl.filament_ids(), 8, e.get('fpage', 0))
        tw = (464 - 3 * 8) // 4
        items = [('fil', i) for i in fids] + ([('more', None)] if more else [])
        for k, (kind, idx) in enumerate(items):
            rect = Rect(100 + (k % 4) * (tw + 8), 74 + (k // 4) * 64, tw, 56)
            tid = 'm.%d' % k
            pr = ctx.pressed == tid
            if kind == 'more':
                label, style = _('Weitere ...'), 'secondary'
                act = (lambda: ctx.edit_set(fpage=e.get('fpage', 0) + 1))
            else:
                label = fl.name(idx)
                style = 'selected' if idx == fsel else 'secondary'
                act = (lambda i=idx: ctx.edit_set(fil=i))

            def paint(c, r, label=label, style=style, pr=pr, kind=kind):
                W.button(c, r, label, style, None, 'bg', fid=F.LBL, pressed=pr,
                         label_fg='text2' if kind == 'more' else None)
            frame.region(tid, rect, (label, style, pr), paint)
            frame.target(tid, rect, act)

        # Farben
        cap('cap.col', 204, _('Farbe'))
        cids, more = self.paged(fl.color_ids(), 16, e.get('cpage', 0))
        cw = (464 - 7 * 8) // 8
        items = [('col', i) for i in cids] + ([('more', None)] if more else [])
        for k, (kind, idx) in enumerate(items):
            rect = Rect(100 + (k % 8) * (cw + 8), 226 + (k // 8) * 64, cw, 56)
            tid = 'c.%d' % k
            pr = ctx.pressed == tid
            if kind == 'more':
                def paint(c, r, pr=pr):
                    W.button(c, r, _('Mehr'), 'secondary', None, 'bg', fid=F.LBL, pressed=pr,
                             label_fg='text2')
                frame.region(tid, rect, ('more', pr), paint)
                frame.target(tid, rect, (lambda: ctx.edit_set(cpage=e.get('cpage', 0) + 1)))
                continue
            col = fl.colors[idx]
            on = idx == csel

            def paint(c, r, col=col, on=on, pr=pr):
                W.button(c, r, '', 'selected' if on else 'secondary', None, 'bg', pressed=pr)
                face = W.BTN_STYLES['selected' if on else 'secondary'][0]
                W.color_dot(c, r.cx, r.cy, 17, col, face,
                            ring=colors.luminance(col) < 0.12 or on)
                if on:
                    mark = 'white' if colors.luminance(col) < 0.5 else 'black'
                    c.thick_line(r.cx - 8, r.cy, r.cx - 3, r.cy + 6, 3, mark)
                    c.thick_line(r.cx - 3, r.cy + 6, r.cx + 8, r.cy - 6, 3, mark)
            frame.region(tid, rect, (col, on, pr), paint)
            frame.target(tid, rect, (lambda i=idx: ctx.edit_set(color=i)))

        # Hersteller
        cap('cap.ven', 356, _('Hersteller'))
        vids = fl.vendor_ids()
        names = [self.vendor_name(fl.vendors[v]) for v in vids]
        # QIDI zuerst, dann Generisch, Rest über "Andere"
        order = sorted(range(len(vids)), key=lambda k: (names[k] != 'QIDI', names[k] != _('Generisch'), k))
        main = order[:2]
        rest = order[2:]
        seg_items = [names[k] for k in main]
        seg_ids = [vids[k] for k in main]
        if rest:
            cur_rest = [k for k in rest if vids[k] == vsel]
            k = cur_rest[0] if cur_rest else None
            seg_items.append((names[k] if k is not None else _('Andere')) + ' ...')
            seg_ids.append(vids[k] if k is not None else None)
        selected = seg_ids.index(vsel) if vsel in seg_ids else -1
        srect = Rect(100, 378, 464, 62)
        rects_holder = []

        def paint_seg(c, r):
            rects_holder[:] = W.seg(c, r, seg_items, selected)
        frame.region('seg', srect, (tuple(seg_items), selected), paint_seg)
        n = len(seg_items)
        sw = (srect.w - 8 - 4 * (n - 1)) / float(max(1, n))
        for k in range(n):
            rr = Rect(srect.x + 4 + k * (sw + 4), srect.y + 4, sw, srect.h - 8)
            if k < len(main):
                act = (lambda v=seg_ids[k]: ctx.edit_set(vendor=v))
            else:
                def act(rest=rest):
                    ids = [vids[j] for j in rest]
                    cur = ids.index(vsel) if vsel in ids else -1
                    ctx.edit_set(vendor=ids[(cur + 1) % len(ids)])
            frame.target('v.%d' % k, rr, act)

        # Vorschau
        prev = Rect(576, 52, 208, 280)
        name = fl.name(fsel) if fsel is not None else _('Kein Material')
        col = fl.colors.get(csel) if csel is not None else None
        vend = self.vendor_name(fl.vendors.get(vsel, '')) if vsel is not None else ''
        sub = ' · '.join(x for x in (colors.color_name(col) if col else '', vend) if x)
        rng = model.temp_range_text(fl.temp_range(fsel)) if fsel is not None else ''
        dry = ctx.drying_temp_for(fl.ftype(fsel)) if fsel is not None else None
        line3 = ' · '.join(x for x in (rng, (_('Trocknen %d °C') % dry) if dry else '') if x)

        def paint_prev(c, r):
            W.tile(c, r)
            W.caption(c, r.x + 14, r.y + 14, _('Vorschau Slot %s') % model.letter(slot), 'surface')
            W.spool(c, r.cx, r.y + 90, 40, col, 'ready' if col else 'empty', 'surface')
            c.text(r.x + 8, r.y + 140, r.w - 16, 24, name, F.BTN, 'text', 'surface', 'center')
            c.text(r.x + 8, r.y + 168, r.w - 16, 20, sub, F.LBL, 'text2', 'surface', 'center')
            W.text_lines(c, r.x + 10, r.y + 196, r.w - 20, line3, F.CAP, 'text3', 'surface',
                         max_lines=2)
        frame.region('prev', prev, (name, col, sub, line3), paint_prev)

        rf = Rect(576, 344, 208, 56)
        pr = ctx.pressed == 'rfid'

        def paint_rfid(c, r):
            W.button(c, r, _('RFID lesen'), 'secondary', 'rfid', 'bg', pressed=pr)
        frame.region('rfid', rf, pr, paint_rfid)
        frame.target('rfid', rf, (lambda: ctx.read_rfid(slot)))
        xr = Rect(576, 412, 64, 56)
        pr = ctx.pressed == 'cancel'

        def paint_x(c, r):
            W.button(c, r, '', 'secondary', 'x', 'bg', pressed=pr)
        frame.region('cancel', xr, pr, paint_x)
        frame.target('cancel', xr, (lambda: ctx.go('filament')))
        sv = Rect(648, 412, 136, 56)
        ok = fsel is not None and csel is not None
        pr = ctx.pressed == 'save'

        def paint_save(c, r):
            W.button(c, r, _('Speichern'), 'primary' if ok else 'disabled', None, 'bg', pressed=pr)
        frame.region('save', sv, (ok, pr), paint_save)
        if ok:
            frame.target('save', sv, (lambda: ctx.save_slot(slot, fsel, csel, vsel)))

    @staticmethod
    def vendor_name(name):
        return {'generic': _('Generisch')}.get((name or '').lower(), name or '')
