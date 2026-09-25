from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from .engine import grant_trust, lua_worker, plan, public_plan, run, stop
from .project import available_connectors, enable_tool, generate_launcher, initialize, load, recipes, save_recipe
from .storage import DockError, catalog, catalog_path, change_catalog, read_json, resolve_project


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def delegate(root, arguments):
    launcher = root / "run.exe"
    if launcher.is_file() and (root / ".project/launcher.json").is_file():
        return subprocess.call([str(launcher), *arguments], cwd=root)
    return local(root, arguments)


def execution_options(arguments):
    own, extra = (arguments[:arguments.index("--")], arguments[arguments.index("--") + 1:]) if "--" in arguments else (arguments, [])
    parser = argparse.ArgumentParser(prog="run")
    parser.add_argument("action", nargs="?")
    parser.add_argument("--profile")
    parser.add_argument("--replace-args", action="store_true")
    parser.add_argument("--debug-terminal", action="store_true")
    parser.add_argument("--rules", action="store_true")
    parsed = parser.parse_args(own)
    return parsed, extra


def local(root: Path, arguments):
    action = arguments[0] if arguments and not arguments[0].startswith("-") else ""
    if action == "dock":
        from .gui import show
        show(root)
        return 0
    if action == "tui":
        from .tui import show
        return show(root)
    if action == "info":
        print_json({"root": str(root), "project": load(root), "recipes": list(recipes(root))})
        return 0
    if action == "trust":
        grant_trust(root)
        print("Configuración actual autorizada en este equipo.")
        return 0
    if action == "stop":
        stop(root, arguments[1] if len(arguments) > 1 else None)
        return 0
    if action == "logs":
        paths = sorted((root / ".project/logs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if paths:
            print_json(read_json(paths[0]))
            print(paths[0].with_suffix(".log").read_text(encoding="utf-8"))
        else:
            print("Sin registros.")
        return 0
    if action == "tools":
        if len(arguments) > 2 and arguments[1] in {"enable", "disable"}:
            enable_tool(root, arguments[2], arguments[1] == "enable")
        print_json({"configured": load(root)["tools"], "available": available_connectors(root)})
        return 0
    if action == "update-launcher":
        print(generate_launcher(root))
        return 0
    is_plan = action == "plan"
    parsed, extra = execution_options(arguments[1:] if is_plan else arguments)
    if is_plan:
        print_json(public_plan(plan(root, parsed.action, parsed.profile, extra, parsed.replace_args, parsed.rules)))
        return 0
    if parsed.debug_terminal:
        args = [x for x in arguments if x != "--debug-terminal"]
        command = [sys.executable, "--project", str(root), *args] if getattr(sys, "frozen", False) else [sys.executable, "-m", "projectdock", "--project", str(root), *args]
        if os.name != "nt":
            raise DockError("La terminal de depuración separada está disponible en Windows")
        subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return 0
    return run(root, parsed.action, parsed.profile, extra, parsed.replace_args)


def main(argv=None):
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args == ["--lua-worker"]:
            try:
                lua_worker()
                return 0
            except Exception as exc:
                print(f"Regla Lua inválida: {exc}", file=sys.stderr)
                return 1
        if args and args[0] == "--project":
            if len(args) < 2:
                raise DockError("Falta la ruta del proyecto")
            return local(Path(args[1]).resolve(), args[2:])
        if not args or args == ["--gui"]:
            from .gui import show
            show()
            return 0
        if args == ["--version"]:
            print(__version__)
            return 0
        command = args.pop(0)
        if command in {"--help", "-h", "help"}:
            print("""ProjectDock — Dock, Lanzadores, Recetas y Conectores

projectdock                         Abre la GUI
projectdock tui [PROYECTO]           Abre el menú de terminal
projectdock register RUTA [--name N] [--language L] [--python RUTA]
projectdock list                     Catálogo JSON
projectdock catalog [RUTA] [--copy]   Abrir catálogo o copiar el actual
projectdock launcher PROYECTO        Generar/actualizar run.exe
projectdock add-action PROYECTO NOMBRE -- EJECUTABLE ARGUMENTOS
projectdock path PROYECTO            Ruta para integración del shell
projectdock cd PROYECTO              Requiere integration/ProjectDock.ps1
projectdock ACCION PROYECTO [--profile PERFIL] [-- ARGUMENTOS]

Acciones: start, dock, info, plan, trust, tools, logs, stop y recetas propias.
run [RECETA] [--profile PERFIL] [--replace-args] [-- ARGUMENTOS]
run dock | run tui | run plan RECETA | run logs | run stop
run tools enable NOMBRE | run tools disable NOMBRE
--debug-terminal abre una consola separada en Windows.
Git, Lua y otras herramientas solo se ejecutan tras autorizar el proyecto.""")
            return 0
        if command == "list":
            print_json(catalog())
            return 0
        if command == "catalog":
            if args:
                change_catalog(Path(args[0]), "--copy" in args)
            print(catalog_path())
            return 0
        if command == "register":
            parser = argparse.ArgumentParser(prog="projectdock register")
            parser.add_argument("path")
            parser.add_argument("--name")
            parser.add_argument("--language", action="append")
            parser.add_argument("--python")
            parsed = parser.parse_args(args)
            print_json(initialize(Path(parsed.path), parsed.name, parsed.language, parsed.python))
            return 0
        if command == "tui":
            from .tui import show
            return show(resolve_project(args[0]) if args else None)
        if not args:
            raise DockError("Falta el nombre, ID o ruta del proyecto")
        root = resolve_project(args.pop(0))
        if command == "path":
            print(root)
            return 0
        if command == "cd":
            raise DockError("Carga integration/ProjectDock.ps1 para cambiar la terminal actual; 'path' devuelve la ruta.")
        if command == "launcher":
            print(generate_launcher(root))
            return 0
        if command == "add-action":
            if len(args) < 3 or args[1] != "--":
                raise DockError("Uso: add-action PROYECTO NOMBRE -- EJECUTABLE ARGUMENTOS")
            save_recipe(root, args[0], args[2:])
            return 0
        if command == "start":
            return delegate(root, args)
        return delegate(root, [command, *args])
    except (DockError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ProjectDock: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
