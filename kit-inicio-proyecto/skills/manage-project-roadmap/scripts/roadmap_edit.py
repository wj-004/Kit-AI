"""Review a task edit in memory before replacing its source; no commands from plan data."""
from __future__ import annotations

import copy
import difflib
import hashlib
import hmac
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from plan_model import FIELD, FIELDS, parse_plan

EDITABLE_FIELDS = tuple(name for name in FIELDS if name != 'Dependencias')


class EditConflict(ValueError):
    """The reviewed version is no longer current."""


def review_branch(root: Path) -> str:
    try:
        result = subprocess.run(['git', 'symbolic-ref', '--quiet', '--short', 'HEAD'], cwd=root,
                                capture_output=True, text=True, encoding='utf-8', timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('Se necesita una rama Git para revisar los cambios mediante Pull Request.') from error
    branch = result.stdout.strip()
    if result.returncode or not branch or branch in {'main', 'master'}:
        raise ValueError('Creá una rama Git distinta de main/master antes de guardar; revisá el diff mediante Pull Request.')
    return branch


def proposal(monitor, payload: dict) -> dict:
    """Resolve the source exclusively from the validated task, never from request paths."""
    if not isinstance(payload, dict) or set(payload) != {'taskId', 'revision', 'title', 'fields'}:
        raise ValueError('La propuesta requiere taskId, revision, title y fields; ID, estado y dependencias son de consulta.')
    if not monitor.graph or monitor.error or payload['revision'] != monitor.graph['revision']:
        raise EditConflict('El plan cambió o contiene errores. Actualizá y revisá nuevamente la tarea.')
    revision = monitor.fingerprint()
    if revision != payload['revision']:
        raise EditConflict('Las fuentes cambiaron. Actualizá y revisá nuevamente la tarea.')
    title, changes = payload['title'], payload['fields']
    if not isinstance(title, str) or not title.strip() or len(title) > 500 or any(c in title for c in '\r\n\0'):
        raise ValueError('El título debe ocupar una línea y tener entre 1 y 500 caracteres.')
    if not isinstance(changes, dict) or not set(changes) <= set(EDITABLE_FIELDS):
        raise ValueError('Campos no editables o desconocidos; las dependencias se conservan.')
    if any(not isinstance(value, str) or not value.strip() or '\r' in value or '\0' in value for value in changes.values()):
        raise ValueError('Los campos deben contener texto no vacío, con saltos de línea LF.')
    original = next((task for task in monitor.graph['tasks'] if task['id'] == payload['taskId']), None)
    if original is None:
        raise ValueError('La tarea no existe en el plan validado.')
    evidence = changes.get('Evidencia actual', original['fields']['Evidencia actual']).strip()
    if not evidence.startswith(original['fields']['Evidencia actual']):
        raise ValueError('Conservá la evidencia histórica; agregá las nuevas verificaciones al final del campo.')
    branch = review_branch(monitor.root)
    source = original['source']
    plan_dir = monitor.plan_dir.resolve()
    path = plan_dir / source
    if (any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(plan_dir))
            or not path.resolve().is_relative_to(plan_dir)):
        raise ValueError('La fuente debe ser un archivo regular dentro del plan, sin enlaces.')
    before_bytes = path.read_bytes()
    before = before_bytes.decode('utf-8')
    newline = '\r\n' if b'\r\n' in before_bytes else '\n'
    lines = before.splitlines(keepends=True)
    start, end, fence = original['line'] - 1, len(lines), None
    positions = {}
    for number in range(start + 1, len(lines)):
        line = lines[number].rstrip('\r\n')
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
            end = number
            break
        match = FIELD.fullmatch(line)
        if match:
            positions[match[1]] = number
    replacements = [(start, start + 1, f"### [{original['status']}] {original['id']} — {title.strip()}{newline}")]
    for name, value in changes.items():
        value = value.strip()
        if value == original['fields'][name]:
            continue
        begin = positions[name]
        stop = min((number for number in positions.values() if number > begin), default=end)
        trailing = ''.join(lines[begin:stop])
        trailing = re.search(r'(?:\r?\n[ \t]*)*$', trailing)[0]
        replacements.append((begin, stop, f'- **{name}:** ' + value.replace('\n', newline) + (trailing or newline)))
    for begin, stop, replacement in sorted(replacements, reverse=True):
        lines[begin:stop] = [replacement]
    after = ''.join(lines)
    report = parse_plan(monitor.plan_dir, {source: after})
    if not report['valid']:
        raise ValueError('Plan inválido:\n- ' + '\n- '.join(report['errors']))
    expected = copy.deepcopy(parse_plan(monitor.plan_dir)['tasks'])
    edited = next(task for task in expected if task['id'] == original['id'])
    edited['title'] = title.strip()
    edited['fields'].update({name: value.strip() for name, value in changes.items()})

    def semantic(tasks: list[dict]) -> list[dict]:
        return [{key: value for key, value in task.items() if key not in {'line', 'sourceUrl'}} for task in tasks]

    if semantic(expected) != semantic(report['tasks']):
        raise ValueError('La edición altera la estructura, otros campos o tareas. No se guardó ningún cambio.')
    if monitor.fingerprint() != revision:
        raise EditConflict('Las fuentes cambiaron durante la validación. Revisá nuevamente.')
    diff = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        fromfile=source, tofile=source))
    if not diff:
        raise ValueError('No hay cambios para guardar.')
    return {'source': source, 'path': path, 'before': before_bytes, 'after': after.encode('utf-8'),
            'revision': revision, 'diff': diff, 'branch': branch}


def approval_token(secret: str, payload: dict, reviewed: dict) -> str:
    content = json.dumps({'proposal': payload, 'diff': reviewed['diff'], 'branch': reviewed['branch']},
                         ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hmac.new(secret.encode(), content, hashlib.sha256).hexdigest()


def persist(monitor, reviewed: dict) -> None:
    """Replace only the reviewed file after rechecking the complete plan revision."""
    path, temporary = reviewed['path'], None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.roadmap-edit-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(reviewed['after'])
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, path.stat().st_mode)
        if (monitor.fingerprint() != reviewed['revision'] or path.read_bytes() != reviewed['before']
                or review_branch(monitor.root) != reviewed['branch']):
            raise EditConflict('El plan o la rama cambió antes de guardar. Revisá nuevamente.')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
