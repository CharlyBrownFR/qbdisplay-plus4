# qbdisplay – Tests: Update am Display (Knopf, Rückfrage, Ergebnis nach dem Neustart)
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
import unittest
from unittest import mock

from tests import helpers  # noqa: F401
from qbdisplay import updates


def make_app():
    from tools import scenarios
    from qbdisplay.canvas import ListSink
    app = scenarios.make_app(ListSink())
    scenarios.s_system_update_available(app)
    app.render()
    return app


def tids(app):
    return [t.tid for t in app.frame.targets]


class UpdateUiTest(unittest.TestCase):
    def test_install_button_only_when_newer(self):
        app = make_app()
        self.assertIn('u.install', tids(app))
        app.update_info['self_newer'] = False
        app.mark_dirty()
        app.render()
        self.assertNotIn('u.install', tids(app))
        self.assertIn('u.search', tids(app))

    def test_no_install_while_printing(self):
        app = make_app()
        app.st.update({'print_stats': {'state': 'printing'}})
        app._status_changed()
        app.render()
        self.assertNotIn('u.install', tids(app))

    def test_confirm_then_started(self):
        app = make_app()
        with mock.patch.object(updates, 'install_release',
                               lambda repo, **k: ('started', (0, 4, 1))):
            app.confirm_install_update()
            app.dialog.on_ok()
            self.assertEqual(app.update_info['state'], 'installing')
            kind, data = app.events.get(timeout=5)
        app.handle(kind, data)
        self.assertEqual(app.update_info['state'], 'restarting')
        app.render()
        self.assertNotIn('u.search', tids(app))

    def test_manual_opens_info(self):
        app = make_app()
        app._update_installed(('manual', 'neues Hilfsskript'))
        self.assertEqual(type(app.dialog).__name__, 'InfoDialog')

    def test_result_after_restart_shown_once(self):
        app = make_app()
        cleared = []
        st = {'state': 'done', 'from': '0.4.0', 'to': '0.4.1'}
        with mock.patch.object(updates, 'read_status', lambda: st), \
                mock.patch.object(updates, 'clear_status', lambda: cleared.append(1)):
            app._update_result_shown = False
            app.handle('connected', None)
            app.handle('connected', None)
        self.assertEqual(cleared, [1])
        self.assertIn('0.4.1', app._toast[0])

    def test_result_waits_while_helper_running(self):
        # am Gerät: neuer Dienst verbindet sich, bevor das Hilfsskript 'done' schreibt
        app = make_app()
        t = [1000.0]
        app.clock = lambda: t[0]
        cleared = []
        st = {'state': 'running', 'from': '0.4.0', 'to': '0.4.1'}
        with mock.patch.object(updates, 'read_status', lambda: st), \
                mock.patch.object(updates, 'clear_status', lambda: cleared.append(1)):
            app._update_result_shown = False
            app.handle('connected', None)
            self.assertEqual(cleared, [])
            st['state'] = 'done'
            t[0] += 20
            app.tick()
        self.assertEqual(cleared, [1])
        self.assertIn('0.4.1', app._toast[0])
        self.assertIsNone(app._update_result_poll)

    def test_result_poll_gives_up(self):
        app = make_app()
        t = [1000.0]
        app.clock = lambda: t[0]
        with mock.patch.object(updates, 'read_status', lambda: {'state': 'running'}):
            app.show_update_result()
            for _i in range(200):
                t[0] += 3
                app.tick()
        self.assertIsNone(app._update_result_poll)


if __name__ == '__main__':
    unittest.main()
