from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from test_kit import PlanFixture, SCRIPTS, task
from plan_model import parse_plan
from roadmap_claim import claim_dir, release, reserve


class ClaimTest(PlanFixture):
    def setUp(self):
        super().setUp()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)

    def test_immediate_assignment_and_owner_checked_release(self):
        info = reserve(self.root, self.plan, 'QA-001', 'chat-uno')
        selected = parse_plan(self.plan)['tasks'][0]
        self.assertEqual('EN_CURSO', selected['status'])
        self.assertEqual('chat-uno', selected['fields']['Responsable'])
        self.assertNotEqual('pendiente', selected['fields']['Fecha de inicio'])
        self.assertTrue((claim_dir(self.root) / 'QA-001.json').is_file())
        with self.assertRaisesRegex(ValueError, 'ya tiene una reserva'):
            reserve(self.root, self.plan, 'QA-001', 'chat-dos')
        with self.assertRaisesRegex(ValueError, 'otro responsable'):
            release(self.root, self.plan, 'QA-001', 'chat-dos')
        with self.assertRaisesRegex(ValueError, 'Actualizá primero'):
            release(self.root, self.plan, 'QA-001', 'chat-uno')
        self.source.write_text(self.source.read_text().replace('[EN_CURSO]', '[PARCIAL]'))
        release(self.root, self.plan, 'QA-001', 'chat-uno')
        self.assertFalse((claim_dir(self.root) / 'QA-001.json').exists())
        self.assertEqual(str(self.root.resolve()), info['worktree'])

    def test_simultaneous_processes_only_one_wins(self):
        command = [sys.executable, '-B', str(SCRIPTS / 'roadmap.py'), 'claim', 'QA-001', '--root', str(self.root), '--owner']
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda owner: subprocess.run(command + [owner], capture_output=True, text=True), ['chat-uno', 'chat-dos']))
        self.assertEqual([0, 1], sorted(result.returncode for result in results))
        task_data = parse_plan(self.plan)['tasks'][0]
        self.assertEqual('EN_CURSO', task_data['status'])
        self.assertIn(task_data['fields']['Responsable'], {'chat-uno', 'chat-dos'})

    def test_shared_git_worktrees_observe_same_reservation(self):
        subprocess.run(['git', '-C', str(self.root), 'add', 'docs'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'base'], check=True)
        other = self.root.parent / (self.root.name + '-worktree')
        self.addCleanup(lambda: subprocess.run(['git', '-C', str(self.root), 'worktree', 'remove', '--force', str(other)], capture_output=True))
        subprocess.run(['git', '-C', str(self.root), 'worktree', 'add', '-qb', 'otra', str(other)], check=True)
        reserve(self.root, self.plan, 'QA-001', 'chat-uno')
        self.assertEqual(claim_dir(self.root), claim_dir(other))
        with self.assertRaisesRegex(ValueError, 'ya tiene una reserva'):
            reserve(other, other / 'docs/plan-maestro', 'QA-001', 'chat-dos')
        self.assertEqual('PENDIENTE', parse_plan(other / 'docs/plan-maestro')['tasks'][0]['status'])

    def test_rejects_unready_task_and_preserves_original(self):
        for content in (task(status='EN_CURSO'), task(scope='PROPUESTO'), task('QA-001', dependencies='QA-002') + task('QA-002')):
            with self.subTest(content=content):
                self.source.write_text(content)
                with self.assertRaises(ValueError):
                    reserve(self.root, self.plan, 'QA-001', 'chat-uno')
                self.assertEqual(content, self.source.read_text())
                self.assertFalse((claim_dir(self.root) / 'QA-001.json').exists())

    def test_partial_preserves_start_and_other_fields(self):
        content = task('MOD-UI-001', status='PARCIAL', **{'Fecha de inicio': '2020-01-02', 'Evidencia actual': 'Historial\n```\n- **Responsable:** ejemplo\n```'})
        self.source.write_text(content.replace('\n', '\r\n'))
        reserve(self.root, self.plan, 'MOD-UI-001', 'chat-dos')
        item = parse_plan(self.plan)['tasks'][0]
        self.assertEqual('2020-01-02', item['fields']['Fecha de inicio'])
        self.assertIn('- **Responsable:** ejemplo', item['fields']['Evidencia actual'])
        self.assertNotIn(b'\n', self.source.read_bytes().replace(b'\r\n', b''))

    def test_failed_write_leaves_no_reservation_or_changes(self):
        original = self.source.read_bytes()
        with patch('roadmap_claim.Path.replace', side_effect=OSError('falló')):
            with self.assertRaises(OSError):
                reserve(self.root, self.plan, 'QA-001', 'chat-uno')
        self.assertEqual(original, self.source.read_bytes())
        self.assertFalse((claim_dir(self.root) / 'QA-001.json').exists())
