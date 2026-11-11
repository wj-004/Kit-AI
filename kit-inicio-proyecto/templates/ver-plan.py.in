#!/usr/bin/env python3
"""Abrir el árbol del proyecto sin configurar puertos ni depender del directorio actual."""
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / '.agents/skills/manage-project-roadmap/scripts'))
    from roadmap import main as roadmap_main
    return roadmap_main(['open', '--root', str(root), *sys.argv[1:]])


if __name__ == '__main__':
    raise SystemExit(main())
