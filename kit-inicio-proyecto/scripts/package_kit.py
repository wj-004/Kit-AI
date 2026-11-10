#!/usr/bin/env python3
"""Create a portable, reproducible archive from an explicit set of resources."""
from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
EXTENSIONS = {'.md', '.in', '.py', '.json', '.yaml', '.html', '.css', '.js'}


def resources() -> list[Path]:
    files = [KIT / 'README.md', KIT / 'PROMPT_MAESTRO.md', KIT / 'EVALUACION.md', KIT / 'EVALUACION_RESULTADOS.json']
    for folder in ('scripts', 'skills', 'templates', 'tests'):
        for path in (KIT / folder).rglob('*'):
            if path.is_symlink():
                raise ValueError('No empaquetar enlaces simbólicos: ' + str(path.relative_to(KIT)))
            if path.is_file() and path.suffix in EXTENSIONS and not any(part.startswith('.') or part == '__pycache__' for part in path.relative_to(KIT).parts):
                files.append(path)
    return sorted(set(files))


def package(output: Path) -> int:
    output = output.absolute()
    if output.suffix.lower() != '.zip' or output.resolve().is_relative_to(KIT.resolve()):
        raise ValueError('La salida debe ser un ZIP situado fuera de la carpeta del kit.')
    if output.is_symlink():
        raise ValueError('La salida no puede ser un enlace simbólico.')
    files = resources()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix='.kit-', suffix='.zip', dir=output.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    hashes = []
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                relative = path.relative_to(KIT).as_posix()
                data = path.read_bytes()
                entry = zipfile.ZipInfo('kit-inicio-proyecto/' + relative, date_time=(2020, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, data)
                hashes.append(hashlib.sha256(data).hexdigest() + '  ' + relative)
            entry = zipfile.ZipInfo('kit-inicio-proyecto/MANIFEST.sha256', date_time=(2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, '\n'.join(hashes) + '\n')
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return len(files)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Empaquetar el prompt y el kit sin cachés ni datos de aplicaciones.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        count = package(args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')
    print(f'{count} recursos y manifiesto empaquetados en {args.output.absolute()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
