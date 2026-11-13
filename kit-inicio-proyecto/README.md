# Kit de inicio de proyectos

Base para preparar proyectos con arquitectura hexagonal y DDD, consultar fuentes y stack y mantener un plan maestro con visor. La organización se adapta al stack confirmado: Laravel en `src/`, servicios Go en `internal/` y `cmd/`, Flutter en `lib/`. Requiere Python 3.9 o posterior para las herramientas; no requiere paquetes Python ni un framework de producto. El perfil se elige con el usuario al iniciar cada proyecto.

## Uso habitual

1. Usar esta carpeta desde una copia del repositorio o adjuntarla completa al chat del proyecto nuevo. El ZIP es opcional y solo facilita el traslado.
2. Pegar [PROMPT_MAESTRO.md](PROMPT_MAESTRO.md) y completar los datos conocidos.
3. El agente pregunta explícitamente qué fuentes usar y si hay otras además de las detectadas, consulta requisitos y stack pendientes y prepara el proyecto. El código funcional empieza cuando se lo solicites.

## Fuentes y consulta inicial

Las fuentes son tu descripción, documentos, planes previos, diseños, contratos de API o sistemas de referencia; el código y las pruebas existentes sirven de evidencia. No hay un directorio obligatorio para entregarlas: pueden ser adjuntos, enlaces, mensajes o archivos en su ubicación actual.

El agente registra tu respuesta y el inventario en `docs/fuentes/README.md`. Ese índice empieza con la consulta pendiente. Antes de cerrar INI-001 debe recibir y registrar la respuesta, aunque sea «no tengo documentos adicionales; partimos de mi descripción». Encontrar adjuntos no reemplaza preguntar si hay otras fuentes. Si ya contestaste explícitamente, se conserva esa respuesta sin repetir. Podés guardar copias locales en `docs/fuentes/documentos/` si te sirve; es opcional.

El prompt contiene la especificación para generar una base compatible si el kit no está adjunto; si está disponible, reutilizar sus recursos. Después del arranque, AGENTS.md y `roadmap.py claim ID --owner "identificador único del chat"` guían la toma inmediata de una tarea autorizada. Para consultas sin trabajar en ella, usar `roadmap.py task ID --format context`. Las referencias son ubicaciones, no una lista de lectura obligatoria. El [flujo ampliado](skills/plan-maestro-desarrollo-sistema/references/flujo-de-trabajo.md) se consulta para preparar, reorganizar o retomar con información insuficiente. No volver a pegar el prompt ni reinstalar/relevar por rutina al ejecutar una tarea.

Las fuentes y los requerimientos originales se leen durante el relevamiento y se incorporan al plan con criterios suficientes. Una vez armado el plan, se usan sus tareas para ejecutar y retomar; los originales se releen solo por pedido expreso del usuario. Si el plan no resuelve una duda, se consulta esa duda y se continúa con lo independiente.

Las skills conservan activación automática con alcance acotado: arquitectura para nuevos modelos o cambios de reglas/fronteras, planificación para preparar o reorganizar, y roadmap para sus herramientas o visor. Los detalles de modelado y del visor están en referencias separadas. Una corrección que conserva el contrato existente no exige cargar las tres skills. Al tomar una tarea autorizada, antes de investigar o trabajar, `claim` la reserva y la guarda EN_CURSO con responsable y fechas reales. Si falta, se crea primero; al retomar una tarea PARCIAL se conserva el inicio original. Al cerrar o interrumpir se actualizan estado, evidencia y próximo paso, se valida el plan y se libera con `release`. El esquema mantiene sus catorce campos y la validación global.

Ejemplos de pedidos: «Prepará este repositorio con el kit» inicia el relevamiento; «Implementá RF-036» consulta esa tarea autorizada y sus referencias; «Retomá RF-036» contrasta su evidencia con los cambios desde el último estado comprobado. RF-036 es un ejemplo, no una tarea preinstalada.

## Instalación de los recursos

Desde esta carpeta, primero podés ver lo que se crearía:

```sh
python3 -B scripts/init_project.py --target /ruta/al/proyecto --name "Mi proyecto" --profile base --dry-run
```

Para crearlo:

```sh
python3 -B scripts/init_project.py --target /ruta/al/proyecto --name "Mi proyecto" --profile base
```

Perfiles disponibles: `base` (stack pendiente), `laravel`, `flutter` y `go`. Son guías de adaptación, no selección automática de lenguaje, versión, UI, ORM o proveedor. Cuando el usuario confirma una combinación distinta, el agente completa el perfil local respetando las reglas comunes.

Un proyecto puede combinar stacks. `--profile` indica la guía inicial de instalación; la ficha conserva el stack y las rutas de cada componente y la skill de arquitectura consulta los perfiles que correspondan. Por ejemplo, un backend Go puede vivir en `backend/` con `go.mod`, `internal/` y `cmd/`, y el cliente Flutter en `mobile/` con `pubspec.yaml` y `lib/`. Esa distribución se define al relevar el proyecto; el instalador no crea aplicaciones ni detecta componentes automáticamente. Un único kit y plan pueden coordinar ambos componentes, sin imponerles una raíz común.

El instalador no sobrescribe archivos diferentes, no sigue enlaces simbólicos en sus destinos y comprueba todas las colisiones antes de escribir. Una repetición con la misma configuración conserva los archivos idénticos. Si ya existe `AGENTS.md`, un plan u otra skill con contenido distinto, informa las rutas en conflicto sin crear un proyecto parcial; el agente debe conciliar esa instalación existente. Prepara `.gitkeep` en las rutas del perfil, sin contextos inventados, dependencias del producto ni código funcional.

## Organización por stack

Las rutas siguientes son relativas a la raíz del repositorio o del componente correspondiente. Se conserva la arquitectura por bounded context y se adapta el empaquetado:

| Perfil | Organización prevista | Rutas preparadas por el instalador |
| --- | --- | --- |
| `base` | Stack pendiente; `src/` provisional hasta confirmarlo | `src/.gitkeep` |
| `laravel` | `src/<Contexto>/{Domain,Application,Infrastructure,UI}` y autoload PSR-4 propio | `src/.gitkeep` |
| `go` | `internal/<contexto>/{domain,application,adapters}`, composición en `internal/bootstrap/` y arranque en `cmd/<aplicacion>/main.go` | `internal/.gitkeep`, `cmd/.gitkeep` |
| `flutter` | `lib/contexts/<contexto>/{domain,application,infrastructure,presentation}`, composición en `lib/app/` y arranque en `lib/main.dart` | `lib/.gitkeep` |

Los nombres de contextos son ejemplos de organización, no módulos instalados. En Go, `internal/` en la raíz no impide imports entre contextos hermanos: sus fronteras y contratos se verifican. En Flutter, el núcleo usa Dart sin imports de Flutter ni adaptadores. Cuando se necesite aislamiento de dependencias o reutilización, se puede extraer un paquete como `packages/ventas_core/`, con API pública, implementación en `lib/src/`, pruebas propias y un `pubspec.yaml` sin Flutter. No se impone un paquete por cada capa. Los perfiles explican los detalles y referencias oficiales.

Si el usuario elige otra raíz, registrar solicitud y fecha en arquitectura y decisiones y usar `--source-root ruta/relativa`. En Go esta opción cambia la raíz de la lógica; el arranque sigue en `cmd/`. `.agents/project.json` registra `source_root`, `source_root_default` del perfil y `source_root_override` (diferencia respecto del valor predeterminado). Este indicador no prueba que una ruta heredada haya sido elegida expresamente. Las repeticiones conservan la raíz registrada en `.agents/project-kit.json` y la fecha inicial.

Para actualizar una instalación anterior, conciliar AGENTS, skills y documentación con esta versión y registrar las rutas y la consulta de fuentes. Las instalaciones antiguas de Go/Flutter bajo `src/` conservan esa ruta al preparar una repetición; los archivos diferentes causan un rechazo sin escrituras. No volver a ejecutar el instalador para sobrescribirlos ni mover código existente automáticamente: un traslado requiere un pedido que cubra esa refactorización. Al resolver el stack de un perfil base, conciliar su ruta provisional con la estructura del componente, sin migraciones automáticas.

La mejora de instrucciones requiere actualizar el AGENTS.md y las tres skills locales de cada proyecto ya integrado, preservando sus reglas y datos propios. Cambiar esta copia del kit no modifica los proyectos instalados ni las skills globales. Para sumar el acceso directo, copiar `templates/ver-plan.py.in` como `ver-plan.py` en la raíz del proyecto, sin sobrescribir un archivo propio; el lanzador usa la skill local actualizada. Si hay varias copias de una skill, revisar cuál se está usando; el instalador no las elimina ni actualiza automáticamente.

## Recursos instalados

```text
AGENTS.md
ver-plan.py
<raíz-del-perfil>/.gitkeep
.agents/project.json
.agents/project-kit.json
.agents/skills/arquitectura-hexagonal-ddd/
.agents/skills/plan-maestro-desarrollo-sistema/
.agents/skills/manage-project-roadmap/
docs/proyecto.md
docs/fuentes/README.md
docs/arquitectura/README.md
docs/decisiones/README.md
docs/plan-maestro/README.md
docs/plan-maestro/00-preparacion.md
docs/plantillas/
```

Se preparan tres tareas iniciales de relevamiento/arquitectura/plan, todas pendientes. No hay requisitos de negocio ficticios ni funcionalidades declaradas terminadas. Las decisiones, módulos y tareas reales se agregan al analizar el proyecto. Las skills globales y los proyectos que sirvieron de referencia permanecen fuera de esta instalación.

En Go se prepara además `cmd/.gitkeep`. No se crean `go.mod`, `pubspec.yaml`, archivos de arranque, contextos ni paquetes Dart durante esta preparación.

## Comandos desde el proyecto preparado

```sh
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py check
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py task INI-001 --format context
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py task INI-001 --format json
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py report --status EN_CURSO --summary
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py report --status EN_CURSO
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py report --json
python3 -B .agents/skills/manage-project-roadmap/scripts/roadmap.py tree
python3 -B ver-plan.py
```

`python3 -B ver-plan.py` valida el plan, abre el navegador y mantiene el árbol sincronizado en un puerto libre. No requiere pedirle al agente una URL ni elegir un puerto. Ctrl+C detiene el servicio. `python3 -B ver-plan.py --static` regenera y abre una copia sin servidor; para edición revisada, usar `python3 -B ver-plan.py --allow-edit` en una rama Git distinta de main/master. La ruta del proyecto se toma del lanzador, incluso al ejecutarlo desde otra carpeta. Si no hay navegador disponible, se imprime el enlace.

El HTML se exporta a `docs/plan-maestro/visualizacion.html`. El servicio local imprime su URL; `--port 0` solicita un puerto libre al sistema y Ctrl+C lo detiene. Las opciones `--root`, `--plan-dir` y `--output` permiten usar otros directorios sin mover los scripts. No se sirven archivos del repositorio mediante un servidor de directorios genérico.

`task ID` valida todo el plan antes del recorte y muestra la tarea completa, sin truncar campos, con archivo/línea y dependencias directas resumidas. `--format json` (o `--json`) ofrece la misma información estructurada. No abre referencias ni ejecuta instrucciones de los campos y no escribe archivos; por eso rechaza `--output`, filtros y `--summary`. ID inexistente o plan inválido devuelve código 1; argumentos inválidos, 2. No hace falta ejecutar check inmediatamente antes de una consulta que ya valida el mismo plan.

`report --summary` omite el listado de tareas; junto con `--json` devuelve contadores globales, cantidad seleccionada y todos los errores. No altera la validación global ni limita el diagnóstico de un plan inválido. `check` ya es breve y `report --json` mantiene la salida completa anterior. Resumir no significa ignorar errores ni considerar correcta una salida truncada.

Los scripts de esta carpeta usan el mismo código que se instala. Para probar todo el kit:

```sh
python3 -B -m unittest discover -s tests -v
node --check skills/manage-project-roadmap/assets/roadmap-tree.js
node --check skills/manage-project-roadmap/assets/roadmap-context.js
node --test tests/roadmap-context.test.js
```

La suite incluye pruebas HTTP en loopback. En un entorno que bloquee la apertura de puertos se necesita la capacidad de ejecutar servidores locales; no hay que cambiar las comprobaciones para obtener un resultado verde.

## Formato compartido y portabilidad

La autoridad del formato está en [plan-schema.json](skills/plan-maestro-desarrollo-sistema/references/plan-schema.json); [plan-schema.md](skills/plan-maestro-desarrollo-sistema/references/plan-schema.md) explica su significado. El parser lo carga y el visor recibe sus campos y estados del parser. La versión 1 usa catorce campos, dependencias por comas y `EXCLUIDO`, sin atribuir un presupuesto inexistente.

La base deriva de las reglas y herramientas de planificación anteriores, pero elimina sus referencias de producto y unifica los esquemas. No migra automáticamente planes con nueve campos o dependencias por punto y coma. Copiar este kit a un proyecto nuevo no cambia el plan ni las skills del repositorio donde se preparó.

Para empaquetar una copia limpia cuando se necesite transportar el kit (opcional):

```sh
python3 -B scripts/package_kit.py --output /ruta/kit-inicio-proyecto.zip
```

Se incluyen únicamente prompt, documentación, scripts, skills, plantillas y pruebas; no se agregan `.env`, cachés, proyectos temporales, capturas ni datos de una aplicación.

La versión 1.7.0 agrega la reserva inmediata al tomar una tarea y su liberación al cerrar o interrumpir. La versión 1.6.0 incorporó el lanzador ver-plan.py y la edición revisada/contexto para Codex de la PR #3. Conserva el esquema 1, los catorce campos, las rutas por stack y los comandos anteriores, incluidos task y --summary. Reduce la entrada de ejecución y separa detalles de arquitectura y visor para consultarlos cuando hagan falta. Mantiene evidencia visual y microinteracciones; las instalaciones anteriores se concilian preservando datos y evidencia. El procedimiento y las mediciones disponibles están en [EVALUACION.md](EVALUACION.md), sin extrapolar un ensayo a todos los proyectos.

## Evidencia visual de las tareas

En Evidencia actual se pueden declarar capturas con `![Descripción](capturas/despues.png)`, relativas al Markdown de la tarea y dentro de docs/plan-maestro. Requieren descripción, formato PNG/JPG/GIF/WebP y hasta 5 MB por archivo; se rechazan rutas externas, URL, SVG y enlaces simbólicos, incluidos directorios enlazados. La lectura se limita y se comprueba nuevamente al exportar.

La galería del detalle conserva el texto original, permite ampliar y recorrer imágenes con botones/flechas y se incluye como data URI en el HTML offline. El servidor no expone rutas de imágenes y detecta sus cambios. El HTML crece con las capturas; no incluir secretos ni datos personales. Esta validación puede rechazar imágenes Markdown antiguas con rutas que no cumplan esas condiciones, sin cambiar el esquema 1 ni los catorce campos. Las consultas task y report --summary se conservan.

La versión 1.3.0 integra evidencia visual y microinteracciones. La galería permite ampliar imágenes y recorrerlas con teclado; las transiciones respetan prefers-reduced-motion y no requieren dependencias. Los navegadores sin Web Animations API conservan la navegación sin animación.
