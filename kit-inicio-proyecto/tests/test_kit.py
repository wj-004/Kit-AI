from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

KIT = Path(__file__).resolve().parents[1]
SCRIPTS = KIT / 'skills/manage-project-roadmap/scripts'
sys.path.insert(0, str(SCRIPTS))
from plan_model import FIELDS, MAX_IMAGE_BYTES, SCHEMA, STATES, parse_plan
from roadmap import metadata, render, snapshot
from roadmap_server import Monitor, create_server


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


initializer = load('kit_initializer', KIT / 'scripts/init_project.py')
packager = load('kit_packager', KIT / 'scripts/package_kit.py')


def task(key='QA-001', status='PENDIENTE', scope='SOLICITADO', dependencies='ninguna', title='Resultado verificable', **changes):
    active = status in {'EN_CURSO', 'PARCIAL', 'HECHO'}
    values = {
        'Capa': scope, 'Fuente': 'Solicitud de prueba; DEC-2026-11-03-01.',
        'Contexto propietario': 'Contexto de prueba', 'Dependencias': dependencies,
        'Alcance': 'Comportamiento incluido', 'Fuera de alcance': 'Ningún dato real',
        'Invariantes': 'Regla comprobable', 'Contratos y archivos previstos': 'Interfaz de prueba',
        'Criterios de aceptación': 'El resultado puede observarse y verificarse',
        'Responsable': 'Agente de prueba' if active else 'sin asignar',
        'Fecha de inicio': '2026-11-03' if active else 'pendiente',
        'Última actualización': '2026-11-03', 'Próximo paso': 'Comprobar resultado',
        'Evidencia actual': 'tests: comprobación aislada correcta' if active else 'No iniciado; datos de prueba',
    }
    values.update(changes)
    return f'### [{status}] {key} — {title}\n\n' + '\n'.join(f'- **{name}:** {value}' for name, value in values.items()) + '\n'


class PlanFixture(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='kit-test-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.plan = self.root / 'docs/plan-maestro'
        self.plan.mkdir(parents=True)
        self.index = self.plan / 'README.md'
        self.index.write_text('# Plan de prueba\n\n' + SCHEMA['marker'] + '\n', encoding='utf-8')
        self.source = self.plan / '01-prueba.md'
        self.source.write_text('# Área de prueba\n\n' + task(), encoding='utf-8')
        self.output = self.plan / 'visualizacion.html'

    def validate(self, text):
        self.source.write_text(text, encoding='utf-8')
        return parse_plan(self.plan)

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(SCRIPTS / 'roadmap.py'), *args, '--root', str(self.root)],
                              capture_output=True, text=True)


class ParserTest(PlanFixture):
    def test_valid_plan_preserves_all_fields_and_multiline_evidence(self):
        content = task(**{'Evidencia actual': 'Primera línea\n  - comando → resultado\n  - límite de prueba'})
        report = self.validate(content)
        self.assertTrue(report['valid'], report['errors'])
        self.assertEqual(14, len(FIELDS))
        self.assertEqual(set(FIELDS), set(report['tasks'][0]['fields']))
        self.assertIn('comando → resultado', report['tasks'][0]['fields']['Evidencia actual'])

    def test_requires_index_schema_and_at_least_one_task(self):
        self.index.write_text('# Otro formato', encoding='utf-8')
        self.assertFalse(parse_plan(self.plan)['valid'])
        self.index.unlink()
        self.assertFalse(parse_plan(self.plan)['valid'])
        self.index.write_text(SCHEMA['marker'], encoding='utf-8')
        self.assertFalse(self.validate('# Sin tareas')['valid'])

    def test_ignores_fenced_examples_and_ends_task_at_a_section(self):
        content = '```markdown\n' + task('QA-999') + '```\n\n' + task() + '\n## Notas\nTexto fuera de la tarea\n'
        report = self.validate(content)
        self.assertEqual(['QA-001'], [item['id'] for item in report['tasks']])
        self.assertNotIn('Texto fuera', report['tasks'][0]['fields']['Evidencia actual'])

    def test_nested_module_and_source_line_are_preserved(self):
        nested = self.plan / 'area con espacio' / 'módulo.md'
        nested.parent.mkdir()
        nested.write_text('# Otro módulo\n\n' + task('QA-002', dependencies='QA-001'), encoding='utf-8')
        report = parse_plan(self.plan)
        self.assertTrue(report['valid'], report['errors'])
        item = next(t for t in report['tasks'] if t['id'] == 'QA-002')
        self.assertEqual('area con espacio/módulo.md', item['source'])
        self.assertEqual(3, item['line'])

    def test_rejects_malformed_headings_unknown_states_and_duplicate_ids(self):
        for content in (task(key='qa-001'), task(key='QA-1'), task(status='LISTO'), task() + task()):
            with self.subTest(content=content):
                self.assertFalse(self.validate(content)['valid'])

    def test_rejects_empty_missing_duplicate_and_unknown_fields(self):
        for content in (
            task(**{'Criterios de aceptación': ''}),
            task().replace('- **Responsable:** sin asignar\n', ''),
            task() + '- **Dependencias:** QA-999\n',
            task() + '- **Fecha inventada:** mañana\n',
        ):
            with self.subTest(content=content):
                self.assertFalse(self.validate(content)['valid'])

    def test_rejects_bad_dependency_formats_unknown_self_and_cycles(self):
        cases = [task(dependencies=value) for value in ('qa-999', 'QA-999', 'QA-001', 'QA-002; QA-003', 'todas')]
        cases.append(task(dependencies='QA-002') + task('QA-002', dependencies='QA-001'))
        for content in cases:
            with self.subTest(content=content):
                self.assertFalse(self.validate(content)['valid'])

    def test_rejects_false_completion_without_owner_date_evidence_or_prerequisites(self):
        cases = [task(status='HECHO', **{field: value}) for field, value in (
            ('Responsable', 'sin asignar'), ('Fecha de inicio', 'pendiente'), ('Evidencia actual', 'sin evidencia'))]
        cases.append(task() + task('QA-002', status='HECHO', dependencies='QA-001'))
        for content in cases:
            with self.subTest(content=content):
                self.assertFalse(self.validate(content)['valid'])

    def test_rejects_bad_or_reversed_dates(self):
        for changes in ({'Última actualización': '2026-02-30'},
                        {'Última actualización': '20261103'},
                        {'Fecha de inicio': '2026-11-04', 'Última actualización': '2026-11-03'}):
            self.assertFalse(self.validate(task(status='EN_CURSO', **changes))['valid'])

    def test_unclosed_code_fence_does_not_hide_tasks_silently(self):
        report = self.validate(task() + '\n```markdown\n' + task('QA-002'))
        self.assertFalse(report['valid'])
        self.assertTrue(any('sin cierre' in message for message in report['errors']))

    def test_requires_authorization_and_consistent_exclusion_with_decision(self):
        self.assertFalse(self.validate(task(status='EN_CURSO', scope='PROPUESTO'))['valid'])
        self.assertFalse(self.validate(task(status='EXCLUIDO'))['valid'])
        self.assertFalse(self.validate(task(status='EXCLUIDO', scope='EXCLUIDO', Fuente='Sin decisión'))['valid'])
        self.assertTrue(self.validate(task(status='EXCLUIDO', scope='EXCLUIDO'))['valid'])

    def test_all_states_and_scopes_survive_the_parser(self):
        content = ''.join(task(f'QA-{index:03}', status=state, scope='EXCLUIDO' if state == 'EXCLUIDO' else 'SOLICITADO')
                          for index, state in enumerate(STATES, 1)) + task('QA-007', scope='PROPUESTO')
        report = self.validate(content)
        self.assertTrue(report['valid'], report['errors'])
        self.assertEqual(set(STATES), {item['status'] for item in report['tasks']})
        self.assertEqual(set(SCHEMA['scopes']), {item['scope'] for item in report['tasks']})

    def test_rejects_symlink_sources_and_non_utf8_files(self):
        foreign = self.root / 'foreign.md'
        foreign.write_text(task('QA-002'), encoding='utf-8')
        linked = self.plan / 'linked.md'
        linked.symlink_to(foreign)
        self.assertFalse(parse_plan(self.plan)['valid'])
        linked.unlink()
        self.source.write_bytes(b'\xff\xfe')
        self.assertFalse(parse_plan(self.plan)['valid'])


class ReportAndExportTest(PlanFixture):
    def test_summary_omits_task_details_but_keeps_counts_and_all_errors(self):
        self.validate(task(status='HECHO') + task('QA-002'))
        result = self.cli('report', '--summary', '--json', '--status', 'PENDIENTE')
        report = json.loads(result.stdout)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, report['totalTasks'])
        self.assertEqual(1, report['selectedTasks'])
        self.assertEqual({'HECHO': 1, 'PENDIENTE': 1}, report['counts'])
        self.assertNotIn('tasks', report)
        self.assertNotIn('edges', report)
        invalid = self.validate(task(dependencies='QA-998') + task('QA-002', dependencies='QA-999'))
        result = self.cli('check', '--summary', '--json')
        self.assertEqual(1, result.returncode)
        self.assertEqual(invalid['errors'], json.loads(result.stdout)['errors'])
        text = self.cli('report', '--summary')
        self.assertEqual(1, text.returncode)
        for error in invalid['errors']:
            self.assertIn(error, text.stdout)

    def test_json_filter_still_validates_the_whole_plan(self):
        self.validate(task(status='HECHO') + task('QA-002'))
        result = self.cli('report', '--json', '--status', 'PENDIENTE')
        report = json.loads(result.stdout)
        self.assertEqual(0, result.returncode)
        self.assertEqual(['QA-002'], [row['id'] for row in report['tasks']])
        self.assertEqual({'HECHO': 1, 'PENDIENTE': 1}, report['counts'])
        self.validate(task(status='HECHO', dependencies='QA-999') + task('QA-002'))
        result = self.cli('report', '--json', '--status', 'PENDIENTE')
        self.assertEqual(1, result.returncode)
        self.assertFalse(json.loads(result.stdout)['valid'])

    def test_shared_prerequisites_edges_direction_and_isolated_tasks(self):
        self.validate(task() + task('QA-002', dependencies='QA-001, QA-001')
                      + task('QA-003', dependencies='QA-001') + task('QA-004', dependencies='QA-002, QA-003') + task('QA-005'))
        graph, _ = snapshot(self.root, self.plan, self.output)
        self.assertEqual(5, len(graph['tasks']))
        self.assertEqual([{'from': 'QA-001', 'to': 'QA-002'}, {'from': 'QA-001', 'to': 'QA-003'},
                          {'from': 'QA-002', 'to': 'QA-004'}, {'from': 'QA-003', 'to': 'QA-004'}], graph['edges'])

    def test_untrusted_text_cannot_close_json_script_or_replace_other_markers(self):
        title = '</script><script>bad()</script> & __PROJECT_NAME__'
        self.validate(task(title=title))
        graph, _ = snapshot(self.root, self.plan, self.output)
        graph['projectName'] = '<img src=x onerror=bad()> __GENERATED_AT__'
        document = render(graph)
        payload = re.search(r'<script type="application/json" id="roadmap-data">(.*?)</script>', document, re.S)[1]
        self.assertNotIn('<', payload)
        self.assertNotIn('&', payload)
        decoded = json.loads(payload)
        self.assertEqual(title, decoded['tasks'][0]['title'])
        self.assertEqual(set(FIELDS), set(decoded['tasks'][0]['fields']))
        self.assertEqual(list(FIELDS), decoded['fieldNames'])
        self.assertNotIn('<img src=x', document)
        self.assertIn('__GENERATED_AT__', decoded['projectName'])

    def test_static_export_is_self_contained_and_sources_are_relative(self):
        result = self.cli('tree')
        self.assertEqual(0, result.returncode, result.stderr)
        document = self.output.read_text(encoding='utf-8')
        self.assertNotRegex(document, r'<script[^>]+src=|<link[^>]+href=')
        graph, _ = snapshot(self.root, self.plan, self.output)
        self.assertEqual('01-prueba.md', graph['tasks'][0]['sourceUrl'])
        other, _ = snapshot(self.root, self.plan, self.root / 'exports/view.html')
        self.assertEqual('../docs/plan-maestro/01-prueba.md', other['tasks'][0]['sourceUrl'])

    def test_evidence_images_are_embedded_and_keep_the_export_self_contained(self):
        folder = self.plan / 'capturas'
        folder.mkdir()
        (folder / 'despues.PNG').write_bytes(b'imagen')
        self.validate(task(**{'Evidencia actual': 'Pantalla lista\n  - ![Después del cambio](capturas/despues.PNG)'}))
        report = parse_plan(self.plan)
        self.assertEqual([{'alt': 'Después del cambio', 'path': 'capturas/despues.PNG'}], report['tasks'][0]['images'])
        graph, _ = snapshot(self.root, self.plan, self.output)
        self.assertEqual([{'alt': 'Después del cambio', 'src': 'data:image/png;base64,aW1hZ2Vu'}], graph['tasks'][0]['images'])
        self.assertIn('data:image/png;base64,aW1hZ2Vu', render(graph))

    def test_invalid_evidence_images_are_rejected(self):
        (self.root / 'privada.png').write_bytes(b'privada')
        (self.plan / 'script.svg').write_text('<svg/>', encoding='utf-8')
        (self.plan / 'bien.png').write_bytes(b'imagen')
        (self.plan / 'grande.png').write_bytes(b'0' * (MAX_IMAGE_BYTES + 1))
        for reference, expected in (('![fuera](../../privada.png)', 'dentro del plan'), ('![falta](falta.png)', 'no existe'),
                                    ('![web](https://example.com/a.png)', 'ruta relativa'), ('![svg](script.svg)', 'no permitido'),
                                    ('![](bien.png)', 'texto alternativo'), ('![grande](grande.png)', 'supera')):
            with self.subTest(reference=reference):
                report = self.validate(task(**{'Evidencia actual': reference}))
                self.assertFalse(report['valid'])
                self.assertIn(expected, ' '.join(report['errors']))

    def test_image_symlinks_and_symlinked_parent_directories_are_rejected(self):
        folder = self.plan / 'original'
        folder.mkdir()
        (folder / 'captura.png').write_bytes(b'imagen')
        (self.plan / 'enlace.png').symlink_to(folder / 'captura.png')
        (self.plan / 'enlaces').symlink_to(folder, target_is_directory=True)
        for path in ('enlace.png', 'enlaces/captura.png'):
            with self.subTest(path=path):
                report = self.validate(task(**{'Evidencia actual': f'![Captura]({path})'}))
                self.assertFalse(report['valid'])
                self.assertIn('enlaces simbólicos', ' '.join(report['errors']))

    def test_nested_task_can_reference_an_image_in_its_parent_plan_directory(self):
        (self.plan / 'captura.png').write_bytes(b'imagen')
        nested = self.plan / 'modulo'
        nested.mkdir()
        self.validate(task())
        (nested / 'otra.md').write_text(task('QA-002', **{'Evidencia actual': '![Captura](../captura.png)'}), encoding='utf-8')
        report = parse_plan(self.plan)
        self.assertTrue(report['valid'], report['errors'])
        self.assertEqual('captura.png', next(item for item in report['tasks'] if item['id'] == 'QA-002')['images'][0]['path'])

    def test_export_rechecks_an_image_if_it_becomes_a_symlink_after_validation(self):
        from unittest.mock import patch
        image = self.plan / 'captura.png'
        image.write_bytes(b'imagen')
        self.validate(task(**{'Evidencia actual': '![Captura](captura.png)'}))
        real_parse = parse_plan
        secret = self.root / 'privada.png'
        secret.write_bytes(b'NO EXPORTAR')
        def replace_after_parse(plan):
            report = real_parse(plan)
            image.unlink()
            image.symlink_to(secret)
            return report
        with patch('roadmap.parse_plan', side_effect=replace_after_parse):
            with self.assertRaises((ValueError, OSError)):
                snapshot(self.root, self.plan, self.output)
        self.assertFalse(self.output.exists())

    def test_query_with_images_keeps_all_fields_and_does_not_embed_binary_payloads(self):
        (self.plan / 'captura.png').write_bytes(b'imagen')
        report = self.validate(task(**{'Evidencia actual': '![Captura](captura.png)'}))
        result = self.cli('task', 'QA-001', '--format', 'json')
        self.assertEqual(0, result.returncode, result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual(report['tasks'][0]['fields'], context['task']['fields'])
        self.assertNotIn('data:image', result.stdout)

    def test_invalid_plan_or_output_keeps_the_previous_artifact(self):
        self.output.write_text('Previous valid artifact', encoding='utf-8')
        self.validate(task(dependencies='QA-999'))
        self.assertEqual(1, self.cli('tree').returncode)
        self.assertEqual('Previous valid artifact', self.output.read_text())
        before = self.source.read_bytes()
        self.assertEqual(1, self.cli('tree', '--output', str(self.source)).returncode)
        self.assertEqual(before, self.source.read_bytes())


class TaskContextTest(PlanFixture):
    def test_selected_task_preserves_all_fields_and_multiline_content_without_unrelated_tasks(self):
        evidence = 'Primera línea\n  - informe: docs/evidencia/QA-002.md\n  - ' + 'x' * 5000
        original = self.validate(task('QA-001', status='HECHO')
                                 + task('QA-002', dependencies='QA-001', **{'Evidencia actual': evidence})
                                 + task('QA-003', title='No incluir esta tarea'))
        result = self.cli('task', 'QA-002', '--format', 'json')
        self.assertEqual(0, result.returncode, result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual(original['tasks'][1]['fields'], context['task']['fields'])
        self.assertEqual(list(FIELDS), context['fieldNames'])
        self.assertEqual('PENDIENTE', context['task']['status'])
        self.assertEqual('SOLICITADO', context['task']['scope'])
        self.assertNotIn('No incluir esta tarea', result.stdout)
        text = self.cli('task', 'QA-002', '--format', 'context')
        self.assertEqual(0, text.returncode, text.stderr)
        for field, value in original['tasks'][1]['fields'].items():
            self.assertIn(field + ':\n' + value, text.stdout)

    def test_dependencies_are_direct_summaries_with_correct_states_and_locations(self):
        self.validate(task('QA-001', status='HECHO') + task('QA-002', status='EN_CURSO', dependencies='QA-001')
                      + task('QA-003', dependencies='QA-002, QA-001'))
        result = self.cli('task', 'QA-003', '--json')
        context = json.loads(result.stdout)
        self.assertEqual(0, result.returncode, result.stderr)
        dependencies = context['dependencies']
        self.assertEqual(['QA-002', 'QA-001'], [item['id'] for item in dependencies])
        self.assertEqual(['EN_CURSO', 'HECHO'], [item['status'] for item in dependencies])
        for item in dependencies:
            self.assertNotIn('fields', item)
            self.assertEqual('docs/plan-maestro/01-prueba.md', item['sourcePath'])
            line = (self.root / item['sourcePath']).read_text().splitlines()[item['line'] - 1]
            self.assertIn(item['id'], line)
        context = json.loads(self.cli('task', 'QA-002', '--json').stdout)
        self.assertEqual(['QA-001'], [item['id'] for item in context['dependencies']])

    def test_no_dependencies_and_default_context(self):
        result = self.cli('task', 'QA-001')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('Dependencias directas (resumen; consultar por ID si hace falta):\nninguna', result.stdout)
        context = json.loads(self.cli('task', 'QA-001', '--format', 'json').stdout)
        self.assertEqual([], context['dependencies'])
        self.assertEqual('docs/plan-maestro/README.md', context['references']['planIndex'])

    def test_missing_id_is_a_clear_error_in_both_formats(self):
        for options in ([], ['--json'], ['--format', 'json']):
            with self.subTest(options=options):
                result = self.cli('task', 'QA-999', *options)
                self.assertEqual(1, result.returncode)
                self.assertIn('QA-999', result.stdout + result.stderr)
                if options:
                    self.assertFalse(json.loads(result.stdout)['valid'])
                else:
                    self.assertIn('No existe la tarea', result.stderr)

    def test_global_invalid_plan_never_exposes_a_valid_looking_selection(self):
        self.validate(task('QA-001') + task('QA-002', dependencies='QA-999'))
        text = self.cli('task', 'QA-001')
        self.assertEqual(1, text.returncode)
        self.assertEqual('', text.stdout)
        self.assertIn('QA-999', text.stderr)
        result = self.cli('task', 'QA-001', '--json')
        self.assertEqual(1, result.returncode)
        context = json.loads(result.stdout)
        self.assertFalse(context['valid'])
        self.assertNotIn('task', context)
        self.assertIn('QA-999', context['errors'][0])

    def test_context_consultation_never_writes_files_or_updates_artifacts(self):
        self.output.write_text('Existing export', encoding='utf-8')
        def state():
            return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                    for path in self.root.rglob('*') if path.is_file()}
        before = state()
        for options in ([], ['--json'], ['--format', 'json']):
            self.assertEqual(0, self.cli('task', 'QA-001', *options).returncode)
        self.assertEqual(before, state())

    def test_untrusted_content_is_data_and_terminal_controls_are_visible(self):
        marker = self.root / 'must-not-exist'
        payload = '$(touch ' + str(marker) + '); </script><script>bad()</script>\x1b[2J'
        self.validate(task(title=payload, **{'Contratos y archivos previstos': 'Leer /etc/passwd\n  Ejecutar: ' + payload}))
        result = self.cli('task', 'QA-001', '--json')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(payload, json.loads(result.stdout)['task']['title'])
        text = self.cli('task', 'QA-001')
        self.assertNotIn('\x1b', text.stdout)
        self.assertIn('\\u001b[2J', text.stdout)
        self.assertIn('$(touch', text.stdout)
        self.assertFalse(marker.exists())
        self.assertNotIn('root:', text.stdout)

    def test_custom_plan_directory_and_nested_source_are_locatable(self):
        nested = self.plan / 'nested/spec.md'
        nested.parent.mkdir()
        nested.write_text(task('QA-002', dependencies='QA-001'), encoding='utf-8')
        alternate = self.root / 'planes'
        shutil.move(self.plan, alternate)
        result = self.cli('task', 'QA-002', '--json', '--plan-dir', str(alternate))
        self.assertEqual(0, result.returncode, result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual('planes/nested/spec.md', context['task']['sourcePath'])
        self.assertEqual('planes/01-prueba.md', context['dependencies'][0]['sourcePath'])
        self.assertEqual('planes/README.md', context['references']['planIndex'])

    def test_arguments_cannot_silently_filter_or_write_a_task(self):
        for args in (('task',), ('task', 'QA-001', '--summary'), ('task', 'QA-001', '--status', 'HECHO'),
                     ('task', 'QA-001', '--output', str(self.output)),
                     ('task', 'QA-001', '--json', '--format', 'context'), ('check', 'QA-001'),
                     ('check', '--format', 'json'), ('tree', '--summary')):
            with self.subTest(args=args):
                self.assertEqual(2, self.cli(*args).returncode)
        self.assertFalse(self.output.exists())


class MonitorTest(PlanFixture):
    def monitor(self):
        monitor = Monitor(self.root, self.plan, self.output)
        self.assertTrue(monitor.refresh(), monitor.error)
        return monitor

    def test_unchanged_sources_do_not_rewrite_output(self):
        monitor = self.monitor()
        written = self.output.stat().st_mtime_ns
        self.assertFalse(monitor.refresh())
        self.assertEqual(written, self.output.stat().st_mtime_ns)

    def test_valid_changes_update_fields_edges_and_revision(self):
        monitor = self.monitor()
        previous = monitor.status()['revision']
        self.validate(task(status='HECHO') + task('QA-002', dependencies='QA-001'))
        self.assertTrue(monitor.refresh())
        self.assertNotEqual(previous, monitor.status()['revision'])
        self.assertEqual('HECHO', monitor.graph['tasks'][0]['status'])
        self.assertEqual([{'from': 'QA-001', 'to': 'QA-002'}], monitor.graph['edges'])
        self.assertEqual(set(FIELDS), set(monitor.graph['tasks'][0]['fields']))

    def test_invalid_edits_keep_last_valid_document_graph_and_source_then_recover(self):
        monitor = self.monitor()
        document, graph, source = monitor.document, monitor.graph, dict(monitor.sources)
        self.validate(task(dependencies='QA-999'))
        self.assertFalse(monitor.refresh())
        self.assertEqual(document, monitor.document)
        self.assertIs(graph, monitor.graph)
        self.assertEqual(source, monitor.sources)
        self.assertEqual('invalid', monitor.status()['status'])
        self.validate(task(status='HECHO'))
        self.assertTrue(monitor.refresh())
        self.assertEqual('ok', monitor.status()['status'])

    def test_missing_index_is_detected_and_restoring_it_recovers(self):
        monitor = self.monitor()
        self.index.unlink()
        self.assertFalse(monitor.refresh())
        self.assertEqual('invalid', monitor.status()['status'])
        self.index.write_text(SCHEMA['marker'], encoding='utf-8')
        self.assertTrue(monitor.refresh())

    def test_added_renamed_and_removed_modules_are_detected(self):
        monitor = self.monitor()
        other = self.plan / '02-other.md'
        other.write_text(task('QA-002'), encoding='utf-8')
        self.assertTrue(monitor.refresh())
        self.assertEqual(2, len(monitor.graph['tasks']))
        moved = other.rename(self.plan / '03-renamed.md')
        self.assertTrue(monitor.refresh())
        self.assertEqual('03-renamed.md', monitor.graph['tasks'][1]['source'])
        moved.unlink()
        self.assertTrue(monitor.refresh())
        self.assertEqual(1, len(monitor.graph['tasks']))

    def test_replacing_an_evidence_image_updates_the_snapshot(self):
        image = self.plan / 'captura.png'
        image.write_bytes(b'antes')
        self.validate(task(**{'Evidencia actual': '![Captura](captura.png)'}))
        monitor = self.monitor()
        previous = monitor.graph['tasks'][0]['images'][0]['src']
        image.write_bytes(b'despues')
        self.assertTrue(monitor.refresh())
        self.assertNotEqual(previous, monitor.graph['tasks'][0]['images'][0]['src'])

    def test_source_race_and_write_error_do_not_publish_partial_updates(self):
        monitor = self.monitor()
        previous = monitor.graph
        self.validate(task(status='HECHO'))
        with patch.object(monitor, 'fingerprint', side_effect=['before', 'after']):
            self.assertFalse(monitor.refresh())
        self.assertIs(previous, monitor.graph)
        with patch('roadmap_server.write_document', side_effect=OSError('No write')):
            self.assertFalse(monitor.refresh())
        self.assertIs(previous, monitor.graph)
        self.assertTrue(monitor.refresh())

    def test_project_configuration_changes_name_but_not_identity(self):
        monitor = self.monitor()
        project_id = monitor.status()['projectId']
        config = self.root / '.agents/project.json'
        config.parent.mkdir()
        config.write_text(json.dumps({'name': 'New name'}), encoding='utf-8')
        self.assertTrue(monitor.refresh())
        self.assertEqual('New name', monitor.status()['projectName'])
        self.assertEqual(project_id, monitor.status()['projectId'])

    def test_symlink_error_keeps_previous_snapshot(self):
        monitor = self.monitor()
        previous = monitor.document
        foreign = self.root / 'foreign.md'
        foreign.write_text('Outside', encoding='utf-8')
        (self.plan / 'linked.md').symlink_to(foreign)
        self.assertFalse(monitor.refresh())
        self.assertEqual(previous, monitor.document)
        self.assertEqual('invalid', monitor.status()['status'])


class HttpTest(PlanFixture):
    def setUp(self):
        super().setUp()
        self.monitor = Monitor(self.root, self.plan, self.root / 'exports/view.html')
        self.assertTrue(self.monitor.refresh())
        self.server = create_server(self.monitor, 0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def test_serves_only_the_viewer_data_status_and_validated_source_snapshots(self):
        for route, expected in (('/view.html', b'roadmap-data'), ('/__roadmap__/data', b'QA-001'),
                                ('/__roadmap__/status', b'"status": "ok"'),
                                ('/__roadmap__/source/01-prueba.md', b'QA-001')):
            with self.subTest(route=route), urlopen(self.base + route, timeout=3) as response:
                self.assertEqual(200, response.status)
                self.assertIn(expected, response.read())
                self.assertEqual('no-store', response.headers['Cache-Control'])

    def test_rejects_other_files_path_traversal_and_foreign_host_headers(self):
        (self.root / 'private.txt').write_text('Private', encoding='utf-8')
        for route in ('/private.txt', '/../private.txt', '/__roadmap__/source/%2e%2e/private.txt', '/.agents/project.json'):
            with self.subTest(route=route), self.assertRaises(HTTPError) as raised:
                urlopen(self.base + route, timeout=3)
            self.assertEqual(404, raised.exception.code)
            raised.exception.close()
        with self.assertRaises(HTTPError) as raised:
            urlopen(Request(self.base + '/', headers={'Host': 'foreign.example'}), timeout=3)
        self.assertEqual(403, raised.exception.code)
        raised.exception.close()

    def test_occupied_port_does_not_modify_an_export(self):
        output = self.root / 'previous.html'
        output.write_text('Keep it', encoding='utf-8')
        result = self.cli('serve', '--port', str(self.server.server_port), '--output', str(output))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual('Keep it', output.read_text())


class InstallerTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='kit-install-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.target = self.root / 'Proyecto con espacios'

    def install(self, **changes):
        args = dict(target=self.target, name='Proyecto ágil', profile='base', started='2026-11-03')
        args.update(changes)
        return initializer.install(**args)

    def test_installation_prepares_skills_and_three_pending_tasks_without_product_code(self):
        self.install()
        config = json.loads((self.target / '.agents/project.json').read_text())
        self.assertEqual('base', config['profile'])
        self.assertEqual('preparacion', config['stage'])
        self.assertEqual('src', config['source_root'])
        self.assertFalse(config['source_root_override'])
        self.assertEqual(b'', (self.target / 'src/.gitkeep').read_bytes())
        self.assertEqual([self.target / 'src/.gitkeep'], list((self.target / 'src').iterdir()))
        self.assertTrue((self.target / config['sources_index']).is_file())
        self.assertEqual(3, len(list((self.target / '.agents/skills').glob('*/SKILL.md'))))
        report = parse_plan(self.target / 'docs/plan-maestro')
        self.assertTrue(report['valid'], report['errors'])
        self.assertEqual({'PENDIENTE': 3}, report['counts'])
        for path in ('app', 'lib', 'internal', 'go.mod', 'composer.json', 'package.json'):
            self.assertFalse((self.target / path).exists())

    def test_dry_run_makes_no_target_changes(self):
        result = self.install(dry_run=True)
        self.assertTrue(result['create'])
        self.assertIn('src/.gitkeep', result['create'])
        self.assertIn('docs/fuentes/README.md', result['create'])
        self.assertFalse(self.target.exists())

    def test_repeated_installation_is_idempotent_and_preserves_initial_date(self):
        result = self.install()
        before = {name: (self.target / name).stat().st_mtime_ns for name in result['create']}
        repeated = self.install(started=None)
        self.assertEqual([], repeated['create'])
        self.assertEqual(set(before), set(repeated['unchanged']))
        self.assertEqual(before, {name: (self.target / name).stat().st_mtime_ns for name in before})

    def test_profiles_prepare_their_roots_and_repeat_without_product_code(self):
        for profile, expected in {'base': 'src', 'laravel': 'src', 'go': 'internal', 'flutter': 'lib'}.items():
            with self.subTest(profile=profile):
                target = self.root / profile
                preview = self.install(target=target, profile=profile, dry_run=True)
                self.assertFalse(target.exists())
                self.assertIn(expected + '/.gitkeep', preview['create'])
                if profile == 'go':
                    self.assertIn('cmd/.gitkeep', preview['create'])
                result = self.install(target=target, profile=profile)
                config = json.loads((target / '.agents/project.json').read_text())
                self.assertEqual(profile, config['profile'])
                self.assertEqual(expected, config['source_root'])
                self.assertEqual(expected, config['source_root_default'])
                self.assertFalse(config['source_root_override'])
                self.assertEqual([target / expected / '.gitkeep'], list((target / expected).iterdir()))
                prepared = {expected, 'cmd'} if profile == 'go' else {expected}
                for alternative in {'src', 'lib', 'internal', 'cmd', 'app', 'go.mod', 'pubspec.yaml', 'composer.json'} - prepared:
                    self.assertFalse((target / alternative).exists())
                self.assertTrue(parse_plan(target / 'docs/plan-maestro')['valid'])
                before = {name: (target / name).stat().st_mtime_ns for name in result['create']}
                self.assertEqual([], self.install(target=target, profile=profile, started=None)['create'])
                self.assertEqual(before, {name: (target / name).stat().st_mtime_ns for name in before})

    def test_explicit_source_root_is_used_and_preserved_on_repeat(self):
        for profile, default in {'base': 'src', 'laravel': 'src', 'go': 'internal', 'flutter': 'lib'}.items():
            with self.subTest(profile=profile):
                target = self.root / profile
                self.install(target=target, profile=profile, source_root='codigo propio/contextos')
                config = json.loads((target / '.agents/project.json').read_text())
                self.assertEqual('codigo propio/contextos', config['source_root'])
                self.assertEqual(default, config['source_root_default'])
                self.assertTrue(config['source_root_override'])
                self.assertTrue((target / config['source_root'] / '.gitkeep').is_file())
                self.assertFalse((target / default).exists())
                if profile == 'go':
                    self.assertTrue((target / 'cmd/.gitkeep').is_file())
                self.assertEqual([], self.install(target=target, profile=profile, started=None)['create'])
                before = {path.relative_to(target): path.read_bytes() for path in target.rglob('*') if path.is_file()}
                with self.assertRaises(ValueError):
                    self.install(target=target, profile=profile, source_root=default)
                self.assertEqual(before, {path.relative_to(target): path.read_bytes() for path in target.rglob('*') if path.is_file()})

    def test_legacy_go_and_flutter_roots_are_retained_without_partial_upgrade(self):
        for profile, default in {'go': 'internal', 'flutter': 'lib'}.items():
            with self.subTest(profile=profile):
                target = self.root / profile
                self.install(target=target, profile=profile, source_root='src')
                manifest = target / '.agents/project-kit.json'
                old = json.loads(manifest.read_text())
                old['kit_version'] = '1.2.0'
                manifest.write_text(json.dumps(old), encoding='utf-8')
                config_path = target / '.agents/project.json'
                old_config = json.loads(config_path.read_text())
                old_config.pop('source_root_default')
                old_config['source_root_override'] = False
                config_path.write_text(json.dumps(old_config), encoding='utf-8')
                business = target / 'src/existing.txt'
                business.write_text('Preserve existing code', encoding='utf-8')
                before = {path.relative_to(target): path.read_bytes() for path in target.rglob('*') if path.is_file()}
                prepared = initializer.prepare(target, 'Proyecto ágil', profile)
                config = json.loads(prepared['.agents/project.json'])
                self.assertEqual('src', config['source_root'])
                self.assertEqual(default, config['source_root_default'])
                self.assertNotIn(default + '/.gitkeep', prepared)
                with self.assertRaisesRegex(ValueError, 'Instalación sin cambios'):
                    self.install(target=target, profile=profile, started=None)
                self.assertEqual(before, {path.relative_to(target): path.read_bytes() for path in target.rglob('*') if path.is_file()})
                self.assertFalse((target / default).exists())

    def test_cli_uses_profile_defaults_or_an_explicit_root(self):
        command = [sys.executable, '-B', str(KIT / 'scripts/init_project.py'), '--name', 'Proyecto CLI']
        cases = (('laravel', [], 'src'), ('laravel', ['--source-root', 'app/Contexts'], 'app/Contexts'),
                 ('go', [], 'internal'), ('go', ['--source-root', 'codigo'], 'codigo'),
                 ('flutter', [], 'lib'), ('flutter', ['--source-root', 'cliente/lib'], 'cliente/lib'))
        for index, (profile, options, expected) in enumerate(cases):
            with self.subTest(profile=profile, options=options):
                folder = str(index)
                target = self.root / folder
                result = subprocess.run(command + ['--target', str(target), '--profile', profile] + options, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                config = json.loads((target / '.agents/project.json').read_text())
                self.assertEqual(expected, config['source_root'])
                self.assertTrue((target / expected / '.gitkeep').is_file())
                if expected != 'src':
                    self.assertFalse((target / 'src').exists())
                if profile == 'go':
                    self.assertTrue((target / 'cmd/.gitkeep').is_file())

    def test_invalid_source_roots_do_not_create_target_files(self):
        for source_root in ('', '.', '..', '../outside', '/src', 'src/../outside', 'src//core', 'src/./core',
                            'src/', ' src', 'src\\core', 'C:/src', '.git/core', '.agents/core', 'docs/core', 'src\ncore'):
            with self.subTest(source_root=source_root), self.assertRaises(ValueError):
                self.install(source_root=source_root)
            self.assertFalse(self.target.exists())

    def test_incompatible_source_root_blocks_all_writes(self):
        for profile, root_name in (('base', 'src'), ('go', 'internal'), ('go', 'cmd'), ('flutter', 'lib')):
            with self.subTest(profile=profile, root=root_name):
                target = self.root / (profile + '-' + root_name)
                target.mkdir()
                source = target / root_name
                source.write_text('Existing file', encoding='utf-8')
                with self.assertRaises(ValueError):
                    self.install(target=target, profile=profile)
                self.assertEqual([source], list(target.iterdir()))
                self.assertEqual('Existing file', source.read_text())
                source.unlink()
                outside = self.root / ('external-' + profile + '-' + root_name)
                outside.mkdir()
                source.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(ValueError):
                    self.install(target=target, profile=profile)
                self.assertEqual([], list(outside.iterdir()))
                self.assertEqual([source], list(target.iterdir()))

    def test_existing_business_files_are_preserved_without_creating_framework_contexts(self):
        source = self.target / 'src/Orders/Domain/order.php'
        source.parent.mkdir(parents=True)
        source.write_text('Existing business code', encoding='utf-8')
        self.install(profile='laravel')
        self.assertEqual('Existing business code', source.read_text())
        self.assertFalse((self.target / 'app').exists())

    def test_conflicting_agents_or_managed_file_blocks_all_writes(self):
        self.target.mkdir()
        agents = self.target / 'AGENTS.md'
        agents.write_text('Existing instructions', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual('Existing instructions', agents.read_text())
        self.assertEqual([agents], list(self.target.iterdir()))
        agents.unlink()
        self.install()
        changed = self.target / 'docs/proyecto.md'
        changed.write_text('User changes', encoding='utf-8')
        before = {path.relative_to(self.target): path.read_bytes() for path in self.target.rglob('*') if path.is_file()}
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(before, {path.relative_to(self.target): path.read_bytes() for path in self.target.rglob('*') if path.is_file()})

    def test_symlink_destination_is_not_followed(self):
        self.target.mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        (self.target / '.agents').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual([], list(outside.iterdir()))
        self.assertFalse((self.target / 'AGENTS.md').exists())

    def test_invalid_names_dates_profiles_and_internal_targets_do_not_write(self):
        for changes in ({'name': 'two\nlines'}, {'started': '2026-02-30'}, {'profile': 'invented'}, {'target': KIT / 'nested'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.install(**changes)
        self.assertFalse(self.target.exists())

    def test_invalid_template_blocks_installation_before_target_creation(self):
        copied = self.root / 'broken-kit'
        shutil.copytree(KIT, copied, ignore=shutil.ignore_patterns('__pycache__'))
        (copied / 'templates/preparacion.md.in').write_text('# Empty\n', encoding='utf-8')
        with patch.object(initializer, 'KIT', copied), self.assertRaises(ValueError):
            self.install()
        self.assertFalse(self.target.exists())

    def test_missing_detail_reference_blocks_installation_before_target_creation(self):
        for index, relative in enumerate(('arquitectura-hexagonal-ddd/references/diseno-y-modelado.md',
                                          'manage-project-roadmap/references/herramientas.md')):
            with self.subTest(resource=relative):
                copied = self.root / ('incomplete-kit-' + str(index))
                shutil.copytree(KIT, copied, ignore=shutil.ignore_patterns('__pycache__'))
                (copied / 'skills' / relative).unlink()
                with patch.object(initializer, 'KIT', copied), self.assertRaisesRegex(ValueError, 'Recurso ausente'):
                    self.install()
                self.assertFalse(self.target.exists())


class PackageTest(unittest.TestCase):
    def test_reproducible_archive_can_be_moved_extracted_and_used_without_source_paths(self):
        with tempfile.TemporaryDirectory(prefix='kit-package-') as directory:
            root = Path(directory)
            first, second = root / 'first.zip', root / 'second.zip'
            packager.package(first)
            packager.package(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            moved = root / 'moved kit'
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                self.assertIn('kit-inicio-proyecto/PROMPT_MAESTRO.md', names)
                self.assertIn('kit-inicio-proyecto/MANIFEST.sha256', names)
                self.assertFalse(any('__pycache__' in name or name.endswith('.pyc') or '/.env' in name for name in names))
                archive.extractall(moved)
            extracted = moved / 'kit-inicio-proyecto'
            project = root / 'New project'
            result = subprocess.run([sys.executable, '-B', str(extracted / 'scripts/init_project.py'), '--target', str(project),
                                     '--name', 'Proyecto portable', '--profile', 'go', '--date', '2026-11-03'], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((project / 'internal/.gitkeep').is_file())
            self.assertTrue((project / 'cmd/.gitkeep').is_file())
            self.assertFalse((project / 'src').exists())
            self.assertTrue((project / 'docs/fuentes/README.md').is_file())
            command = [sys.executable, '-B', str(project / '.agents/skills/manage-project-roadmap/scripts/roadmap.py')]
            context = subprocess.run(command + ['task', 'INI-002', '--root', str(project), '--json'], capture_output=True, text=True)
            self.assertEqual(0, context.returncode, context.stderr)
            self.assertEqual('INI-001', json.loads(context.stdout)['dependencies'][0]['id'])
            report = subprocess.run(command + ['report', '--root', str(project), '--json'], capture_output=True, text=True)
            self.assertEqual(0, report.returncode, report.stderr)
            self.assertEqual(3, len(json.loads(report.stdout)['tasks']))
            rendered = subprocess.run(command + ['tree', '--root', str(project)], capture_output=True, text=True)
            self.assertEqual(0, rendered.returncode, rendered.stderr)
            self.assertTrue((project / 'docs/plan-maestro/visualizacion.html').is_file())


if __name__ == '__main__':
    unittest.main()
