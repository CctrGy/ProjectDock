# Configuración modular

Edita los archivos desde **Configuración y código** o cualquier editor.
Los JSON usan UTF-8. Cambiar recetas no requiere recompilar el lanzador.

## Proyecto

project.json define schema, id, instance_id, name, languages, default_action,
default_profile, python, tools, environment y logs. El ID identifica el origen
del proyecto; instance_id distingue copias locales. Al registrar una copia
cuyo original todavía existe se genera otro instance_id.

La versión del código, la del lanzador y schema son datos separados.
El campo trusted no concede autorización: la confianza se guarda en este
equipo, fuera del proyecto, ligada a la ruta y a la configuración.

## Recetas

.project/recipes/start.json:

~~~json
{
  "name": "start",
  "command": ["{python}", "{root}/main.py"],
  "cwd": "{root}",
  "args": ["--verbose"],
  "environment": {"APP_MODE": "development"},
  "instance": "block",
  "timeout": 0
}
~~~

command es una lista, no una línea de shell. Cada argumento conserva sus
espacios. Para scripts especifica su intérprete: Python, bash, powershell.exe
-NoProfile -File, etc. Para CMD/BAT se rechazan argumentos con metacaracteres.

| Macro | Resolución |
| --- | --- |
| {root} | Directorio del proyecto. |
| {python} | .project/python, después .venv y finalmente el Python configurado. |
| {tool:nombre} | Herramienta habilitada según prioridad local/global/manual. |
| {env:NOMBRE} | Variable de entorno disponible. |
| {secret:NOMBRE} | Variable externa PROJECTDOCK_SECRET_NOMBRE. |

No guardes secretos literales. Los valores referenciados se ocultan en el
plan y los registros; no se pueden ocultar automáticamente sus transformaciones.

instance admite block y allow. timeout son segundos; 0 significa sin límite.
interactive hereda entrada en CLI; la GUI no emula una terminal PTY.

## Perfiles y argumentos

.project/profiles/demo.json:

~~~json
{
  "environment": {"APP_MODE": "demo"},
  "args": {"start": ["--demo"]},
  "tools": {"git": {"enabled": false}},
  "options": {"serve": {"port": 8080}}
}
~~~

Variables: sistema → proyecto → receta → perfil.
La lista del perfil sustituye a la lista de argumentos de la receta.
Los argumentos después de -- se añaden. --replace-args sustituye los argumentos
libres; las opciones tipadas siguen sus reglas. No se adivina la semántica de
argumentos desconocidos.

~~~powershell
run --profile demo -- --verbose
run --replace-args -- --version
run plan start --profile demo
~~~

## Opciones tipadas

Una receta admite options:

~~~json
{
  "port": {"type": "integer", "default": 8000, "flag": "--port"},
  "format": {"type": "string", "default": "json", "choices": ["json", "text"]},
  "fast": {"type": "boolean", "default": false, "conflicts": ["safe"]},
  "safe": {"type": "boolean", "default": true}
}
~~~

Los perfiles sobreescriben valores predeterminados. Se validan tipos,
elecciones, opciones requeridas y conflictos.
Las opciones conocidas que lleguen tras -- prevalecen sobre el perfil y se
emiten una sola vez. Se admiten --port 8080 y --port=8080; las booleanas también
admiten --fast=false. No dupliques estas opciones en args: el plan lo rechaza.

## Lua

Añade "lua": "rules/build.lua" a una receta. Recibe context.system,
context.profile, context.options y context.args y devuelve una lista de textos.

~~~lua
local args = context.args
if context.system == "win32" then
    table.insert(args, "--platform")
    table.insert(args, "windows")
end
return args
~~~

Solo se evalúa con autorización local. Usa otro proceso, límite de 3 segundos
y 8 MiB de memoria Lua. No expone os, io, package, require, debug, load ni
el puente a Python. Esto no convierte las recetas en una sandbox.
Distribuciones y versiones deben declararse en perfiles o adaptadores.

~~~powershell
run plan build --rules
~~~

## Conectores

Compartidos: PROJECTDOCK_HOME/connectors, por defecto
LOCALAPPDATA/ProjectDock/connectors. Locales: .project/connectors.
Los locales prevalecen sobre compartidos e incorporados.

.project/connectors/mi-herramienta.json:

~~~json
{
  "executable": "mi-herramienta.exe",
  "languages": ["python", "javascript"],
  "recipes": {"analizar": ["{tool:mi-herramienta}", "check", "{root}"]}
}
~~~

Habilitar crea las recetas que no existan; no reemplaza las editadas.
languages ["*"] admite cualquier proyecto.
En project.json, tools contiene:

~~~json
{
  "mi-herramienta": {
    "enabled": true,
    "executable": "mi-herramienta.exe",
    "priority": "local-first"
  }
}
~~~

local-first busca .project/tools/NOMBRE/EJECUTABLE y después PATH.
global-first invierte el orden. manual exige una ruta existente; usa {root}.
Un perfil puede ajustar estos campos. Archify requiere un proveedor configurado.
GitHub Actions utiliza gh y su autenticación existente.

## Grupos

~~~json
{"name": "check", "steps": ["lint", "test"], "mode": "sequence"}
~~~

sequence se detiene en el primer error. parallel ejecuta hasta 16 pasos a la vez
y solicita cancelar el grupo al detectar un fallo. Se rechazan ciclos.
Todavía no hay condiciones de disponibilidad HTTP/TCP entre servicios.

## Bitácora

.project/logs guarda resultado JSON y salida por ejecución. .project/state
permite detener acciones entre interfaces. Se conservan 100 ejecuciones y
10 MiB de texto por ejecución por defecto; logs.keep_runs y
logs.max_bytes_per_run permiten configurarlo.
STARTING/RUNNING indican ejecución, no salud funcional.
La GUI detiene sus acciones al cerrarse. La CLI espera y devuelve su código.
--debug-terminal abre otra consola Windows. El supervisor permanente está pendiente.
