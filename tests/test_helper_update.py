# qbdisplay – Tests: Update im Hilfsskript (systemd/qbdisplay-helper) in einer Sandbox
#
# Copyright (C) 2026  STRE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Spielt ``update``/``update-run`` mit Attrappen für systemctl, curl, sudo usw. durch.
Nichts davon berührt das System: alle Pfade liegen in einem Temp-Ordner."""
import os
import shutil
import subprocess
import tempfile
import unittest

from tests import helpers  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, 'systemd', 'qbdisplay-helper')
SERVICE = os.path.join(ROOT, 'systemd', 'qbdisplay.service')
BASH = shutil.which('bash')

STUBS = {
    # systemctl: protokolliert; "restart makerbase-client" = Display flasht (Datei weg)
    'systemctl': '''#!/bin/bash
echo "systemctl $*" >> "$SB/log"
if [ "$1" = restart ] && [ "$2" = makerbase-client ] && [ "${STUB_FLASH_FAIL:-0}" != 1 ]; then
  rm -f "$SB/root/800_480.tft"
fi
if [ "$1" = is-active ]; then [ "${STUB_ACTIVE:-1}" = 1 ]; exit; fi
exit 0
''',
    'curl': '#!/bin/bash\necho "{\\"print_stats\\": {\\"state\\": \\"${STUB_STATE:-standby}\\"}}"\n',
    'systemd-run': '#!/bin/bash\necho "systemd-run $*" >> "$SB/log"\n',
    'sudo': '#!/bin/bash\n[ "$1" = -u ] && shift 2\n"$@"\n',
    'sleep': '#!/bin/bash\nexit 0\n',
    'chown': '#!/bin/bash\nexit 0\n',
    'python3': '#!/bin/bash\ncat >/dev/null; exit 0\n',
}


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.chmod(path, mode)


@unittest.skipUnless(BASH, 'bash fehlt')
class HelperUpdateTest(unittest.TestCase):
    def setUp(self):
        self.sb = tempfile.mkdtemp().replace('\\', '/')
        self.addCleanup(shutil.rmtree, self.sb, True)
        sb = self.sb
        self.user = subprocess.run([BASH, '-c', 'id -un'], stdout=subprocess.PIPE,
                                   universal_newlines=True).stdout.strip()
        self.app = sb + '/home/qbdisplay'
        self.backup = sb + '/home/qbdisplay-backup'
        self.updates = sb + '/home/qbdisplay-updates'
        os.makedirs(self.backup)
        os.makedirs(sb + '/root')
        for name, text in STUBS.items():
            write(sb + '/bin/' + name, text, 0o755)
        with open(HELPER, encoding='utf-8') as f:
            src = f.read()
        # so wie install.sh es nach /usr/local/sbin legt (Vergleichsbasis für "manual")
        installed = (src.replace('@BACKUP@', self.backup).replace('@APPDIR@', self.app)
                     .replace('@USER@', self.user))
        write(sb + '/installed-helper', installed, 0o755)
        # die laufende Kopie zeigt nur mit Ziel-Display-Datei und SELF in die Sandbox
        run = (installed
               .replace('TFT_TARGET="/root/800_480.tft"', 'TFT_TARGET="%s/root/800_480.tft"' % sb)
               .replace('SELF="/usr/local/sbin/qbdisplay-helper"',
                        'SELF="%s/installed-helper"' % sb))
        write(sb + '/helper', run, 0o755)
        self.make_pkg(self.app, '0.4.0', b'TFT-A')
        with open(self.backup + '/installed-tft.sha256', 'w') as f:
            f.write(self.sha(self.app + '/qbdisplay.tft'))

    def read(self, path):
        with open(path, encoding='utf-8') as f:
            return f.read().strip()

    def sha(self, path):
        import hashlib
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def make_pkg(self, path, version, tft, helper=None, service=None):
        write(path + '/install.sh', '#!/bin/bash\n', 0o755)
        write(path + '/qbdisplay/__init__.py', '__version__ = "%s"\n' % version)
        with open(path + '/qbdisplay.tft', 'wb') as f:
            f.write(tft)
        with open(HELPER, encoding='utf-8') as f:
            write(path + '/systemd/qbdisplay-helper', helper or f.read(), 0o755)
        with open(SERVICE, encoding='utf-8') as f:
            write(path + '/systemd/qbdisplay.service', service or f.read())
        return path

    def run_helper(self, *args, **env):
        e = dict(os.environ, SB=self.sb, PATH=self.sb + '/bin:' + os.environ.get('PATH', ''))
        e.update({k: str(v) for k, v in env.items()})
        return subprocess.run([BASH, self.sb + '/helper'] + list(args), env=e,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True)

    def status(self):
        with open(self.backup + '/update-status', encoding='utf-8') as f:
            return dict(line.split('=', 1) for line in f.read().splitlines())

    def log(self):
        try:
            with open(self.sb + '/log', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ''

    def version(self, path):
        with open(path + '/qbdisplay/__init__.py', encoding='utf-8') as f:
            return f.read().split('"')[1]

    # ------------------------------------------------------------------
    def test_update_same_tft_no_flash(self):
        new = self.make_pkg(self.updates + '/qbdisplay-plus4-0.4.1', '0.4.1', b'TFT-A')
        r = self.run_helper('update', new)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('systemd-run --unit=qbdisplay-update', self.log())
        r = self.run_helper('update-run', new)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.version(self.app), '0.4.1')
        self.assertEqual(self.version(self.app + '-alt-0.4.0'), '0.4.0')
        self.assertNotIn('makerbase-client', self.log())
        st = self.status()
        self.assertEqual((st['state'], st['from'], st['to']), ('done', '0.4.0', '0.4.1'))

    def test_update_new_tft_flashes(self):
        new = self.make_pkg(self.updates + '/qbdisplay-plus4-0.5.0', '0.5.0', b'TFT-B')
        r = self.run_helper('update-run', new)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('systemctl restart makerbase-client', self.log())
        self.assertEqual(self.read(self.backup + '/installed-tft.sha256'),
                         self.sha(self.app + '/qbdisplay.tft'))
        self.assertEqual(self.status()['state'], 'done')

    def test_start_fails_rolls_back(self):
        new = self.make_pkg(self.updates + '/qbdisplay-plus4-0.5.0', '0.5.0', b'TFT-B')
        r = self.run_helper('update-run', new, STUB_ACTIVE=0)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.version(self.app), '0.4.0')
        self.assertEqual(self.version(self.app + '.failed'), '0.5.0')
        # alte Display-Datei wieder aufgespielt und vermerkt
        self.assertEqual(self.log().count('restart makerbase-client'), 2)
        self.assertEqual(self.read(self.backup + '/installed-tft.sha256'),
                         self.sha(self.app + '/qbdisplay.tft'))
        st = self.status()
        self.assertEqual(st['state'], 'failed')
        self.assertEqual((st['from'], st['message']), ('0.4.0', 'qbdisplay 0.5.0 startet nicht'))

    def test_flash_fails_rolls_back(self):
        new = self.make_pkg(self.updates + '/qbdisplay-plus4-0.5.0', '0.5.0', b'TFT-B')
        r = self.run_helper('update-run', new, STUB_FLASH_FAIL=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.version(self.app), '0.4.0')
        self.assertEqual(self.status()['state'], 'failed')

    def test_refuses_outside_update_dir(self):
        new = self.make_pkg(self.sb + '/elsewhere/qbdisplay-plus4-0.5.0', '0.5.0', b'X')
        r = self.run_helper('update', new)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('nicht unter', r.stdout)
        self.assertNotIn('systemd-run', self.log())

    def test_refuses_while_printing(self):
        new = self.make_pkg(self.updates + '/qbdisplay-plus4-0.5.0', '0.5.0', b'X')
        r = self.run_helper('update', new, STUB_STATE='printing')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Druck', r.stdout)

    def test_changed_helper_needs_manual_install(self):
        new = self.make_pkg(self.updates + '/qbdisplay-plus4-0.5.0', '0.5.0', b'X',
                            helper='#!/bin/bash\nwhoami\n')
        r = self.run_helper('update', new)
        self.assertEqual(r.returncode, 3)
        self.assertIn('manual', r.stdout)
        self.assertNotIn('systemd-run', self.log())

    def test_changed_service_needs_manual_install(self):
        new = self.make_pkg(self.updates + '/qbdisplay-plus4-0.5.0', '0.5.0', b'X',
                            service='[Service]\nUser=root\n')
        r = self.run_helper('update', new)
        self.assertEqual(r.returncode, 3)

    def test_missing_file(self):
        new = self.make_pkg(self.updates + '/qbdisplay-plus4-0.5.0', '0.5.0', b'X')
        os.remove(new + '/qbdisplay.tft')
        r = self.run_helper('update', new)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('qbdisplay.tft fehlt', r.stdout)


if __name__ == '__main__':
    unittest.main()
