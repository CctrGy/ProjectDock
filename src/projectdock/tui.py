from pathlib import Path

from .engine import grant_trust, run
from .project import load, recipes
from .storage import DockError, catalog


def show(root=None):
    while True:
        if root is None:
            projects = catalog()["projects"]
            print("\n╔═ PROJECTDOCK · Proyectos ═════════════════╗")
            for index, project in enumerate(projects, 1):
                print(f" {index}. {project['name']}  ·  {project['path']}")
            answer = input(" Proyecto / q salir > ").strip()
            if answer.lower() == "q":
                return 0
            try:
                root = Path(projects[int(answer) - 1]["path"])
            except (ValueError, IndexError):
                continue
        try:
            actions = list(recipes(root))
            print(f"\n╔═ {load(root)['name']} · Recetas ═════════════════╗")
            for index, name in enumerate(actions, 1):
                print(f" {index}. {name}")
            print(" c configurar · a autorizar · p proyectos · q salir")
            answer = input(" > ").strip()
            if answer == "q":
                return 0
            if answer == "p":
                root = None
            elif answer == "c":
                from .gui import show as gui
                gui(root)
            elif answer == "a":
                if input("¿Autorizar la configuración actual? [sí/no] ").lower() in {"sí", "si"}:
                    grant_trust(root)
            else:
                print("Código de salida:", run(root, actions[int(answer) - 1]))
        except (DockError, OSError, ValueError, IndexError) as exc:
            print("Aviso:", exc)
