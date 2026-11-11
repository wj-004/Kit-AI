"""Single parser and schema shared by validation, reports and the viewer (stdlib)."""
from __future__ import annotations

import json
import os
import stat
from contextlib import ExitStack
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_PATH = Path(__file__).resolve().parents[2] / 'plan-maestro-desarrollo-sistema/references/plan-schema.json'
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
FIELDS = tuple(SCHEMA['fields'])
STATES = tuple(SCHEMA['states'])
ID = SCHEMA['id_pattern']
HEADING = re.compile(r'^### \[([A-Z_]+)\] (' + ID + r') — (.+)$')
FIELD = re.compile(r'^- \*\*([^*\n]+):\*\*[ \t]*(.*)$')
PLACEHOLDERS = {'', 'pendiente', 'sin asignar', 'sin evidencia', 'hecho', 'todo', 'tbd', 'por completar', 'ninguno'}
IMAGE = re.compile(r'!\[([^\]\n]*)\]\(([^)\n]*)\)')
# Sin SVG: puede contener scripts.
IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def normalized(value: str) -> str:
    return value.strip(' .\t\r\n-').casefold()


def iso_date(value: str) -> date:
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Formato de fecha inválido.')
    return date.fromisoformat(value)


def read_evidence_image(path: Path, plan_dir: Path) -> bytes:
    """Read a bounded regular image without traversing symbolic links."""
    root = plan_dir.resolve()
    try:
        path = root / path.absolute().relative_to(plan_dir.absolute())
    except ValueError:
        raise ValueError('debe ser un archivo dentro del plan') from None
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('debe ser un archivo dentro del plan')
    for component in (path, *path.parents):
        if component == root:
            break
        if component.is_symlink():
            raise ValueError('no admite enlaces simbólicos')
    if resolved.suffix.lower() not in IMAGE_TYPES:
        raise ValueError('tiene un tipo no permitido (' + ', '.join(IMAGE_TYPES) + ')')
    if not resolved.is_file():
        raise ValueError('no existe como archivo regular')
    expected = resolved.stat()
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with ExitStack() as stack:
        if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY'):
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, directory)
            relative = resolved.relative_to(root)
            for name in relative.parts[:-1]:
                directory = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                stack.callback(os.close, directory)
            descriptor = os.open(relative.name, flags, dir_fd=directory)
        else:
            descriptor = os.open(resolved, flags)
        stream = stack.enter_context(os.fdopen(descriptor, 'rb'))
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
            raise ValueError('cambió durante la lectura')
        if opened.st_size > MAX_IMAGE_BYTES:
            raise ValueError(f'supera {MAX_IMAGE_BYTES // 1024 // 1024} MB')
        data = stream.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f'supera {MAX_IMAGE_BYTES // 1024 // 1024} MB')
        return data


def evidence_images(task: dict, plan_dir: Path) -> tuple[list, list]:
    """Images are relative to the task specification, never remote resources."""
    images, errors = [], []
    for alt, reference in IMAGE.findall(task['fields'].get('Evidencia actual', '')):
        try:
            if not alt.strip():
                raise ValueError('requiere texto alternativo')
            parsed = urlsplit(reference)
            if not reference.strip() or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or Path(reference).is_absolute():
                raise ValueError('requiere una ruta relativa local, sin URL')
            path = (plan_dir / task['source']).parent / reference
            read_evidence_image(path, plan_dir)
            images.append({'alt': alt.strip(), 'path': path.resolve().relative_to(plan_dir).as_posix()})
        except (OSError, ValueError) as error:
            problem = str(error) if isinstance(error, ValueError) else 'tiene una ruta inválida o cambió durante la lectura'
            errors.append(f"{task['id']}: la imagen {reference} {problem}.")
    return images, errors


def parse_plan(plan_dir: Path, overrides: dict[str, str] | None = None) -> dict:
    plan_dir = plan_dir.resolve()
    errors, tasks, sources, modules = [], [], {}, []
    index = plan_dir / 'README.md'
    try:
        if index.is_symlink() or not index.is_file():
            errors.append('Falta README.md regular como índice del plan.')
        elif SCHEMA['marker'] not in index.read_text(encoding='utf-8'):
            errors.append(f"El índice debe declarar {SCHEMA['marker']}.")
        paths = sorted(path for path in plan_dir.rglob('*.md') if path.name != 'README.md')
        for path in paths:
            relative = path.relative_to(plan_dir).as_posix()
            if path.is_symlink() or not path.resolve().is_relative_to(plan_dir):
                errors.append(f'{relative}: no se admiten fuentes enlazadas fuera del plan.')
                continue
            text = overrides[relative] if overrides and relative in overrides else path.read_text(encoding='utf-8')
            sources[relative] = text
            module = {'id': relative[:-3], 'title': path.stem}
            current, label, fence = None, None, None

            def finish() -> None:
                nonlocal current, label
                if current is not None:
                    current['fields'] = {key: '\n'.join(value).strip() for key, value in current['fields'].items()}
                    tasks.append(current)
                current, label = None, None

            for number, line in enumerate(text.splitlines(), 1):
                marker = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
                if marker:
                    if fence is None:
                        fence = (marker[1][0], len(marker[1]))
                    elif marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                        fence = None
                    if current is not None and label:
                        current['fields'][label].append(line)
                    continue
                if fence:
                    if current is not None and label:
                        current['fields'][label].append(line)
                    continue
                match = HEADING.fullmatch(line)
                if match:
                    finish()
                    current = {'id': match[2], 'status': match[1], 'title': match[3], 'module': module['id'],
                               'source': relative, 'line': number, 'fields': {}}
                    continue
                if re.match(r'^###\s+\[', line):
                    finish()
                    errors.append(f'{relative}:{number}: encabezado de tarea inválido.')
                    continue
                if re.match(r'^#{1,3}\s+', line):
                    finish()
                    if line.startswith('# '):
                        module['title'] = line[2:].strip()
                    continue
                if current is None:
                    continue
                field = FIELD.fullmatch(line)
                if field:
                    label = field[1]
                    if label in current['fields']:
                        errors.append(f"{current['id']}: campo duplicado {label}.")
                    current['fields'][label] = [field[2]]
                elif label:
                    current['fields'][label].append(line)
            if fence is not None:
                errors.append(f'{relative}: bloque de código sin cierre.')
            finish()
            if any(task['module'] == module['id'] for task in tasks):
                modules.append(module)
    except (OSError, UnicodeError) as error:
        errors.append(f'No se pudo leer el plan: {error}')
    if not tasks:
        errors.append('El plan no contiene tareas válidas.')
    by_id = {}
    for task in tasks:
        key, status, values = task['id'], task['status'], task['fields']
        if key in by_id:
            errors.append(f'{key}: ID duplicado.')
        by_id[key] = task
        if status not in STATES:
            errors.append(f'{key}: estado desconocido {status}.')
        for name in FIELDS:
            if not values.get(name):
                errors.append(f'{key}: campo obligatorio vacío o ausente: {name}.')
        for name in values.keys() - set(FIELDS):
            errors.append(f'{key}: campo desconocido: {name}.')
        scope = values.get('Capa', '')
        if scope not in SCHEMA['scopes']:
            errors.append(f'{key}: Capa debe pertenecer al esquema.')
        if scope == 'PROPUESTO' and status != 'PENDIENTE':
            errors.append(f'{key}: una propuesta requiere autorización antes de ejecutarse.')
        if (scope == 'EXCLUIDO') != (status == 'EXCLUIDO'):
            errors.append(f'{key}: capa y estado EXCLUIDO deben coincidir.')
        if status == 'EXCLUIDO' and not re.search(SCHEMA['decision_pattern'], values.get('Fuente', '')):
            errors.append(f'{key}: exclusión sin decisión explícita identificada en Fuente.')
        if status in {'EN_CURSO', 'PARCIAL', 'HECHO'} and normalized(values.get('Responsable', '')) in PLACEHOLDERS:
            errors.append(f'{key}: falta responsable asignado.')
        start = values.get('Fecha de inicio', '')
        updated = values.get('Última actualización', '')
        started = None
        try:
            if start != 'pendiente':
                started = iso_date(start)
            elif status in {'EN_CURSO', 'PARCIAL', 'HECHO'}:
                errors.append(f'{key}: el estado requiere Fecha de inicio válida.')
            last_update = iso_date(updated)
            if started and last_update < started:
                errors.append(f'{key}: Última actualización precede al inicio.')
        except ValueError:
            errors.append(f'{key}: fecha ISO inválida.')
        if status == 'HECHO' and normalized(values.get('Evidencia actual', '')) in PLACEHOLDERS:
            errors.append(f'{key}: HECHO requiere evidencia verificable.')
        dependency_text = values.get('Dependencias', '')
        if dependency_text == 'ninguna':
            task['dependencies'] = []
        elif re.fullmatch(ID + r'(?:,\s*' + ID + r')*', dependency_text):
            task['dependencies'] = list(dict.fromkeys(item.strip() for item in dependency_text.split(',')))
        else:
            task['dependencies'] = []
            errors.append(f'{key}: Dependencias requiere ninguna o IDs por comas.')
        task['scope'] = scope
        task['images'], image_errors = evidence_images(task, plan_dir)
        errors.extend(image_errors)
    for task in tasks:
        for prerequisite in task['dependencies']:
            if prerequisite not in by_id:
                errors.append(f"{task['id']}: dependencia inexistente {prerequisite}.")
            elif prerequisite == task['id']:
                errors.append(f"{task['id']}: dependencia de sí misma.")
            elif task['status'] == 'HECHO' and by_id[prerequisite]['status'] != 'HECHO':
                errors.append(f"{task['id']}: HECHO requiere cerrar {prerequisite}.")
    visited, active = set(), []

    def visit(key: str) -> None:
        if key in active:
            errors.append('Dependencias cíclicas: ' + ' → '.join(active[active.index(key):] + [key]))
            return
        if key in visited or key not in by_id:
            return
        active.append(key)
        for prerequisite in by_id[key]['dependencies']:
            visit(prerequisite)
        active.pop()
        visited.add(key)

    for key in by_id:
        visit(key)
    return {'valid': not errors, 'errors': errors, 'schemaVersion': SCHEMA['version'],
            'fieldNames': list(FIELDS), 'states': list(STATES), 'modules': modules, 'tasks': tasks,
            'edges': [{'from': dependency, 'to': task['id']} for task in tasks for dependency in task['dependencies']],
            'counts': dict(Counter(task['status'] for task in tasks)), 'sources': sources}
