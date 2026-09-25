"""Prueba el Dock compilado y su lanzador sin depender del paquete instalado."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from projectdock import __version__


def main():
    engine = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="projectdock-portable-") as directory:
        base = Path(directory)
        root = base / "project with spaces"
        root.mkdir()
        environment = dict(os.environ, PROJECTDOCK_HOME=str(base / "settings"), PROJECTDOCK_CATALOG=str(base / "projects.db"))
        environment.pop("PYTHONPATH", None)
        def call(executable, *args, code=0):
            result = subprocess.run([str(executable), *args], cwd=base, env=environment, text=True, encoding="utf-8", capture_output=True, timeout=40)
            assert result.returncode == code, (args, result.stdout, result.stderr)
            return result.stdout
        assert call(engine, "--version").strip() == __version__
        call(engine, "register", str(root), "--name", "Portable")
        # El programa de prueba es otro ejecutable empaquetado, no Python externo.
        call(engine, "add-action", "Portable", "start", "--", str(engine), "--version")
        call(engine, "launcher", "Portable")
        launcher = root / "run.exe"
        call(engine, "trust", "Portable")
        assert call(launcher).strip() == __version__
        assert call(engine, "start", "Portable").strip() == __version__
        # Lua debe funcionar también dentro del runtime copiado.
        rule = root / ".project/rules/test.lua"
        rule.write_text('return {"--version"}', encoding="utf-8")
        recipe = root / ".project/recipes/start.json"
        value = json.loads(recipe.read_text())
        value["command"] = [str(engine)]
        value["lua"] = "rules/test.lua"
        recipe.write_text(json.dumps(value), encoding="utf-8")
        call(engine, "trust", "Portable")
        assert call(launcher).strip() == __version__
        assert "EXITED" in call(launcher, "logs")
        print("Portable + launcher + Lua: OK")


if __name__ == "__main__":
    main()
