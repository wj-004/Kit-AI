"""Cooperative local task reservation shared by Git worktrees."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from plan_model import FIELD, HEADING, ID, parse_plan


def claim_dir(root: Path) -> Path:
    try:
        result = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                cwd=root, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is None or result.returncode:
        raise ValueError('La reserva requiere un repositorio Git local compartido entre los chats.')
    return Path(result.stdout.strip()) / 'roadmap-claims'


@contextmanager
def guard(folder: Path):
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = folder / '.guard'
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as error:
        raise ValueError('Otra operación de reserva está en curso; volvé a intentarlo. Si quedó interrumpida, investigá antes de retirar .guard.') from error
    try:
        yield
    finally:
        lock.rmdir()


def validated(plan_dir: Path, task_id: str) -> tuple[dict, dict]:
    report = parse_plan(plan_dir)
    if not report['valid']:
        raise ValueError('Plan inválido:\n- ' + '\n- '.join(report['errors']))
    task = next((item for item in report['tasks'] if item['id'] == task_id), None)
    if task is None:
        raise ValueError(f'No existe la tarea {task_id}; creala primero con alcance autorizado.')
    return report, task


def task_key(task_id: str) -> str:
    if not re.fullmatch(ID, task_id):
        raise ValueError('ID de tarea inválido.')
    return task_id


def owner_name(owner: str) -> str:
    if not owner.strip() or len(owner) > 200 or any(ord(c) < 32 for c in owner):
        raise ValueError('Indicá un responsable único para este chat, en una sola línea.')
    return owner.strip()


def reserve(root: Path, plan_dir: Path, task_id: str, owner: str) -> dict:
    task_id, owner = task_key(task_id), owner_name(owner)
    folder = claim_dir(root)
    with guard(folder):
        reservation = folder / (task_id + '.json')
        if reservation.exists():
            raise ValueError(f'{task_id} ya tiene una reserva en {reservation}; no iniciar otra ejecución.')
        report, task = validated(plan_dir, task_id)
        if task['scope'] != 'SOLICITADO' or task['status'] not in {'PENDIENTE', 'PARCIAL'}:
            raise ValueError(f"{task_id}: solo se pueden reservar tareas SOLICITADO en PENDIENTE o PARCIAL; estado actual {task['status']}.")
        by_id = {item['id']: item for item in report['tasks']}
        pending = [key for key in task['dependencies'] if by_id[key]['status'] != 'HECHO']
        if pending:
            raise ValueError(f"{task_id}: requisitos sin cerrar: {', '.join(pending)}.")
        path = plan_dir / task['source']
        if any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(plan_dir)):
            raise ValueError('La fuente del plan no puede contener enlaces simbólicos.')
        before = path.read_bytes()
        text = before.decode('utf-8')
        newline = '\r\n' if b'\r\n' in before else '\n'
        lines = text.splitlines(keepends=True)
        start = task['line'] - 1
        match = HEADING.fullmatch(lines[start].rstrip('\r\n'))
        if not match or match[2] != task_id:
            raise ValueError('La tarea cambió durante la reserva; volvé a consultar el plan.')
        lines[start] = f'### [EN_CURSO] {task_id} — {task["title"]}{newline}'
        updates = {'Responsable': owner, 'Fecha de inicio': task['fields']['Fecha de inicio']
                   if task['fields']['Fecha de inicio'] != 'pendiente' else date.today().isoformat(),
                   'Última actualización': date.today().isoformat()}
        seen, fence = set(), None
        for index in range(start + 1, len(lines)):
            line = lines[index].rstrip('\r\n')
            marker = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
            if marker:
                if fence is None:
                    fence = (marker[1][0], len(marker[1]))
                elif marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                    fence = None
                continue
            if fence:
                continue
            if re.match(r'^#{1,3}\s+', line):
                break
            field = FIELD.fullmatch(line)
            if field and field[1] in updates:
                if index + 1 < len(lines) and lines[index + 1].strip() and not FIELD.fullmatch(lines[index + 1].rstrip('\r\n')) and not re.match(r'^#{1,3}\s+', lines[index + 1]):
                    raise ValueError(f'{task_id}: el campo {field[1]} debe ocupar una sola línea para reservar.')
                lines[index] = f'- **{field[1]}:** {updates[field[1]]}{newline}'
                seen.add(field[1])
        if seen != set(updates):
            raise ValueError('No se pudieron localizar los campos de asignación.')
        after = ''.join(lines)
        candidate = parse_plan(plan_dir, {task['source']: after})
        if not candidate['valid']:
            raise ValueError('La reserva produciría un plan inválido:\n- ' + '\n- '.join(candidate['errors']))
        import copy
        expected = copy.deepcopy(report['tasks'])
        selected = next(item for item in expected if item['id'] == task_id)
        selected['status'] = 'EN_CURSO'
        selected['fields'].update(updates)
        if expected != candidate['tasks']:
            raise ValueError('La reserva alteraría otros campos o tareas; no se guardó.')
        info = {'task': task_id, 'owner': owner, 'worktree': str(root.resolve()), 'plan': str(plan_dir.resolve())}
        temporary = None
        created = False
        try:
            with reservation.open('x', encoding='utf-8') as handle:
                created = True
                json.dump(info, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.roadmap-claim-', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(after.encode('utf-8'))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, path.stat().st_mode)
            if path.read_bytes() != before:
                raise ValueError('La fuente cambió durante la reserva; no se sobrescribió.')
            temporary.replace(path)
        except Exception:
            if created:
                reservation.unlink(missing_ok=True)
            raise
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return info


def release(root: Path, plan_dir: Path, task_id: str, owner: str) -> None:
    task_id, owner = task_key(task_id), owner_name(owner)
    folder = claim_dir(root)
    with guard(folder):
        reservation = folder / (task_id + '.json')
        if not reservation.is_file():
            raise ValueError(f'{task_id} no tiene una reserva local.')
        info = json.loads(reservation.read_text(encoding='utf-8'))
        if info != {'task': task_id, 'owner': owner, 'worktree': str(root.resolve()), 'plan': str(plan_dir.resolve())}:
            raise ValueError('La reserva pertenece a otro responsable o directorio de trabajo.')
        _, task = validated(plan_dir, task_id)
        if task['status'] == 'EN_CURSO':
            raise ValueError('Actualizá primero estado, evidencia y próximo paso; después liberá la reserva.')
        reservation.unlink()
