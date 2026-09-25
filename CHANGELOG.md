# Historial

## 0.1.1 — 2026-09-25

- Timeout y cancelación activos aunque el programa cierre su salida.
- Control de árboles de procesos y cancelación previa al arranque.
- Validación de configuración, perfiles, conectores y grupos antes de ejecutar.
- Planes y registros ocultan secretos con caracteres especiales y entre bloques.
- Registros limitados por bytes UTF-8; cola de salida y consola acotadas.
- Actualización del lanzador con staging y recuperación ante errores.
- El catálogo reconoce proyectos trasladados; los cambios con override de entorno
  se rechazan explícitamente.
- Corrección del asistente al deshabilitar herramientas y de guardado del editor.
- Setup Windows por usuario, desinstalador, ZIP portable y SHA-256.
- Instalación remota mediante un comando; empaquetado con dependencias fijadas.

## 0.1.0 — 2026-09-25

Primera implementación: catálogo configurable, Core compartido, CLI/TUI/GUI,
recetas, perfiles, conectores, Lua, bitácora y lanzadores Windows con runtime local.
Incluye pruebas, documentación y flujo CI.
