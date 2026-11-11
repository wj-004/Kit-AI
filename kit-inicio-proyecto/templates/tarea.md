# Plantilla de tarea

Copiar este bloque en una especificación y completar los campos con información real. Conservar el esquema común de la skill de planificación. Dependencias admite `ninguna` o IDs separados por comas.

```markdown
### [PENDIENTE] AREA-001 — Resultado verificable

- **Capa:** SOLICITADO
- **Fuente:** solicitud o decisión con fecha
- **Contexto propietario:** contexto responsable
- **Dependencias:** ninguna
- **Alcance:** resultado incluido
- **Fuera de alcance:** límites pertinentes
- **Invariantes:** reglas relevantes o explicación de su ausencia en una tarea documental
- **Contratos y archivos previstos:** interfaces, datos, adaptadores o documentación afectados
- **Criterios de aceptación:** resultados observables y comprobaciones necesarias
- **Responsable:** sin asignar
- **Fecha de inicio:** pendiente
- **Última actualización:** AAAA-MM-DD
- **Próximo paso:** primera acción concreta
- **Evidencia actual:** punto de partida observado y límites
```

PROPUESTO no autoriza implementación. Antes de implementar, incluso una corrección breve, guardar la tarea como EN_CURSO con responsable e inicio reales y actualizar la fecha; al retomar, conservar el inicio original. HECHO necesita evidencia y dependencias cerradas. Para EXCLUIDO, registrar la decisión explícita y su ID en Fuente. La tarea es la ubicación principal de estado, responsable, fechas y siguiente paso. En Evidencia actual guardar un resumen y enlaces al informe de resultados y decisiones materiales; no copiar su contenido completo. Evidencia actual puede incluir capturas con `![descripción](capturas/AREA-001-despues.png)`, guardadas dentro de la carpeta del plan.
