# Historial

## Sin publicar — compatibilidad de lanzadores

- Confirmación add siempre visible en el formulario desplazable de incorporación.
- El botón del Dock permite editar el proyecto seleccionado y abrir uno nuevo.
- La edición conserva la identidad del catálogo y no regenera el lanzador por defecto.
- Entrada gráfica sin terminal visible e icono propio para Windows.

- Consola heredada para TUI y consola externa desde GUI en Windows.
- --debug-terminal conserva argumentos de la aplicación y código de salida.
- Python explícito prevalece; crear un entorno no lo selecciona silenciosamente.
- Recetas LANCTL interactivas, build estricto y build-development separado.
- Instalación opcional del extra dev y exclusión por recursos entre recetas.
- Informe migration-preview sin cambios en el proyecto inspeccionado.
- La autorización incluye cambios en conectores compartidos.
- Verificación del lanzador compilado en consola real y argumentos complejos.

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
