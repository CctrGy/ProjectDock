# Seguridad

Registrar un proyecto no ejecuta su código. La ejecución requiere autorización
local vinculada a la ruta y a la configuración. Tras autorizar, los comandos
tienen los permisos del usuario: no se ejecutan en una sandbox.

La huella cubre recetas, perfiles, reglas, conectores, scripts de .project y
project.json; no pretende aprobar cada cambio del código fuente externo.
Lua usa otro proceso con memoria, tiempo y bibliotecas limitados.

No guardes secretos literales. La ocultación de valores referenciados en logs
no protege sus transformaciones ni archivos escritos por herramientas externas.
No publiques credenciales ni datos privados en incidencias.
Para problemas sensibles, usa avisos privados de seguridad si están habilitados
en GitHub. No hay telemetría ni actualizaciones automáticas.
