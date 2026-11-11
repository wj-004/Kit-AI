# Comparación reproducible de versiones

La comparación de herramientas y la evaluación con un agente responden preguntas distintas. No convertir bytes, líneas o caracteres en tokens estimados ni atribuir porcentajes de ahorro sin mediciones del entorno.

## Comparación Laravel 1.4.0 y 1.5.0 — 2026-11-10

Cuatro ejecuciones aisladas, en orden ABBA, con los commits publicados `1e2ff97` (1.4.0) y `f2e8c0e` (1.5.0), sin modificar sus instrucciones. Misma tarea EVAL-001, código, criterios completos del plan y dependencias fijadas por el mismo composer.lock. Modelo `gpt-6.1-sol`, esfuerzo `xhigh`, CLI `codex-cli 0.166.0-alpha.6`. PHP 8.4.11, Laravel Framework 12.72.0 y PHPUnit 11.5.57.

La corrección exige rechazar cantidad cero en CartLine y en POST /api/cart/total, conservando precio cero, carrito vacío, errores por campo, API y totales válidos. La aplicación Laravel es temporal: usa arquitectura hexagonal en src/Cart, contenedor y validación HTTP reales. Las 8 pruebas iniciales pasan. Antes de corregir, las 13 verificaciones independientes detectan exactamente cuatro fallos de cantidad cero y ningún error del entorno. Las dependencias se prepararon una vez; Composer y el calentamiento de Laravel quedan fuera del tiempo medido.

| Mediana de dos ejecuciones por versión | 1.4.0 | 1.5.0 |
| --- | ---: | ---: |
| Tiempo total, segundos | 100.7 | 64.3 |
| Primer cambio PHP, incluidas pruebas, segundos | 56.0 | 39.9 |
| Comandos registrados | 15.0 | 10.5 |
| Tokens de entrada acumulados | 270649.5 | 170577.5 |
| De ellos, cacheados | 244672.0 | 153344.0 |
| Entrada no cacheada | 25977.5 | 17233.5 |
| Tokens de salida | 5811.0 | 3551.5 |
| Ejecuciones con relectura observada del original | 1 de 2 | 0 de 2 |

Tiempos individuales: 1.4.0, [96.81, 104.622]; 1.5.0, [64.356, 64.165]. Reducciones observadas de medianas en este caso: 36.2% en tiempo, 37.0% en entrada acumulada y 38.9% en salida. Los contadores provienen de Codex; la entrada incluye caché y no se interpreta como precio.

Las cuatro soluciones pasaron las mismas 13 verificaciones independientes y conservaron las 8 pruebas iniciales, composer.json/composer.lock y el plan válido con EVAL-001 HECHO y 14 campos. El núcleo no incorporó imports Laravel. Las regresiones adicionales escritas por cada agente varían: los totales, incluida aceptación, fueron [34, 31] para 1.4.0 y [32, 32] para 1.5.0. Se compara el trabajo completo con los mismos criterios, sin atribuir velocidad de una suite a otra con distinta cobertura adicional.

[Datos, fixture, aceptación independiente, versiones, controles y comandos](EVALUACION_RESULTADOS.json), sección `laravel_comparison_2026_11_10`. El ensayo cubre una corrección pequeña sin persistencia, permisos o frontend; faltan casos mayores para generalizar. Las pruebas HTTP se basan en las [herramientas oficiales de Laravel](https://laravel.com/framework/docs/12.x/http-tests).

## Ejecución breve y lectura de fuentes — 2026-11-10

Se comparó el kit 1.4.0 de `1e2ff97` con la versión 1.5.0 de esta entrega, instalada desde sus archivos reales. Fixture sintético Go: corregir cantidades cero en un carrito, manteniendo API, pruebas existentes y criterios completos en EVAL-001. El pedido refiere al ID del plan, sin pedir releer el requerimiento original. Modelo `gpt-6.1-sol`, esfuerzo `xhigh` y CLI `codex-cli 0.166.0-alpha.6`; no se cambiaron entre variantes.

| Mediana de dos ejecuciones por versión | 1.4.0 | 1.5.0 final |
| --- | ---: | ---: |
| Tiempo total, segundos | 86.0 | 61.8 |
| Primer cambio Go, incluidas pruebas, segundos | 48.0 | 34.8 |
| Comandos ejecutados | 19.0 | 15.0 |
| Tokens de entrada acumulados, incluida caché | 263152.5 | 157433.5 |
| Tokens de salida | 4770.5 | 3100.5 |
| Ejecuciones con relectura observada del original | 2 de 2 | 0 de 2 |

Tiempos individuales: 1.4.0, [84.071, 87.867]; 1.5.0 final, [55.562, 67.981]. La reducción observada de la mediana fue 28.1% en tiempo y 35.0% en tokens de salida para este caso. Las cuatro ejecuciones principales pasaron la aceptación independiente; ambas versiones conservaron el plan válido, la tarea HECHO y los catorce campos. Los contadores de entrada son acumulados y contienen caché; no se equiparan a palabras, precio ni ahorro general.

Se conservan dos ejecuciones intermedias: la primera revisión breve mejoró tiempo pero releyó un original en una de ellas. Ese hallazgo motivó colocar la prohibición al principio de AGENTS.md y devolver `readingPolicy` junto al contexto de la tarea; después se ejecutaron dos copias nuevas de la versión final. El orden inicial fue ABBA; las repeticiones finales nuevas se realizaron tras la corrección, conservando los controles anteriores. No es una muestra amplia ni una nueva secuencia ABBA completa.

[Resultados estructurados, fixture, controles, comandos y ejecuciones intermedias](EVALUACION_RESULTADOS.json). Los eventos con razonamientos del modelo permanecen fuera del kit. Faltan casos de funcionalidades, permisos y proyectos grandes antes de generalizar el resultado.

Verificación funcional de la entrega: 62 pruebas correctas con permiso para loopback; sintaxis JavaScript correcta. El helper Python de validación de skills no pudo ejecutarse por falta de PyYAML; se validaron sus metadatos YAML y la política de invocación automática con Ruby/Psych, y se comprobaron las referencias locales modificadas. No se agregó una dependencia al producto.

## Verificación de rutas por perfil — 2026-11-09

Cambio de rutas, incorporado al kit 1.4.0: Laravel conserva `src/`; Go prepara `internal/` y `cmd/`; Flutter prepara `lib/`. Base mantiene `src/` provisional hasta confirmar el stack. Se actualizaron prompt, perfiles, flujo y documentos generados; se conserva el esquema 1 del plan y no se generan aplicaciones. La versión final integra también los cambios remotos de evidencia visual y microinteracciones de 1.3.0.

Antes de integrar los cambios remotos, `python3 -B -m unittest discover -s tests -v` ejecutó 54 pruebas: 51 correctas y tres errores al abrir un puerto de loopback por restricciones del entorno. Las tres se ejecutaron después con permiso para el servidor local mediante `python3 -B -m unittest discover -s tests -v -k HttpTest`: todas correctas. Quedaron comprobadas esas 54 pruebas entre ambas ejecuciones; no se presenta la primera como una suite aprobada.

Tras integrar los cambios remotos de 1.3.0 y resolver los conflictos de documentación y ZIP, se ejecutó la suite completa con permiso para loopback: 61 pruebas correctas en 3.760 segundos informados por unittest, código de salida 0. La comprobación de sintaxis JavaScript también terminó con código 0.

La cobertura incluye rutas predeterminadas y elegidas por el usuario, dry-run sin escrituras, repetición con fecha conservada, colisiones y enlaces simbólicos en las nuevas rutas, conservación de instalaciones Go/Flutter bajo `src/` sin actualización parcial, paquete trasladado y comandos del plan. `node --check skills/manage-project-roadmap/assets/roadmap-tree.js` también terminó con código 0. No se ejecutaron compilaciones de aplicaciones Go/Flutter: esta entrega modifica el kit de preparación, sin código de producto.

## Mediciones disponibles — 2026-11-05

Referencia anterior: `04f621f` (kit 1.1.0); candidato: kit 1.2.0 de esta entrega. Python 3.9.6, mismo intérprete/equipo y plan temporal instalado con la versión anterior: tres tareas iniciales pendientes, INI-002 seleccionada y una dependencia directa. No es una aplicación comercial ni una evaluación de desarrollo con agente.

Se alternaron tres ejecuciones por comando, capturando stdout completo, código de salida y tiempo de pared con perf_counter. Ambos validan todo el plan. Se comprobó que los catorce campos de la tarea seleccionada coinciden y que INI-001 figura como dependencia. El reporte anterior incluye las tres tareas; task entrega una completa y resúmenes de sus prerrequisitos.

| Comando | Bytes de stdout UTF-8 | Tiempos de pared, segundos | Mediana, segundos |
| --- | ---: | --- | ---: |
| Anterior: report --json | 5839 | 0.080902, 0.030886, 0.029643 | 0.030886 |
| Actual: task INI-002 --json | 2596 | 0.031040, 0.031319, 0.029263 | 0.031040 |

La salida específica contiene menos datos ajenos a la tarea; estos tiempos breves no muestran una mejora de latencia. No se midieron tokens, contexto incorporado por un agente, llamadas a sus herramientas ni tiempo total de resolver una tarea. Las seis ejecuciones CLI de esta comprobación no son llamadas medidas de un agente.

Regresión del candidato: `python3 -B -m unittest discover -s tests -v` → 53 pruebas correctas en 3.008 segundos informados por unittest. Incluye consultas, rechazo global, ausencia de escrituras, contenido no confiable, comandos anteriores, instalación, repetición, colisiones, ZIP trasladado y seguridad del visor. `node --check skills/manage-project-roadmap/assets/roadmap-tree.js`, sintaxis Python en memoria y validación oficial de las tres skills/metadatos → correctos. No es una comparación de velocidad de suites con distinta cobertura ni equivale a ejecutar las tres tareas siguientes con un agente.

El intento inicial de usar py_compile no terminó por falta de permiso de escritura en la caché del intérprete. Se sustituyó por compilación en memoria, sin insistir en esa ruta; la suite importó y ejecutó los scripts correctamente. No queda ese intento registrado como una comprobación aprobada.

## Repetir la medición de la CLI

Preparar una copia anterior y otra candidata, registrar sus SHAs y usar el mismo proyecto/plan válido sin modificarlo entre comandos. Este ejemplo solo consulta y falla si un comando devuelve error; imprime los datos medidos completos. Sustituir las cuatro rutas/ID:

```sh
python3 -B - /copia-anterior/kit-inicio-proyecto /copia-actual/kit-inicio-proyecto /ruta/proyecto INI-002 <<'PY'
import json, statistics, subprocess, sys, time
from pathlib import Path
previous, current, project, task_id = sys.argv[1:]
script = 'skills/manage-project-roadmap/scripts/roadmap.py'
commands = {
    'previous_report_json': [sys.executable, '-B', str(Path(previous) / script), 'report', '--json', '--root', project],
    'current_task_json': [sys.executable, '-B', str(Path(current) / script), 'task', task_id, '--json', '--root', project],
}
samples, outputs = {key: [] for key in commands}, {}
for run in range(3):
    order = list(commands) if run % 2 == 0 else list(reversed(commands))
    for name in order:
        started = time.perf_counter()
        result = subprocess.run(commands[name], capture_output=True)
        samples[name].append(time.perf_counter() - started)
        if result.returncode:
            sys.stderr.buffer.write(result.stdout + result.stderr)
            raise SystemExit(result.returncode)
        outputs[name] = result.stdout
before, after = json.loads(outputs['previous_report_json']), json.loads(outputs['current_task_json'])
selected = next(item for item in before['tasks'] if item['id'] == task_id)
assert selected['fields'] == after['task']['fields']
assert selected['dependencies'] == [item['id'] for item in after['dependencies']]
print(json.dumps({name: {'stdout_bytes': len(outputs[name]), 'wall_seconds': samples[name],
                         'median_seconds': statistics.median(samples[name])} for name in commands}, indent=2))
PY
```

Para comparar pruebas, fijar la misma selección existente en ambas versiones, capturar resultado y duración por separado y declarar pruebas nuevas que solo tiene el candidato. No interpretar suites con distinta cobertura como una comparación directa de velocidad.

## Evaluación ampliada con un agente

Elegir tareas reales o fixtures anonimizadas del mismo repositorio, sin desarrollar una aplicación adicional para medir el kit. Preparar antes de los ensayos un commit base, solicitudes, fuentes confirmadas, alcance, criterios y pruebas de aceptación independientes de la solución. No completar incógnitas durante una rama por inferencia.

| Caso | Contrato y aceptación que deben fijarse antes | Estado de la evaluación A/B |
| --- | --- | --- |
| Corrección pequeña | Error reproducible, comportamiento esperado, límites y prueba de regresión del fallo. | Ensayos mínimos Go y Laravel documentados arriba; falta ampliación en proyectos reales. |
| CRUD acotado | Operaciones/campos, invariantes, errores, persistencia y permisos aplicables, con pruebas de recorridos y estados. | No ejecutada. |
| Cambio de permisos | Actores/recursos, matriz esperada, aislamiento y casos permitidos/denegados, con pruebas positivas y negativas. | No ejecutada. |

1. Para cada caso crear dos copias aisladas e idénticas del commit base, fuentes y respuestas. Variar solo el kit/instrucciones de A (04f621f) y B (SHA candidato registrado). Conciliar su instalación sin sobrescribir datos ajenos. Conservar la misma arquitectura, esquema, stack, estado inicial y autorización de la tarea.
2. Usar chats independientes sin historia previa, con el mismo modelo, configuración, herramientas, permisos, recursos y criterios de parada. No pegar al agente el resultado esperado del otro ensayo. Registrar versiones y condiciones, incluidos fallos de servicios externos. Si hay repetición para controlar variabilidad, mantener el mismo protocolo y alternar el orden A/B; no elegir solo el mejor resultado.
3. Ejecutar la misma solicitud de tarea autorizada. Para comprobar reanudación, terminar una sesión en un punto de traspaso previamente definido, conservar su evidencia y empezar una sesión nueva sin transmitir memoria adicional. No interrumpir una escritura ni fabricar un cierre. Registrar por separado preparación, ejecución y reanudación; no cargar a una variante costos iniciales que la otra no tuvo.
4. Conservar tiempos de inicio/fin, registros de herramientas y pruebas, diff final y aceptación independiente. El evaluador debe revisar autorización, arquitectura/DDD, pruebas necesarias, integridad y trazabilidad con los mismos criterios; comparar consumo solo junto con corrección y pendientes. Una variante incompleta no cuenta como ahorro equivalente.
5. Medir tokens solo desde contadores reales proporcionados por el entorno/modelo; si no están disponibles, marcar N/D. Medir contexto incorporado con registros de lecturas/salidas recibidas, declarando si se cuentan bytes/caracteres, repeticiones y límites visibles. No sumar el tamaño del repositorio como si todo se hubiese leído ni confundir stdout con entrada total del modelo.
6. Registrar llamadas a herramientas desde el log real, con política de conteo fija para llamadas compuestas y subcomandos. Tiempo de pruebas: intervalos medidos de procesos o trazas; tiempo total: pared de cada recorrido, incluyendo o separando espera del usuario según una regla idéntica y documentada. Conservar fallos y ampliar el diagnóstico cuando sea necesario.

Una fila por ejecución, guardada en el informe principal del ensayo y enlazada desde su tarea:

| Caso/variante/repetición | SHAs, modelo y condiciones | Total / pruebas (s) | Llamadas y criterio de conteo | Contexto, unidad y registro | Tokens reales / N/D | Criterios cumplidos, pruebas, fallos y límites |
| --- | --- | --- | --- | --- | --- | --- |
| Completar con una ejecución real | Registrar | Medir | Medir | Medir o N/D | Medir o N/D | Revisar el resultado y enlazar evidencia |

Los ensayos de arriba cubren correcciones sintéticas pequeñas en Go y Laravel. Sigue pendiente completar la comparación ampliada de los tres casos de este procedimiento con aceptación, tiempos, llamadas y contadores disponibles. La mejora observada en ese fixture no demuestra ahorro general del agente. No duplicar este informe en fichas, decisiones y tareas: enlazar la evidencia principal con un resumen.


## Verificación de la versión 1.6.0 — 2026-11-11

Se integró la PR #3 conservando la consulta compacta y la política de lectura de 1.5.0. Se corrigió el rechazo de rutas válidas bajo alias del sistema en macOS; los enlaces dentro del plan siguen rechazados. El contexto para Codex respeta las skills necesarias para el cambio y las autorizaciones existentes.

- Python 3.9: `python3 -B -m unittest discover -s tests`, 84 pruebas aprobadas. Incluyen instalación sin sobrescrituras, edición revisada, revisiones desactualizadas, autorizaciones HTTP, alias del sistema y apertura con puerto automático.
- JavaScript: 6 pruebas aprobadas con `node --test tests/roadmap-context.test.js`; sintaxis válida de roadmap-tree.js y roadmap-context.js.
- Inspección visual en un proyecto temporal: selección de tarea, edición, propuesta para Codex, vuelta al formulario conservando el borrador, revisión del diff, autorización, guardado y actualización del árbol. No se envió un prompt a Codex ni se modificó un proyecto real.
- YAML de las tres skills y metadatos validado con Ruby/Psych; el validador Python de skills requiere PyYAML, ausente en este entorno. ZIP reproducible verificado por la suite.

El registro EN_CURSO con responsable e inicio antes de implementar es obligatorio en las instrucciones, incluido el caso de correcciones breves. El parser comprueba el estado actual y sus campos; no observa las escrituras de código ni prueba el orden histórico de las transiciones. Esta verificación no mide tiempos ni tokens del agente para 1.6.0; las mediciones anteriores corresponden a sus versiones y fixtures declarados.
