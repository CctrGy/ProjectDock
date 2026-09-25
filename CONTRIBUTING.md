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
