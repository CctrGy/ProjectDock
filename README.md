# ProjectDock

**Tus proyectos, sus herramientas y un único punto de arranque.**

Gestor modular con GUI, CLI y menú TUI. Cada proyecto conserva recetas,
perfiles, conectores y reglas en **.project/**; un **run.exe** local permite
ejecutarlo sin recordar comandos largos. El Dock central mantiene el catálogo.

> **0.1.0 · versión inicial experimental para Windows.**
> El motor se prueba también en Linux mediante CI. El empaquetado inicial es Windows.

## Conceptos

| Nombre | Función |
| --- | --- |
| Dock | Aplicación central y catálogo de proyectos. |
| Lanzador | run.exe del proyecto, delegado de su motor local. |
| Receta | Comando, argumentos, entorno y política de ejecución. |
| Perfil | Variantes de argumentos, variables y herramientas. |
| Conector | Integración declarativa de una herramienta. |
| Regla | Código Lua opcional que transforma argumentos. |
| Bitácora | Salida, duración y resultado de las ejecuciones. |

## Incluido

- Asistente para incorporar carpetas y detectar Python, JavaScript/TypeScript,
  .NET, Rust, Go y C/C++ mediante archivos conocidos.
- Editor integrado de configuraciones JSON, scripts vinculados y reglas Lua.
- Perfiles, opciones tipadas, conflictos y paso explícito de argumentos.
- Entornos Python mediante recetas separadas de creación e instalación.
- Conectores por proyecto: Git, ToHub, pytest, Ruff, coverage, npm, .NET,
  Cargo, Go, CMake, Docker, ADR, Gource y GitHub Actions mediante gh.
- Punto de extensión Archify: requiere configurar un proveedor real.
- Grupos secuenciales/paralelos, códigos de salida, timeout y cancelación.
- Autorización local de la configuración, invalidada cuando cambia.
- Catálogo JSON llamado projects.db, con ubicación configurable.
- Lanzadores independientes del Dock central con motor en .project/runtime.

El runtime incluye las dependencias de **ProjectDock**. Python, Git, Node y
compiladores del proyecto siguen siendo externos salvo configuración local.
No instala herramientas automáticamente. Copiar un entorno virtual Python
no garantiza que funcione en otro equipo.

## Inicio desde código

Requiere Python 3.10+ y Tkinter, incluido habitualmente en Python para Windows.

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\projectdock.exe
~~~

Sin argumentos abre la GUI. **Incorporar proyecto** permite ajustar nombre,
lenguajes, Python, argumentos y conectores. Generar run.exe requiere compilar.

## Compilar y usar la distribución portable

~~~powershell
.\build.ps1
.\dist\ProjectDock\ProjectDock.exe
~~~

El script prepara un entorno, ejecuta las pruebas y construye:

~~~text
dist/ProjectDock/
├── ProjectDock.exe
├── Launcher.exe
└── _internal/
~~~

Conserva toda la carpeta. Puedes copiarla o instalarla por usuario con
install.ps1, sin privilegios de administrador.

## CLI

El comando projectdock debe estar en PATH o debe usarse su ruta completa.

~~~powershell
projectdock register C:\Proyectos\MiApp --name MiApp --language python
projectdock launcher MiApp
projectdock info MiApp
projectdock plan MiApp start
projectdock trust MiApp
projectdock start MiApp
projectdock dock MiApp
projectdock tui MiApp
~~~

Revisa las recetas antes de autorizar. Registrar no ejecuta código del proyecto.

Dentro del proyecto:

~~~powershell
.\run.exe
.\run.exe dock
.\run.exe test
.\run.exe --profile demo -- --port 8080
.\run.exe logs
.\run.exe stop
~~~

En CMD se puede escribir run. Para usar run y projectdock cd desde PowerShell:

~~~powershell
$env:PROJECTDOCK_EXE = 'C:\ruta\ProjectDock\ProjectDock.exe'
. 'C:\ruta\ProjectDock\integration\ProjectDock.ps1'
projectdock cd MiApp
run
run dock
~~~

No se modifica tu perfil de PowerShell automáticamente.

## Estructura local

~~~text
MiApp/
├── run.exe
├── .project/
│   ├── project.json
│   ├── launcher.json
│   ├── recipes/
│   ├── profiles/
│   ├── connectors/
│   ├── rules/
│   ├── scripts/
│   ├── runtime/
│   ├── state/
│   └── logs/
└── ...código existente...
~~~

Para excluir el gestor, añade al .gitignore del proyecto:

~~~gitignore
/.project/
/run.exe
~~~

ProjectDock no modifica ese archivo automáticamente.

## Catálogo

Se guarda en la carpeta Documentos real del usuario bajo ProjectDock/projects.db.
La ruta elegida y las autorizaciones viven en LOCALAPPDATA/ProjectDock.
Desde la GUI puedes cambiar el catálogo o usar:

~~~powershell
projectdock catalog D:\MisProyectos\projects.db --copy
~~~

--copy copia el catálogo y selecciona el nuevo, conservando el original.
Sin --copy abre el existente o crea uno vacío. No mueve los proyectos.
PROJECTDOCK_HOME y PROJECTDOCK_CATALOG permiten aislar datos y catálogo.

## Documentación

- [Configuración, recetas, conectores y Lua](docs/CONFIGURATION.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Alcance y evolución](docs/ROADMAP.md)
- [Contribución y pruebas](CONTRIBUTING.md)
- [Seguridad](SECURITY.md)
- [Cambios](CHANGELOG.md)

## Licencia

Pendiente de elección por el propietario. No se presupone una licencia de
código abierto por publicar el repositorio.
