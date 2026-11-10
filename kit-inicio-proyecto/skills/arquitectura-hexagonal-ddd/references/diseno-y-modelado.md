# Diseño y modelado hexagonal con DDD

Consultar al definir o cambiar contextos, contratos, invariantes o modelos. Para una corrección que conserva el contrato actual, usar su especificación y el código afectado.

Una vez armado el plan, usar sus requisitos y criterios. Las fuentes originales se releen solo por pedido expreso del usuario; una duda del plan se consulta, sin reiniciar el relevamiento.

Elegir solo el perfil confirmado cuando se necesite adaptar paquetes, imports o composición: [Laravel](laravel.md), [Go](go.md), [Flutter](flutter.md). No relevar otra vez el stack ya registrado.

## Preparar la arquitectura

- Adaptar la organización al stack confirmado: Laravel en `src/<Contexto>/{Domain,Application,Infrastructure,UI}`; servicios Go en `internal/<contexto>/{domain,application,adapters}`, con arranque en `cmd/<aplicacion>`; Flutter en `lib/contexts/<contexto>/{domain,application,infrastructure,presentation}`, con composición en `lib/app/`. El perfil base conserva `src/` provisional hasta confirmar el stack; no convierte esa ruta en obligación para otros lenguajes. Registrar la raíz efectiva en `.agents/project.json`, ficha y arquitectura, y las rutas por componente cuando se combinen stacks. Una elección distinta del perfil necesita solicitud y fecha en decisiones. Conservar rutas heredadas pendientes de conciliación sin atribuirles una autorización ni mover código por instalar el kit.
- Partir de actores, lenguaje, procesos, invariantes y propiedad de datos. Derivar contextos de esas reglas; no crearlos por cada pantalla ni suponer microservicios.
- Organizar por contexto y, dentro, Domain, Application, Infrastructure y UI/Presentation. La dirección de dependencias apunta al núcleo; la composición conecta adaptadores con puertos.
- Domain contiene entidades, agregados, value objects, invariantes, servicios y eventos sin imports de frameworks, ORM, HTTP o SDKs. Application coordina casos de uso y depende de contratos del núcleo, nunca de Infrastructure/UI ni de servicios globales del framework. En Flutter, separar carpetas dentro de un paquete no aísla sus dependencias de pubspec: comprobar imports y extraer un núcleo Dart cuando se necesite aislamiento del manifiesto. Crear paquetes por fronteras justificadas, sin imponer uno por cada capa.
- Ubicar los puertos donde el núcleo los necesita: repositorios y capacidades del dominio en Domain; reloj, transacciones, identidad, comunicación u otras necesidades de orquestación en Application cuando esa sea su responsabilidad. No forzar interfaces ajenas al problema ni permitir que un adaptador defina la política.
- UI valida formato y traduce entrada/salida. Las escrituras y decisiones de negocio pasan por Application; los modelos ORM y componentes de pantalla no las implementan. Las consultas usan contratos de lectura cuando corresponda, sin esconder reglas en closures de UI.
- Los contextos se comunican con contratos publicados, no mediante tablas, modelos, casos de uso internos o implementaciones de otro contexto. La orquestación usa esos contratos y adaptadores explícitos. SharedKernel se limita a conceptos realmente compartidos con propietario y semántica común.
- Precisar límites transaccionales y concurrentes desde las invariantes. No considerar atómica una llamada externa junto a una transacción local. Elegir idempotencia, outbox, reintentos o compensación según el recorrido; no imponer CQRS, event sourcing o un bus por defecto.

Registrar cambios materiales en decisiones según el flujo y su plantilla; una modificación rutinaria no requiere una nueva decisión. Mantener incógnitas pendientes, conservar fuentes y autorizaciones; los ejemplos de otro proyecto no son requisitos.

## Modelado de Domain

Exigir los elementos que correspondan al modelo de negocio:

- **Entidad:** cuando el concepto conserva identidad y tiene ciclo de vida o comportamiento. Su estado cambia mediante operaciones que protegen invariantes, no por escrituras arbitrarias de la UI/ORM.
- **Value object:** cuando representa un concepto definido por su valor, igualdad y restricciones propias. Encapsular validación semántica y conservar inmutabilidad; no sustituirlo por un string/DTO si eso dispersa invariantes.
- **Agregado y raíz:** cuando hay un límite de consistencia que debe proteger invariantes al modificar entidades/valores. Precisar su frontera y punto de entrada; no agrupar todos los modelos ni crear contenedores sin una razón de negocio.
- **Servicios/eventos de dominio:** para políticas que no pertenecen naturalmente a una entidad/valor y hechos del negocio necesarios para sus recorridos, respectivamente. No generar uno por cada operación CRUD por rutina.

No exigir todas las categorías en cada contexto ni crear clases vacías para cumplir carpetas. Tampoco omitir entidades, valores o agregados necesarios para reducir tokens: documentar qué concepto/invariante justificó su elección y probar su comportamiento. Los DTOs de transporte no sustituyen el modelo; las reglas no se trasladan a Eloquent, controladores, componentes o adaptadores.

## Aplicar a trabajo autorizado

Si existe una tarea, usar su contexto ya consultado; abrir un prerrequisito solo si su contrato o evidencia condiciona el cambio y el resumen no alcanza. Preparar las rutas del perfil con `.gitkeep` no autoriza frameworks, contextos ficticios ni funcionalidades.

Modelar invariantes en el dominio; comprobar permisos e identidad/tenant en límites y casos de uso con contratos confiables. Tratar errores externos mediante contratos de error del núcleo; el adaptador los traduce. Registrar datos necesarios sin secretos ni cuerpos completos con información personal. La UI ofrece errores comprensibles y conserva los detalles técnicos en la observabilidad apropiada.

Aplicar la estrategia de pruebas del flujo a las invariantes, casos de uso, contratos y adaptadores afectados. Un chequeo de imports es estructural; no demuestra aislamiento, reglas correctas ni una integración operativa.

En un repositorio existente, contrastar su estructura con el perfil y las decisiones vigentes; identificar diferencias concretas y proponer cortes de refactorización con alcance. Conservar la raíz registrada, incluidas instalaciones antiguas de Go/Flutter bajo src; no convertir su presencia en una elección expresa ni trasladar código sin un pedido que lo cubra. No atribuir pureza de dominio a una estructura de carpetas: revisar imports, herencia, tipos y dependencias de Domain/Application, y adaptar autoload/composición a las rutas acordadas.
