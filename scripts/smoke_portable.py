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
        # Comprobar argumentos y una consola real, también a través de run.exe.
        probe = root / "terminal_probe.py"
        probe.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "Path('terminal-result.json').write_text(json.dumps({"
            "'tty':[sys.stdin.isatty(),sys.stdout.isatty(),sys.stderr.isatty()],"
            "'args':sys.argv[1:]}),encoding='utf-8')\n"
            "print('\\x1b[32mconsole probe\\x1b[0m')\n"
            "raise SystemExit(7)\n", encoding="utf-8")
        call(engine, "add-action", "Portable", "terminal-check", "--", sys.executable, str(probe))
        call(engine, "launcher", "Portable")
        assert rule.read_text(encoding="utf-8") == 'return {"--version"}'
        call(engine, "trust", "Portable")
        tricky = ["two words", 'a"quote', "áé中", "&|<>^%", "--debug-terminal"]
        call(launcher, "terminal-check", "--debug-terminal", "--", *tricky, code=7)
        result = json.loads((root / "terminal-result.json").read_text(encoding="utf-8"))
        assert result["tty"] == [True, True, True], result
        assert result["args"] == tricky, result
        print("Portable + launcher + Lua + real console + argument fidelity: OK")


if __name__ == "__main__":
    main()
