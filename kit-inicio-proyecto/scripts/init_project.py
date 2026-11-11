#!/usr/bin/env python3
"""Install preparation resources without overwriting an existing project."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path, PurePosixPath

KIT = Path(__file__).resolve().parents[1]
VERSION = '1.6.0'
PROFILES = {
    'base': 'stack por consultar; no se adopta un framework automáticamente',
    'laravel': 'Laravel confirmado; versiones, UI, persistencia e integraciones se relevan en el proyecto',
    'flutter': 'Flutter confirmado; plataformas, estado, backend y persistencia se relevan en el proyecto',
    'go': 'Go confirmado; transporte, persistencia y operación se relevan en el proyecto',
}
SOURCE_ROOTS = {'base': 'src', 'laravel': 'src', 'go': 'internal', 'flutter': 'lib'}
TEMPLATES = {
    'ver-plan.py.in': 'ver-plan.py',
    'AGENTS.md.in': 'AGENTS.md', 'proyecto.md.in': 'docs/proyecto.md',
    'arquitectura.md.in': 'docs/arquitectura/README.md', 'decisiones.md.in': 'docs/decisiones/README.md',
    'fuentes.md.in': 'docs/fuentes/README.md',
    'plan-index.md.in': 'docs/plan-maestro/README.md', 'preparacion.md.in': 'docs/plan-maestro/00-preparacion.md',
    'tarea.md': 'docs/plantillas/tarea.md', 'modulo.md': 'docs/plantillas/modulo.md',
    'decision.md': 'docs/plantillas/decision.md', 'traspaso.md': 'docs/plantillas/traspaso.md',
}


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def render(template: str, values: dict) -> str:
    def replace(match):
        if match[1] not in values:
            raise ValueError(f'Marcador de plantilla desconocido: {match[1]}')
        return values[match[1]]
    return re.sub(r'\{\{([A-Z_]+)\}\}', replace, template)


def prepare(target: Path, name: str, profile: str, started: str | None = None,
            source_root: str | None = None) -> dict[str, bytes]:
    if not name.strip() or len(name) > 120 or any(ord(char) < 32 for char in name):
        raise ValueError('Usar un nombre de proyecto de una línea, de 1 a 120 caracteres.')
    if profile not in PROFILES:
        raise ValueError(f'Perfil desconocido: {profile}')
    if target.resolve().is_relative_to(KIT.resolve()):
        raise ValueError('El proyecto de destino debe estar fuera de la carpeta del kit.')
    if (target / '.agents').is_symlink():
        raise ValueError('El directorio .agents del destino no puede ser un enlace simbólico.')
    previous = target / '.agents/project-kit.json'
    if previous.is_symlink():
        raise ValueError('El manifiesto existente no puede ser un enlace simbólico.')
    if previous.exists():
        old = json.loads(previous.read_text(encoding='utf-8'))
        if not isinstance(old, dict):
            raise ValueError('El manifiesto existente no es válido.')
        started = started or old.get('created_date')
        source_root = source_root if source_root is not None else old.get('source_root')
    default_source_root = SOURCE_ROOTS[profile]
    source_root = default_source_root if source_root is None else source_root
    if (not isinstance(source_root, str) or not source_root or source_root != source_root.strip()
            or any(ord(char) < 32 for char in source_root) or '\\' in source_root or ':' in source_root
            or PurePosixPath(source_root).is_absolute()
            or any(part in {'', '.', '..'} for part in source_root.split('/'))
            or source_root.split('/')[0] in {'.git', '.agents', '.codex', 'docs'}):
        raise ValueError('La raíz de código debe ser una ruta relativa dentro del proyecto, sin . ni .. ni directorios reservados.')
    started = started or date.today().isoformat()
    if not isinstance(started, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', started):
        raise ValueError('La fecha debe ser ISO: AAAA-MM-DD.')
    date.fromisoformat(started)
    layouts = {
        'base': f'`{source_root}/` es provisional hasta confirmar el stack; definir las rutas por componente al relevarlo.',
        'laravel': f'`{source_root}/<Contexto>/{{Domain,Application,Infrastructure,UI}}`; configurar un prefijo PSR-4 propio hacia esta raíz.',
        'go': f'`{source_root}/<contexto>/{{domain,application,adapters}}`; `cmd/<aplicacion>/main.go` inicia el proceso y `{source_root}/bootstrap/` conecta las dependencias.',
        'flutter': f'`{source_root}/contexts/<contexto>/{{domain,application,infrastructure,presentation}}`; `{source_root}/app/` contiene router, tema y composición, y `{source_root}/main.dart` inicia la aplicación. Extraer paquetes Dart cuando se necesite aislamiento de dependencias o reutilización.',
    }
    values = {'NAME': name, 'PROFILE': profile, 'PROFILE_DESCRIPTION': PROFILES[profile], 'DATE': started,
              'SOURCE_ROOT': source_root, 'DEFAULT_SOURCE_ROOT': default_source_root,
              'SOURCE_LAYOUT': layouts[profile]}
    files = {source_root + '/.gitkeep': b''}
    if profile == 'go':
        files['cmd/.gitkeep'] = b''
    for source, destination in TEMPLATES.items():
        files[destination] = render((KIT / 'templates' / source).read_text(encoding='utf-8'), values).encode('utf-8')
    required = (
        'arquitectura-hexagonal-ddd/SKILL.md', 'arquitectura-hexagonal-ddd/references/diseno-y-modelado.md',
        'manage-project-roadmap/references/herramientas.md', 'plan-maestro-desarrollo-sistema/SKILL.md',
        'plan-maestro-desarrollo-sistema/references/flujo-de-trabajo.md',
        'plan-maestro-desarrollo-sistema/references/plan-schema.json', 'manage-project-roadmap/SKILL.md',
        'manage-project-roadmap/scripts/plan_model.py', 'manage-project-roadmap/scripts/roadmap.py',
        'manage-project-roadmap/scripts/roadmap_server.py', 'manage-project-roadmap/scripts/roadmap_edit.py',
        'manage-project-roadmap/assets/roadmap-context.js', 'manage-project-roadmap/assets/roadmap-tree.html',
        'manage-project-roadmap/assets/roadmap-tree.js', 'manage-project-roadmap/assets/roadmap-tree.css',
    )
    for resource in required:
        if not (KIT / 'skills' / resource).is_file():
            raise ValueError(f'Recurso ausente del kit: skills/{resource}')
    for path in sorted((KIT / 'skills').rglob('*')):
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_symlink():
            raise ValueError(f'El kit no admite recursos enlazados: {path.name}')
        if path.is_file():
            files['.agents/skills/' + path.relative_to(KIT / 'skills').as_posix()] = path.read_bytes()
    files['.agents/project.json'] = encode({'name': values['NAME'], 'profile': profile,
                                           'stage': 'preparacion', 'plan_schema_version': 1,
                                           'source_root': source_root, 'source_root_default': default_source_root,
                                           'source_root_override': source_root != default_source_root,
                                           'sources_index': 'docs/fuentes/README.md'})
    files['.agents/project-kit.json'] = encode({'kit_version': VERSION, 'created_date': started,
                                               'source_root': source_root,
                                               'files_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}})
    return files


def preflight(target: Path, files: dict[str, bytes]) -> tuple[list[str], list[str]]:
    conflicts, unchanged = [], []
    if target.exists() and not target.is_dir():
        raise ValueError('El destino debe ser un directorio.')
    for relative, content in files.items():
        path = target / relative
        cursor = path
        unsafe = False
        while cursor != target:
            if cursor.is_symlink() or (cursor != path and cursor.exists() and not cursor.is_dir()):
                unsafe = True
                break
            cursor = cursor.parent
        if unsafe or path.is_symlink():
            conflicts.append(relative + ' (destino enlazado o padre incompatible)')
        elif path.exists():
            if path.is_file() and path.read_bytes() == content:
                unchanged.append(relative)
            else:
                conflicts.append(relative)
    if conflicts:
        raise ValueError('Instalación sin cambios: existen archivos diferentes o destinos incompatibles:\n- ' + '\n- '.join(conflicts))
    return sorted(set(files) - set(unchanged)), unchanged


def validate_prepared(files: dict[str, bytes]) -> None:
    scripts = KIT / 'skills/manage-project-roadmap/scripts'
    sys.path.insert(0, str(scripts))
    from plan_model import parse_plan
    with tempfile.TemporaryDirectory(prefix='kit-plan-check-') as directory:
        root = Path(directory)
        for relative, content in files.items():
            if relative.startswith('docs/plan-maestro/'):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        report = parse_plan(root / 'docs/plan-maestro')
        if not report['valid']:
            raise ValueError('El plan generado no es válido:\n- ' + '\n- '.join(report['errors']))


def install(target: Path, name: str, profile: str = 'base', started: str | None = None, dry_run: bool = False,
            source_root: str | None = None) -> dict:
    target = target.resolve()
    files = prepare(target, name, profile, started, source_root)
    created, unchanged = preflight(target, files)
    validate_prepared(files)
    if not dry_run:
        written = []
        try:
            for relative in created:
                path = target / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation also protects a file added after preflight.
                with path.open('xb') as handle:
                    written.append(path)
                    handle.write(files[relative])
        except OSError:
            for path in reversed(written):
                path.unlink(missing_ok=True)
            raise
    return {'target': str(target), 'profile': profile, 'dry_run': dry_run,
            'create': created, 'unchanged': sorted(unchanged)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Preparar skills, arquitectura y plan sin generar código de producto.')
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--profile', choices=PROFILES, default='base')
    parser.add_argument('--date', help='Fecha inicial ISO; por defecto hoy o la fecha de la instalación existente.')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--source-root', help='Raíz relativa elegida por el usuario en lugar de la del perfil: base/Laravel src, Go internal, Flutter lib.')
    args = parser.parse_args(argv)
    try:
        result = install(args.target, args.name, args.profile, args.date, args.dry_run, args.source_root)
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
