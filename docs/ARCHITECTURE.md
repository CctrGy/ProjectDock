# Arquitectura

~~~text
ProjectDock.exe (Dock)
  ├── projects.db → nombre / ruta / identidad
  └── run.exe (Lanzador)
        └── .project/runtime/ProjectDock.exe --project RUTA
              ├── CLI
              ├── TUI
              └── GUI
                    └── Core compartido
                          ├── storage: catálogo y escritura atómica
                          ├── project: detección y configuración
                          ├── connectors: herramientas declarativas
                          └── engine: planes, procesos y bitácora
~~~

Las interfaces no construyen comandos por su cuenta. El Dock delega en el
lanzador si existe; antes de generarlo usa directamente el mismo Core.
run.exe solo localiza el motor y delega. El proyecto conserva autoridad sobre
sus recetas: el catálogo no duplica esa configuración.

La detección no ejecuta código. Las autorizaciones son locales. Lua transforma
argumentos mediante un proceso acotado. Las escrituras JSON son atómicas y
catálogo, autorizaciones y reserva de acciones usan bloqueos del sistema.

El gestor portable requiere _internal y el lanzador .project/runtime.
No necesitan Python externo para ejecutar ProjectDock; las herramientas
de los proyectos tienen sus propios requisitos. portability es descriptivo,
no una certificación automática.

id identifica el proyecto; instance_id la copia de trabajo. La ruta lo
localiza y el nombre es un alias. Nombres ambiguos requieren ruta o ID.
Un remoto Git no es identidad única porque varios clones pueden compartirlo.

El formato actual es schema 1. Versiones desconocidas se rechazan.
Las migraciones futuras deben preservar scripts y recetas personales.
La actualización del runtime se hace desde el Dock central; nunca se
reemplaza un run.exe desconocido.
