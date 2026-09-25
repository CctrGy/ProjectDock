from __future__ import annotations

import copy
import re
import shutil
import sys
from pathlib import Path

from .connectors import BUILTINS
from .storage import DockError, catalog, new_id, read_json, register, write_json


def detect(root: Path):
    checks = {
        "python": ("pyproject.toml", "requirements.txt", "*.py"),
        "javascript": ("package.json",), "typescript": ("tsconfig.json",),
        "dotnet": ("*.csproj", "*.sln", "*.fsproj"), "rust": ("Cargo.toml",),
        "go": ("go.mod",), "cpp": ("CMakeLists.txt", "Makefile"),
    }
    return [lang for lang, patterns in checks.items() if any(next(root.glob(p), None) for p in patterns)] or ["custom"]


def load(root: Path):
    config = read_json(root / ".project/project.json")
    if not isinstance(config, dict) or config.get("schema") != 1:
        raise DockError("Versión de configuración no compatible")
    for key in ["id", "instance_id", "name", "default_action", "default_profile"]:
        if not isinstance(config.get(key), str):
            raise DockError(f"project.json requiere un campo de texto '{key}'")
    if not isinstance(config.get("languages"), list) or not config["languages"]:
        raise DockError("project.json requiere una lista no vacía de lenguajes")
    if not isinstance(config.get("tools"), dict):
        raise DockError("project.json requiere un objeto tools")
    return config


def recipes(root: Path):
    result = {}
    for path in sorted((root / ".project/recipes").glob("*.json")):
        value = read_json(path)
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
                result[path.stem] = read_json(path)
    return result


def save_recipe(root: Path, name: str, command: list[str], **options):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name) or name in {"dock", "info", "logs", "stop", "plan", "tools", "trust", "update-launcher", "tui"}:
        raise DockError("Nombre de receta inválido o reservado")
    path = root / ".project/recipes" / f"{name}.json"
    if path.exists():
        raise DockError(f"La receta {name} ya existe; edítala en Dock")
    write_json(path, {"name": name, "command": command, "cwd": "{root}", "args": [], "environment": {}, "instance": "block", "timeout": 0, **options})
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
        "logs": {"keep_runs": 100}, "version": "", "launcher_version": "0.1.0"}
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


def generate_launcher(root: Path):
    config = load(root)
    source = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2] / "dist/ProjectDock"
    engine, bootstrap = source / "ProjectDock.exe", source / "Launcher.exe"
    if not engine.exists() or not bootstrap.exists():
        raise DockError("Compila primero con build.ps1 o usa la distribución portable")
    target = root / "run.exe"
    marker = root / ".project/launcher.json"
    if target.exists() and not marker.exists():
        raise DockError("Ya existe run.exe y no pertenece a ProjectDock")
    destination = root / ".project/runtime"
    destination.mkdir(parents=True, exist_ok=True)
    if engine.resolve() == (destination / "ProjectDock.exe").resolve():
        raise DockError("Actualiza el lanzador desde el Dock central")
    shutil.copy2(engine, destination / "ProjectDock.exe")
    shutil.copy2(bootstrap, destination / "Launcher.exe")
    if (source / "_internal").exists():
        shutil.copytree(source / "_internal", destination / "_internal", dirs_exist_ok=True)
    shutil.copy2(bootstrap, target)
    write_json(marker, {"version": "0.1.0", "engine": ".project/runtime/ProjectDock.exe"})
    config["launcher_version"] = "0.1.0"
    write_json(root / ".project/project.json", config)
    return target
