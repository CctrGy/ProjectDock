"""Lanzador mínimo: delega en el motor distribuido dentro de .project."""
import ctypes
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(sys.executable).resolve().parent
    engine = root / ".project/runtime/ProjectDock.exe"
    if not engine.is_file():
        message = "Falta .project/runtime/ProjectDock.exe. Regenera el lanzador desde ProjectDock."
        print(message, file=sys.stderr)
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(None, message, "ProjectDock", 0x10)
        return 1
    try:
        explorer_launch = False
        if sys.platform == "win32":
            processes = (ctypes.c_ulong * 4)()
            explorer_launch = ctypes.windll.kernel32.GetConsoleProcessList(processes, 4) == 1
        code = subprocess.call([str(engine), "--project", str(root), *sys.argv[1:]], cwd=root)
        if code and explorer_launch:
            ctypes.windll.user32.MessageBoxW(None,
                f"La ejecución terminó con código {code}.\nAbre 'run dock' para configurar o 'run logs' para ver el resultado.",
                "ProjectDock · Diagnóstico", 0x10)
        return code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
