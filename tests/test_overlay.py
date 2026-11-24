# qbdisplay – Tests: Dialoge schweben über der stehenden Seite
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.

import os
import tempfile
import unittest

from tests import helpers  # noqa: F401


def pixels(sim):
    fd, path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        sim.save(path)
        from PIL import Image
        with Image.open(path) as im:
            return im.convert('RGB').tobytes()
    finally:
        os.remove(path)


class OverlayTest(unittest.TestCase):
    def setUp(self):
        from tools import scenarios
        from qbdisplay.sim import Simulator
        self.scenarios = scenarios
        self.sim = Simulator()
        self.app = scenarios.make_app(self.sim)
        scenarios.s_move_unhomed(self.app)
        self.app.render()

    def fresh(self, setup):
        from qbdisplay.sim import Simulator
        sim = Simulator()
        app = self.scenarios.make_app(sim)
        setup(app)
        app.render()
        return pixels(sim)

    def test_open_draws_only_the_dialog(self):
        page = self.sim.commands
        self.sim.reset_stats()
        self.app.confirm_free_move()
        self.app.render()
        self.assertLess(self.sim.commands, page // 4)
        self.sim.reset_stats()
        self.app.render()
        self.assertEqual(self.sim.commands, 0)

    def test_close_restores_page_exactly(self):
        self.app.confirm_free_move()
        self.app.render()
        self.app.close_dialog()
        self.app.render()
        self.assertEqual(pixels(self.sim), self.fresh(self.scenarios.s_move_unhomed))

    def test_page_value_changed_behind_dialog(self):
        self.app.confirm_free_move()
        self.app.render()
        self.app.st.update({'extruder': {'temperature': 123.0}})
        self.app._status_changed()
        self.sim.reset_stats()
        self.app.render()
        self.assertEqual(self.sim.commands, 0)          # Seite steht still
        self.app.close_dialog()
        self.app.render()

        def setup(app):
            self.scenarios.s_move_unhomed(app)
            app.st.update({'extruder': {'temperature': 123.0}})
            app._status_changed()
        self.assertEqual(pixels(self.sim), self.fresh(setup))

    def test_dialog_to_dialog_and_back(self):
        self.app.confirm_free_move()
        self.app.render()
        self.app.info('Hinweis', 'Kurzer Text')
        self.app.render()
        self.app.close_dialog()
        self.app.render()
        self.assertEqual(pixels(self.sim), self.fresh(self.scenarios.s_move_unhomed))

    def test_leaving_page_from_dialog(self):
        self.app.confirm_free_move()
        self.app.render()
        self.app.close_dialog()
        self.app.go('home')
        self.app.render()
        self.assertEqual(pixels(self.sim), self.fresh(self.scenarios.s_home_idle))

    def test_redraw_while_dialog_open(self):
        self.app.confirm_free_move()
        self.app.render()
        self.app.redraw()
        self.app.render()
        self.app.close_dialog()
        self.app.render()
        self.assertEqual(pixels(self.sim), self.fresh(self.scenarios.s_move_unhomed))


if __name__ == '__main__':
    unittest.main()
