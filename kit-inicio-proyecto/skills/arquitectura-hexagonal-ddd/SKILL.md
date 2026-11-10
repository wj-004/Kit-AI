---
name: arquitectura-hexagonal-ddd
description: Definir o cambiar fronteras entre contextos, contratos y reglas de dominio con arquitectura hexagonal y DDD. Aplicar a decisiones de arquitectura y modelado nuevo; una corrección que conserva el contrato usa la arquitectura existente.
---

# Arquitectura hexagonal y DDD

Domain protege las invariantes; Application coordina casos de uso mediante contratos del núcleo. Las dependencias apuntan al núcleo, sin imports de frameworks, ORM ni adaptadores. UI traduce entrada/salida; la composición conecta implementaciones. Los contextos se comunican por contratos publicados.

Conservar las rutas y decisiones registradas. Para cambios de frontera o contrato, consultar la sección afectada de arquitectura y registrar la decisión material. Para nuevo modelado o adaptación del stack, consultar [diseño y modelado](references/diseno-y-modelado.md) y solo el perfil necesario. Justificar entidades, valores y agregados por identidad, invariantes y consistencia; comprobar su comportamiento.

El pedido define el alcance. Una tarea ya consultada aporta requisitos y autorización: abrir referencias técnicas si falta un dato que cambie la decisión. Tras armar el plan, releer fuentes o requerimientos originales solo por pedido expreso del usuario; si el plan no alcanza, consultar la duda. La implementación corriente se guía por AGENTS.md; no requiere activar planificación ni leer el flujo completo.
