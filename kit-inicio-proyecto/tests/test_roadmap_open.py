from __future__ import annotations

import contextlib
import io
import json
import runpy
import sys
import threading
from unittest.mock import patch
from urllib.request import urlopen

from test_kit import KIT, PlanFixture, initializer, task
from roadmap import main
from roadmap_server import create_server


class OpenTest(PlanFixture):
    def test_live_open_uses_a_free_port_and_publishes_before_browser_reads(self):
        opened, errors, servers = [], [], []
        finished = threading.Event()

        def capture_server(monitor, port):
            self.assertEqual(0, port)
            server = create_server(monitor, port)
            servers.append(server)
            return server

        def browser(url, **options):
            try:
                opened.append(url)
                with urlopen(url + '__roadmap__/data', timeout=3) as response:
                    graph = json.load(response)
                self.assertEqual(str(self.root.resolve()), graph['projectPath'])
                self.assertFalse(graph['live']['allowEdit'])
                self.source.write_text(task(title='Actualización desde el editor'), encoding='utf-8')
                with urlopen(url, timeout=3) as response:
                    self.assertIn(b'roadmap-data', response.read())
            except BaseException as error:
                errors.append(error)
            finally:
                servers[0].shutdown()
                finished.set()
            return True

        with patch('roadmap_server.create_server', side_effect=capture_server), patch('webbrowser.open', side_effect=browser):
            result = main(['open', '--root', str(self.root), '--output', str(self.plan / 'Mi árbol.html')])
            self.assertTrue(finished.wait(5))
        self.assertEqual([], errors)
        self.assertEqual(0, result)
        self.assertEqual([f'http://127.0.0.1:{servers[0].server_port}/'], opened)
        self.assertNotEqual(0, servers[0].server_port)

    def test_static_open_needs_no_server_and_preserves_specifications(self):
        before = self.source.read_bytes()
        with patch('webbrowser.open', return_value=True) as browser, patch('roadmap_server.create_server') as server:
            self.assertEqual(0, main(['open', '--static', '--root', str(self.root)]))
        server.assert_not_called()
        browser.assert_called_once_with(self.output.resolve().as_uri(), new=2)
        self.assertEqual(before, self.source.read_bytes())
        self.assertNotIn('"live":', self.output.read_text(encoding='utf-8'))

    def test_invalid_plan_neither_opens_browser_nor_replaces_existing_export(self):
        self.output.write_bytes(b'exportacion previa')
        self.source.write_text(task(dependencies='QA-999'), encoding='utf-8')
        with patch('webbrowser.open') as browser, self.assertRaises(SystemExit) as error:
            main(['open', '--static', '--root', str(self.root)])
        self.assertEqual(1, error.exception.code)
        browser.assert_not_called()
        self.assertEqual(b'exportacion previa', self.output.read_bytes())

    def test_browser_failure_prints_a_usable_link(self):
        with patch('webbrowser.open', return_value=False), contextlib.redirect_stdout(io.StringIO()) as output:
            main(['open', '--static', '--root', str(self.root)])
        self.assertIn(self.output.resolve().as_uri(), output.getvalue())

    def test_static_cannot_enable_edits_and_other_commands_reject_static(self):
        for args in (['open', '--static', '--allow-edit'], ['tree', '--static']):
            with self.subTest(args=args), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(2, error.exception.code)

    def test_installed_launcher_uses_its_project_from_another_directory(self):
        files = initializer.prepare(self.root, 'Proyecto con espacios', 'go', started='2026-11-11')
        launcher = self.root / 'ver-plan.py'
        launcher.write_bytes(files['ver-plan.py'])
        module = runpy.run_path(str(launcher))
        with patch.object(sys, 'argv', [str(launcher), '--static']), patch('roadmap.main', return_value=0) as command:
            self.assertEqual(0, module['main']())
        command.assert_called_once_with(['open', '--root', str(self.root.resolve()), '--static'])
        self.assertEqual((KIT / 'templates/ver-plan.py.in').read_bytes(), files['ver-plan.py'])
