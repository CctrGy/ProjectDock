from __future__ import annotations

import copy
import re
import shutil
import sys
import os
import tempfile
import hashlib
from pathlib import Path

from .connectors import BUILTINS
from .storage import DockError, catalog, new_id, read_json, register, write_json
from . import __version__, validation


def detect(root: Path):
    checks = {
        "python": ("pyproject.toml", "requirements.txt", "*.py"),
        "javascript": ("package.json",), "typescript": ("tsconfig.json",),
        "dotnet": ("*.csproj", "*.sln", "*.fsproj"), "rust": ("Cargo.toml",),
        "go": ("go.mod",), "cpp": ("CMakeLists.txt", "Makefile"),
    }
    return [lang for lang, patterns in checks.items() if any(next(root.glob(p), None) for p in patterns)] or ["custom"]


def load(root: Path):
    return validation.project(read_json(root / ".project/project.json"))


def recipes(root: Path):
    result = {}
    for path in sorted((root / ".project/recipes").glob("*.json")):
        value = validation.recipe(read_json(path), path.stem)
        name = value.get("name", path.stem)
        if name in result:
            raise DockError(f"Receta duplicada: {name}")
        result[name] = value
    return result


def available_connectors(root: Path):
    result = copy.deepcopy(BUILTINS)
    from .storage import settings_path
    for directory in [settings_path().parent / "connectors", root / ".project/connectors"]:
        if directory.is_dir():
            for path in directory.glob("*.json"):
                result[path.stem] = validation.connector(read_json(path))
    return result


def save_recipe(root: Path, name: str, command: list[str], **options):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name) or name in validation.RESERVED:
        raise DockError("Nombre de receta inválido o reservado")
    path = root / ".project/recipes" / f"{name}.json"
    if path.exists():
        raise DockError(f"La receta {name} ya existe; edítala en Dock")
    value = {"name": name, "command": command, "cwd": "{root}", "args": [], "environment": {}, "instance": "block", "timeout": 0, **options}
    validation.recipe(value)
    write_json(path, value)
    if name == "start":
        config = load(root)
        if not config.get("default_action"):
            config["default_action"] = "start"
            write_json(root / ".project/project.json", config)


def enable_tool(root: Path, name: str, enabled=True):
    config = load(root)
    connector = available_connectors(root).get(name)
    if not connector:
        raise DockError(f"Conector desconocido: {name}")
    if "*" not in connector["languages"] and not set(config["languages"]).intersection(connector["languages"]):
        raise DockError(f"{name} no es compatible con este proyecto")
    config.setdefault("tools", {}).setdefault(name, {"executable": connector["executable"], "priority": "local-first"})["enabled"] = enabled
    write_json(root / ".project/project.json", config)
    if enabled:
        for recipe, command in connector.get("recipes", {}).items():
            if recipe not in recipes(root):
                save_recipe(root, recipe, command, tool=name)


def initialize(root: Path, name=None, languages=None, python=None):
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise DockError("Selecciona una carpeta existente")
    path = root / ".project/project.json"
    if path.exists():
        config = load(root)
        duplicates = [r for r in catalog()["projects"] if r["instance_id"] == config["instance_id"] and Path(r["path"]).resolve() != root and Path(r["path"]).exists()]
        if duplicates:
            config["instance_id"] = new_id()
            write_json(path, config)
        register(root, config)
        return config
    config = {"schema": 1, "id": new_id(), "instance_id": new_id(), "name": name or root.name,
        "languages": languages or detect(root), "default_action": "start", "default_profile": "development",
        "python": python or "python", "trusted": False, "portability": "system-dependent", "tools": {},
        "logs": {"keep_runs": 100}, "version": "", "launcher_version": __version__}
    validation.project(config)
    write_json(path, config)
    write_json(root / ".project/profiles/development.json", {"environment": {}, "args": {}, "tools": {}})
    for directory in ["recipes", "scripts", "rules", "connectors", "logs", "runtime", "state"]:
        (root / ".project" / directory).mkdir(parents=True, exist_ok=True)
    if (root / "lanctl.py").exists():
        for app in ["lanctl", "lanip", "lanwire", "lanrack", "lanaccess", "lanmon"]:
            if (root / f"{app}.py").exists():
                save_recipe(root, "start" if app == "lanctl" else app, ["{python}", f"{{root}}/{app}.py"])
        if (root / "scripts/build-windows.ps1").exists():
            save_recipe(root, "build", ["powershell.exe", "-NoProfile", "-File", "{root}/scripts/build-windows.ps1", "-AllowDirty"])
    elif (root / "main.py").exists():
        save_recipe(root, "start", ["{python}", "{root}/main.py"])
    elif (root / "package.json").exists():
        config["tools"]["npm"] = {"enabled": True, "executable": "npm", "priority": "local-first"}
        save_recipe(root, "start", ["{tool:npm}", "start"], tool="npm")
    elif "rust" in config["languages"]:
        save_recipe(root, "start", ["cargo", "run"])
    elif "dotnet" in config["languages"]:
        save_recipe(root, "start", ["dotnet", "run"])
    elif "go" in config["languages"]:
        save_recipe(root, "start", ["go", "run", "."])
    else:
        config["default_action"] = ""
    write_json(path, config)
    if "python" in config["languages"]:
        save_recipe(root, "environment-create", [config["python"], "-m", "venv", "{root}/.project/python"])
        install = ["{python}", "-m", "pip", "install"]
        if (root / "pyproject.toml").exists():
            install += ["-e", "{root}"]
        elif (root / "requirements.txt").exists():
            install += ["-r", "{root}/requirements.txt"]
        else:
            install = []
        if install:
            save_recipe(root, "environment-install", install)
    register(root, config)
    return config


def generate_launcher(root: Path, source: Path | None = None):
    from .storage import lock
    from .engine import process_alive
    root = root.resolve()
    config = load(root)
    source = source or (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2] / "dist/ProjectDock")
    engine, bootstrap = source / "ProjectDock.exe", source / "Launcher.exe"
    if not engine.exists() or not bootstrap.exists():
        raise DockError("Compila primero con build.ps1 o usa la distribución portable")
    target = root / "run.exe"
    marker = root / ".project/launcher.json"
    if target.exists() and not marker.exists():
        raise DockError("Ya existe run.exe y no pertenece a ProjectDock")
    destination = root / ".project/runtime"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if engine.resolve() == (destination / "ProjectDock.exe").resolve():
        raise DockError("Actualiza el lanzador desde el Dock central")
    with lock(root / ".project/launcher.lock"):
        for path in (root / ".project/state").glob("*.json"):
            state = read_json(path)
            if state.get("status") in {"STARTING", "RUNNING"} and process_alive(state["pid"], state["created"]):
                raise DockError("Detén las ejecuciones del proyecto antes de actualizar su lanzador")
        if target.exists():
            previous_hash = read_json(marker).get("sha256")
            old_bootstrap = destination / "Launcher.exe"
            if previous_hash is None and old_bootstrap.exists():
                previous_hash = hashlib.sha256(old_bootstrap.read_bytes()).hexdigest()
            if previous_hash != hashlib.sha256(target.read_bytes()).hexdigest():
                raise DockError("run.exe ha cambiado fuera de ProjectDock; no se reemplazará")
        staging = Path(tempfile.mkdtemp(prefix=".launcher-", dir=root / ".project"))
        backup = staging / "previous-runtime"
        new_runtime = staging / "runtime"
        old_config = copy.deepcopy(config)
        old_marker = read_json(marker) if marker.exists() else None
        swapped = False
        committed = False
        try:
            new_runtime.mkdir()
            shutil.copy2(engine, new_runtime / "ProjectDock.exe")
            shutil.copy2(bootstrap, new_runtime / "Launcher.exe")
            if (source / "_internal").exists():
                shutil.copytree(source / "_internal", new_runtime / "_internal")
            new_run = staging / "run.exe"
            shutil.copy2(bootstrap, new_run)
            if target.exists():
                shutil.copy2(target, staging / "previous-run.exe")
            if destination.exists():
                destination.rename(backup)
            try:
                new_runtime.rename(destination)
            except OSError:
                if backup.exists():
                    backup.rename(destination)
                raise
            swapped = True
            os.replace(new_run, target)
            config["launcher_version"] = __version__
            write_json(root / ".project/project.json", config)
            write_json(marker, {"version": __version__, "engine": ".project/runtime/ProjectDock.exe",
                                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
            committed = True
        except Exception:
            if swapped:
                # Solo revierte directorios creados por esta operación.
                destination.rename(staging / "failed-runtime")
                if backup.exists():
                    backup.rename(destination)
                old_run = staging / "previous-run.exe"
                if old_run.exists():
                    os.replace(old_run, target)
                else:
                    target.unlink(missing_ok=True)
                write_json(root / ".project/project.json", old_config)
                if old_marker is None:
                    marker.unlink(missing_ok=True)
                else:
                    write_json(marker, old_marker)
            raise
        finally:
            # Una copia anterior no restaurada se conserva para recuperación manual.
            if not backup.exists() or committed:
                if staging.resolve().is_relative_to((root / ".project").resolve()):
                    shutil.rmtree(staging)
    return target
