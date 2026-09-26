"""Entrada Windows sin consola; el motor conserva su CLI y sus workers."""
import ctypes
import subprocess
import sys
from pathlib import Path


def main():
    engine = Path(sys.executable).resolve().with_name("ProjectDock.exe")
    try:
        subprocess.Popen([str(engine), "--gui"], cwd=engine.parent,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return 0
    except OSError as exc:
        ctypes.windll.user32.MessageBoxW(None, str(exc), "ProjectDock", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
