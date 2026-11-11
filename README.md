# Promt-AI

Prompt maestro y kit reutilizable para iniciar proyectos con arquitectura hexagonal y DDD, tres skills, plantillas, validador y visor del plan maestro.

El agente consulta las fuentes, los requisitos y el stack al comenzar cada proyecto. Reutiliza las decisiones ya informadas y puede trabajar con varios stacks por componente. Laravel organiza los contextos en `src/`; los servicios Go, en `internal/` con arranque en `cmd/`; Flutter, en `lib/`. El perfil base conserva `src/` provisional hasta confirmar el stack. El arranque prepara esas rutas, arquitectura, skills, plan y visor; las funcionalidades se desarrollan cuando el usuario las solicita.

## Empezar un proyecto

1. Abrí el [prompt maestro](kit-inicio-proyecto/PROMPT_MAESTRO.md).
2. Usá la carpeta `kit-inicio-proyecto` desde tu copia del repositorio o adjuntala al chat del nuevo proyecto. El [ZIP del kit](dist/kit-inicio-proyecto.zip) es una alternativa opcional para transportarlo.
3. Pegá el prompt e indicá los datos que ya conocés. El agente consulta las fuentes y el stack que falten antes de cerrar el relevamiento y aplicar un perfil.

La [guía del kit](kit-inicio-proyecto/README.md) explica la instalación, el formato del plan, los comandos y sus límites.

Antes de implementar cualquier tarea, incluso una corrección breve, el agente debe guardarla EN_CURSO con responsable y fecha de inicio reales. El validador comprueba esos campos; la secuencia previa a la implementación es una obligación del flujo, no un bloqueo automático del editor.

La preparación lee las fuentes y arma el plan. Después, AGENTS.md y el contexto de una tarea guían la ejecución; las referencias técnicas se abren cuando hacen falta. Los requerimientos originales se releen solo por pedido expreso del usuario. Las skills de arquitectura, planificación y visor se aplican según el cambio, sin cargarlas todas para una corrección corriente. El [flujo ampliado](kit-inicio-proyecto/skills/plan-maestro-desarrollo-sistema/references/flujo-de-trabajo.md) se consulta para preparar, reorganizar o retomar con información insuficiente.

## Instalación desde una copia del repositorio

Requiere Python 3.9 o posterior; las herramientas usan su biblioteca estándar.

```sh
git clone https://github.com/wj-004/Promt-AI.git
cd Promt-AI/kit-inicio-proyecto
python3 -B scripts/init_project.py --target /ruta/al/proyecto --name "Mi proyecto" --profile base --dry-run
```

Cuando se hayan revisado los destinos, repetí el comando sin `--dry-run`. Elegí `--profile laravel`, `--profile go` o `--profile flutter` si el stack ya está confirmado; `base` conserva la decisión pendiente. El instalador prepara `.gitkeep` en `src/` para base/Laravel, en `internal/` y `cmd/` para Go, y en `lib/` para Flutter. No sobrescribe archivos diferentes ni genera código funcional del producto. `--source-root` permite una raíz distinta elegida por el usuario; las rutas existentes se conservan hasta una conciliación autorizada.

Las fuentes pueden ser adjuntos, enlaces, texto del chat o archivos en su ubicación actual. `docs/fuentes/README.md` es el índice que se instala en el proyecto, con la consulta pendiente hasta registrar tu respuesta. No hay que depositar los documentos en una carpeta para que el agente los solicite o analice.

## Consultar una tarea

Desde un proyecto preparado, sustituir INI-001 por la tarea elegida:

```sh
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py task INI-001 --format context
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py task INI-001 --format json
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py report --status EN_CURSO --summary
```

La consulta valida el plan completo antes de devolver una tarea con todos sus campos y resúmenes de dependencias. No escribe archivos. Los comandos anteriores siguen disponibles; --summary conserva errores y contadores sin volcar el listado. La versión 1.6.0 mantiene el esquema 1 y las rutas por stack, con una entrada breve y detalles bajo consulta. Domain conserva entidades, valores y agregados según identidad, invariantes y consistencia del modelo.

## Skills incluidas

| Skill | Función |
| --- | --- |
| [arquitectura-hexagonal-ddd](kit-inicio-proyecto/skills/arquitectura-hexagonal-ddd/SKILL.md) | Reglas del núcleo, puertos, adaptadores, contextos y perfiles tecnológicos. |
| [plan-maestro-desarrollo-sistema](kit-inicio-proyecto/skills/plan-maestro-desarrollo-sistema/SKILL.md) | Relevamiento, alcance, tareas, criterios de aceptación y evidencia. |
| [manage-project-roadmap](kit-inicio-proyecto/skills/manage-project-roadmap/SKILL.md) | Validación, consultas, exportación y visor interactivo del plan. |

## Visor del plan maestro

El visor ofrece búsqueda, filtros, detalle de tareas, zoom y cadenas de dependencias. Puede exportarse como HTML o sincronizarse con los documentos mediante un servidor local. Desde un proyecto actualizado, ejecutá `python3 -B ver-plan.py`: abre el navegador y elige un puerto libre. Ctrl+C lo detiene; `--static` abre una copia sin servidor. La PR #3 agrega edición revisada y contexto de tareas para Codex.

![Visor del plan maestro en un proyecto de demostración](docs/visor-plan-maestro.jpg)

## Verificación

Desde `kit-inicio-proyecto`:

```sh
python3 -B -m unittest discover -s tests -v
node --check skills/manage-project-roadmap/assets/roadmap-tree.js
node --check skills/manage-project-roadmap/assets/roadmap-context.js
node --test tests/roadmap-context.test.js
```

Node se usa para comprobar la sintaxis y las pruebas JavaScript; no es una dependencia de ejecución del kit. Las pruebas HTTP requieren permitir servidores temporales en loopback.

El ZIP es opcional; la instalación y las pruebas funcionan directamente desde el repositorio. Contiene los recursos del kit y un `MANIFEST.sha256`. Para generarlo:

```sh
python3 -B scripts/package_kit.py --output ../dist/kit-inicio-proyecto.zip
```

[EVALUACION.md](kit-inicio-proyecto/EVALUACION.md) conserva mediciones de la CLI y de ensayos aislados con Codex, con su alcance y límites. Un resultado de una tarea no se presenta como ahorro general para todos los proyectos.
