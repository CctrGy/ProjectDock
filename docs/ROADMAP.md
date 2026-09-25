# Alcance y evolución

## Implementado en 0.1.0

- Catálogo configurable, identidades y detección de varios lenguajes.
- GUI con asistente, recetas, conectores, editor JSON/Lua/scripts y bitácora.
- CLI y menú TUI con el mismo motor.
- Lanzadores Windows con runtime local.
- Perfiles, opciones tipadas y reglas Lua acotadas.
- Conectores por proyecto y prioridad local/global/manual.
- Entornos Python mediante recetas explícitas.
- Grupos, exclusión por receta, timeout, cancelación y registros.
- Integración optativa de PowerShell para cd y run.
- Confianza local invalidada por cambios de configuración.

## Pendiente

- Supervisor persistente, bandeja, inicio con Windows y notificaciones.
- Salud de servicios, reinicio automático y dependencias entre proyectos.
- Exportar/importar plantillas con revisión de datos personales.
- Instalación y actualización verificadas de herramientas con versiones fijadas.
- Detección detallada de distribuciones y versiones.
- Actualización transaccional del runtime y rollback.
- Reasociación asistida de proyectos movidos o desconectados.
- Formularios para todas las opciones; el editor JSON cubre las avanzadas.
- PTY, TUI a pantalla completa y empaquetado Linux/macOS.
- Proveedor concreto de Archify.
- Almacén nativo de secretos; ahora se referencian variables de entorno.

Licencia pendiente. Esta implementación es nueva; no incorpora código de los
ZIP anteriores ni modifica LANCTL.
