from __future__ import annotations

import json
import subprocess
import threading
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_kit import PlanFixture, task


def create_symlink(test, link, target):
    try:
        link.symlink_to(target)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            test.skipTest("Windows no permite crear enlaces simbólicos (WinError 1314).")
        raise
from plan_model import parse_plan
from roadmap import render, snapshot
from roadmap_edit import EditConflict, persist, proposal
from roadmap_server import Monitor, create_server


class EditFixture(PlanFixture):
    def setUp(self):
        super().setUp()
        subprocess.run(['git', 'init', '--initial-branch=codex/task-edit', str(self.root)],
                       capture_output=True, check=True, timeout=5)
        self.monitor = Monitor(self.root, self.plan, self.output, allow_edit=True)
        self.assertTrue(self.monitor.refresh(), self.monitor.error)

    def payload(self, **changes):
        return {'taskId': 'QA-001', 'revision': self.monitor.graph['revision'],
                'title': 'Título revisado', 'fields': {}, **changes}


class EditTest(EditFixture):
    def test_preview_does_not_write_and_save_preserves_other_tasks_and_crlf(self):
        content = '# Módulo\r\n\r\n' + (task() + '\n' + task('QA-002', dependencies='QA-001')).replace('\n', '\r\n')
        self.source.write_bytes(content.encode('utf-8'))
        self.monitor.refresh()
        original = self.source.read_bytes()
        reviewed = proposal(self.monitor, self.payload(fields={'Alcance': 'Descripción completa\n  - segunda línea',
                                                              'Criterios de aceptación': 'Prueba observable'}))
        self.assertEqual(original, self.source.read_bytes())
        self.assertIn('+', reviewed['diff'])
        persist(self.monitor, reviewed)
        report = parse_plan(self.plan)
        self.assertTrue(report['valid'], report['errors'])
        first, second = report['tasks']
        self.assertEqual('Título revisado', first['title'])
        self.assertEqual('PENDIENTE', first['status'])
        self.assertEqual([], first['dependencies'])
        self.assertEqual('Descripción completa\n  - segunda línea', first['fields']['Alcance'])
        self.assertEqual(['QA-001'], second['dependencies'])
        self.assertTrue(self.source.read_bytes().endswith(task('QA-002', dependencies='QA-001').replace('\n', '\r\n').encode()))
        self.assertNotIn(b'\n', self.source.read_bytes().replace(b'\r\n', b''))

    def test_schema_and_structural_injection_fail_without_writes(self):
        original = self.source.read_bytes()
        cases = [self.payload(status='HECHO'), self.payload(taskId='../private.md'),
                 self.payload(fields={'Dependencias': 'QA-999'}), self.payload(title='Título\n### [HECHO] QA-999 — Otra'),
                 self.payload(fields={'Última actualización': 'ayer'}), self.payload(fields={'Criterios de aceptación': ''}),
                 self.payload(fields={'Alcance': 'Otro\n' + task('QA-002')}),
                 self.payload(fields={'Alcance': 'Otro\n## Cortar el módulo'}), self.payload(fields={'Capa': 'EXCLUIDO'}),
                 self.payload(fields={'No existe': 'campo'})]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                proposal(self.monitor, payload)
            self.assertEqual(original, self.source.read_bytes())

    def test_code_fences_remain_data_and_evidence_is_not_erased(self):
        original = self.monitor.graph['tasks'][0]
        value = 'Ejemplo literal\n```sh\n### [HECHO] QA-999 — No ejecutar\n- **Dependencias:** QA-999\n```'
        reviewed = proposal(self.monitor, self.payload(fields={'Alcance': value}))
        persist(self.monitor, reviewed)
        report = parse_plan(self.plan)
        self.assertEqual(1, len(report['tasks']))
        self.assertEqual(value, report['tasks'][0]['fields']['Alcance'])
        self.assertEqual(original['fields']['Evidencia actual'], report['tasks'][0]['fields']['Evidencia actual'])

    def test_evidence_can_be_appended_but_history_cannot_be_replaced(self):
        original = self.monitor.graph['tasks'][0]['fields']['Evidencia actual']
        with self.assertRaisesRegex(ValueError, 'evidencia histórica'):
            proposal(self.monitor, self.payload(fields={'Evidencia actual': 'Evidencia nueva sin historia'}))
        reviewed = proposal(self.monitor, self.payload(fields={'Evidencia actual': original + '\nPrueba nueva: resultado y límite.'}))
        persist(self.monitor, reviewed)
        self.assertEqual(original + '\nPrueba nueva: resultado y límite.',
                         parse_plan(self.plan)['tasks'][0]['fields']['Evidencia actual'])

    def test_edit_preserves_embedded_visual_evidence(self):
        (self.plan / 'captura.png').write_bytes(b'imagen')
        self.source.write_text(task(**{'Evidencia actual': 'Resultado\n![Captura](captura.png)'}), encoding='utf-8')
        self.assertTrue(self.monitor.refresh(), self.monitor.error)
        before = self.monitor.graph['tasks'][0]['images']
        self.assertEqual('data:image/png;base64,aW1hZ2Vu', before[0]['src'])
        reviewed = proposal(self.monitor, self.payload(fields={'Alcance': 'Descripción revisada'}))
        persist(self.monitor, reviewed)
        self.assertTrue(self.monitor.refresh(), self.monitor.error)
        self.assertEqual(before, self.monitor.graph['tasks'][0]['images'])
        self.assertEqual('Resultado\n![Captura](captura.png)', self.monitor.graph['tasks'][0]['fields']['Evidencia actual'])

    def test_stale_revision_and_external_changes_reject_without_overwriting(self):
        payload = self.payload()
        reviewed = proposal(self.monitor, payload)
        external = task(title='Cambio desde el editor externo')
        self.source.write_text(external, encoding='utf-8')
        with self.assertRaises(EditConflict):
            proposal(self.monitor, payload)
        with self.assertRaises(EditConflict):
            persist(self.monitor, reviewed)
        self.assertEqual(external, self.source.read_text(encoding='utf-8'))
        self.assertEqual([], list(self.plan.glob('.roadmap-edit-*')))

    def test_main_branch_and_branch_switch_require_new_review(self):
        reviewed = proposal(self.monitor, self.payload())
        subprocess.run(['git', 'symbolic-ref', 'HEAD', 'refs/heads/main'], cwd=self.root, check=True, timeout=5)
        with self.assertRaises(ValueError):
            proposal(self.monitor, self.payload())
        with self.assertRaises(ValueError):
            persist(self.monitor, reviewed)

    def test_failed_replace_keeps_original_and_cleans_temporary_file(self):
        original = self.source.read_bytes()
        reviewed = proposal(self.monitor, self.payload())
        with patch('roadmap_edit.Path.replace', side_effect=OSError('Archivo ocupado')):
            with self.assertRaises(OSError):
                persist(self.monitor, reviewed)
        self.assertEqual(original, self.source.read_bytes())
        self.assertEqual([], list(self.plan.glob('.roadmap-edit-*')))

    def test_linked_source_is_rejected(self):
        outside = self.root / 'outside.md'
        outside.write_bytes(self.source.read_bytes())
        self.source.unlink()
        create_symlink(self, self.source, outside)
        with self.assertRaises(ValueError):
            proposal(self.monitor, self.payload())

    def test_static_export_has_no_live_capability_or_session_secret(self):
        graph, _ = snapshot(self.root, self.plan, self.output)
        self.assertNotIn('live', graph)
        self.assertNotIn(self.monitor.edit_secret, render(graph))
        self.assertNotIn(self.monitor.edit_secret, self.monitor.document.decode())
        self.assertNotEqual(0, self.cli('tree', '--allow-edit').returncode)

    def test_project_directory_comes_from_root_and_survives_static_and_live_exports(self):
        config = self.root / '.agents/project.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'name': 'Mi proyecto', 'projectPath': '/otra/carpeta'}), encoding='utf-8')
        graph, _ = snapshot(self.root, self.plan, self.output)
        self.assertEqual(str(self.root.resolve()), graph['projectPath'])
        document = render(graph)
        payload = document.split('<script type="application/json" id="roadmap-data">', 1)[1].split('</script>', 1)[0]
        self.assertEqual(str(self.root.resolve()), json.loads(payload)['projectPath'])
        self.monitor.refresh()
        self.assertEqual(str(self.root.resolve()), self.monitor.graph['projectPath'])


class EditHttpTest(EditFixture):
    def setUp(self):
        super().setUp()
        self.server = create_server(self.monitor, 0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def request(self, operation, payload, *, headers=None, expected=200):
        merged = {'Origin': self.base, 'Content-Type': 'application/json', 'X-Roadmap-Token': self.monitor.edit_secret}
        merged.update(headers or {})
        request = Request(self.base + '/__roadmap__/edit/' + operation, json.dumps(payload).encode(), headers=merged)
        if expected == 200:
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        with raised.exception as error:
            self.assertEqual(expected, error.code, error.read().decode())

    def test_only_exact_reviewed_change_can_be_explicitly_saved(self):
        before = self.source.read_bytes()
        payload = self.payload(fields={'Alcance': 'Descripción del resultado revisada'})
        with urlopen(self.base + '/__roadmap__/session', timeout=3) as response:
            session = json.load(response)
        self.assertEqual(self.monitor.edit_secret, session['token'])
        preview = self.request('preview', payload)
        self.assertEqual(before, self.source.read_bytes())
        self.request('save', payload, expected=403)
        self.request('save', {**payload, 'approval': preview['approval'], 'authorized': 'true'}, expected=403)
        self.request('save', {**payload, 'title': 'Cambió tras revisión', 'approval': preview['approval'], 'authorized': True}, expected=403)
        self.assertEqual(before, self.source.read_bytes())
        result = self.request('save', {**payload, 'approval': preview['approval'], 'authorized': True})
        self.assertTrue(result['saved'])
        self.assertNotEqual(payload['revision'], result['revision'])
        self.request('save', {**payload, 'approval': preview['approval'], 'authorized': True}, expected=409)
        self.assertEqual('Título revisado', self.monitor.graph['tasks'][0]['title'])

    def test_foreign_origin_token_host_and_content_type_are_rejected(self):
        before = self.source.read_bytes()
        for headers in ({'Origin': 'https://attacker.example'}, {'Origin': 'null'}, {'X-Roadmap-Token': ''},
                        {'Host': 'attacker.example'}):
            self.request('preview', self.payload(), headers=headers, expected=403)
        self.request('preview', self.payload(), headers={'Content-Type': 'text/plain'}, expected=415)
        self.request('preview', self.payload(title='x' * 270000), expected=413)
        self.request('preview', [], expected=422)
        self.request('unknown', self.payload(), expected=404)
        self.assertEqual(before, self.source.read_bytes())

    def test_read_only_server_has_no_write_capability(self):
        self.monitor.allow_edit = False
        self.request('preview', self.payload(), expected=403)
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base + '/__roadmap__/session', timeout=3)
        raised.exception.close()
        self.assertEqual(404, raised.exception.code)

    def test_unpublished_valid_and_invalid_changes_both_conflict(self):
        for content in (task(title='Nueva versión'), task(dependencies='QA-999')):
            self.source.write_text(content, encoding='utf-8')
            self.request('preview', self.payload(), expected=409)
            self.assertEqual(content, self.source.read_text(encoding='utf-8'))
