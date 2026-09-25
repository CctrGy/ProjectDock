"""Prueba el Dock compilado y su lanzador sin depender del paquete instalado."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    engine = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="projectdock-portable-") as directory:
        base = Path(directory)
        root = base / "project with spaces"
        root.mkdir()
        environment = dict(os.environ, PROJECTDOCK_HOME=str(base / "settings"), PROJECTDOCK_CATALOG=str(base / "projects.db"))
        environment.pop("PYTHONPATH", None)
        def call(executable, *args, code=0):
            result = subprocess.run([str(executable), *args], cwd=base, env=environment, text=True, capture_output=True, timeout=40)
            assert result.returncode == code, (args, result.stdout, result.stderr)
            return result.stdout
        assert call(engine, "--version").strip() == "0.1.0"
        call(engine, "register", str(root), "--name", "Portable")
        # El programa de prueba es otro ejecutable empaquetado, no Python externo.
        call(engine, "add-action", "Portable", "start", "--", str(engine), "--version")
        call(engine, "launcher", "Portable")
        launcher = root / "run.exe"
        call(engine, "trust", "Portable")
        assert call(launcher).strip() == "0.1.0"
        assert call(engine, "start", "Portable").strip() == "0.1.0"
        # Lua debe funcionar también dentro del runtime copiado.
        rule = root / ".project/rules/test.lua"
        rule.write_text('return {"--version"}', encoding="utf-8")
        recipe = root / ".project/recipes/start.json"
        value = json.loads(recipe.read_text())
        value["command"] = [str(engine)]
        value["lua"] = "rules/test.lua"
        recipe.write_text(json.dumps(value), encoding="utf-8")
        call(engine, "trust", "Portable")
        assert call(launcher).strip() == "0.1.0"
        assert "EXITED" in call(launcher, "logs")
        print("Portable + launcher + Lua: OK")


if __name__ == "__main__":
    main()
