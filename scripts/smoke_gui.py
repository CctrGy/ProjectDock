"""Comprueba widgets y captura solo la ventana propia en Windows."""
import os
import sys
import tempfile
import ctypes
import time
import tkinter as tk
from pathlib import Path

from projectdock.gui import DockWindow
from projectdock.project import enable_tool, initialize


def main():
    with tempfile.TemporaryDirectory(prefix="projectdock-gui-") as directory:
        base = Path(directory)
        os.environ["PROJECTDOCK_HOME"] = str(base / "settings")
        os.environ["PROJECTDOCK_CATALOG"] = str(base / "projects.db")
        root = base / "Demo"
        root.mkdir()
        (root / "main.py").write_text("print('Demo de ProjectDock')", encoding="utf-8")
        initialize(root, python=sys.executable)
        enable_tool(root, "pytest")
        if os.name == "nt":
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        window = tk.Tk()
        failures = []
        window.report_callback_exception = lambda *args: failures.append(str(args))
        app = DockWindow(window, root)
        window.update()
        assert app.actions.exists("start")
        assert app.actions.exists("test")
        for index in range(4):
            app.tabs.select(index)
            window.update()
        app.tabs.select(0)
        window.update()
        if len(sys.argv) > 1:
            from PIL import ImageGrab
            window.lift()
            window.update()
            time.sleep(0.8)
            x, y = window.winfo_rootx(), window.winfo_rooty()
            ImageGrab.grab((x, y, x + window.winfo_width(), y + window.winfo_height())).save(sys.argv[1])
        window.destroy()
        assert not failures, failures
        print("GUI smoke: OK")


if __name__ == "__main__":
    main()
