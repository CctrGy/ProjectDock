"""Informe de migración sin ejecutar código ni escribir en el proyecto."""
import hashlib
from pathlib import Path

from .project import detect
from .storage import DockError


def preview(root):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise DockError("Selecciona una carpeta existente")
    wrappers = []
    for filename in ["run.cmd", "run.bat", "run.ps1", "run.exe"]:
        path = root / filename
        if path.is_file():
            wrappers.append({"file": filename, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "decision": "conservar hasta validar equivalencia de argumentos y terminal"})
    ignore = root / ".gitignore"
    lines = ignore.read_text(encoding="utf-8-sig").splitlines() if ignore.exists() else []
    return {
        "root": str(root), "read_only": True, "languages": detect(root),
        "configured": (root / ".project/project.json").is_file(),
        "wrappers": wrappers,
        "gitignore_suggested": [x for x in ["/.project/", "/run.exe"] if x not in lines],
        "gitignore_note": "Sugerencias literales; no evalúan patrones Git, negaciones ni exclusiones globales.",
        "checks": [
            "run.exe tiene precedencia sobre run.cmd en CMD; en PowerShell usar .\\run.exe.",
            "Comparar run.cmd ARGUMENTOS con run.exe -- ARGUMENTOS, incluidos espacios, comillas y Unicode.",
            "Comprobar CLI, TUI, Ctrl+C, redimensionado y códigos de salida en datos temporales.",
            "Seleccionar python explícitamente; crear .project/python no cambia el intérprete.",
            "Instalar el extra dev solo si el proyecto lo declara.",
            "La receta build conserva los controles del script; build-development permite -AllowDirty.",
            "Conservar scripts especializados de build, instaladores y pruebas.",
            "Los ejecutables distribuidos del proyecto deben funcionar sin ProjectDock.",
            "Actualizar el lanzador no migra ni sobrescribe recetas existentes.",
        ],
    }
