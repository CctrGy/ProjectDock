# Contribuir

1. Crea una rama desde main.
2. Prepara un entorno Python 3.10+ e instala el proyecto editable.
3. Añade pruebas para los comportamientos que cambien.
4. Ejecuta python -m pytest -q.
5. Para empaquetado Windows, ejecuta build.ps1 y verifica los ejecutables.

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e . pytest
.\.venv\Scripts\python.exe -m pytest -q
~~~

Usa proyectos temporales y catálogos aislados. No subas datos personales,
entornos, ejecutables, registros, credenciales o projects.db.
No reemplaces scripts del usuario. Las integraciones declaran lenguajes,
ejecutable y recetas. Cambios incompatibles requieren una versión de schema.

## Distribución Windows

Ejecuta build.ps1 -Release para usar un entorno aislado con dependencias fijadas.
Después ejecuta scripts/package-release.ps1 (requiere Inno Setup 6) y
scripts/test-installer.ps1 -Installer RUTA-AL-SETUP en un equipo sin una
instalación de ProjectDock registrada. El test instala, reinstala y desinstala
en una carpeta propia, comprobando PATH y conservación de datos.

El workflow Publish Windows release admite un tag ya existente, ejecuta la
matriz de pruebas y publica un borrador solo después de verificar los artefactos.
No reemplaza archivos de una release ya publicada.
