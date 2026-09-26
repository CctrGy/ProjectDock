"""Verifica la entrada gráfica compilada en un perfil temporal de Windows."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import psutil

entry = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="projectdock-window-") as directory:
    env = dict(os.environ, PROJECTDOCK_HOME=directory,
               PROJECTDOCK_CATALOG=str(Path(directory) / "projects.db"))
    subprocess.run([str(entry)], env=env, timeout=20, check=True)
    engine = None
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for process in psutil.process_iter(["exe", "environ"]):
            try:
                if (process.info["exe"] and Path(process.info["exe"]) == entry.with_name("ProjectDock.exe")
                        and process.info["environ"].get("PROJECTDOCK_HOME") == directory):
                    engine = process
                    break
            except (psutil.Error, OSError):
                pass
        if engine:
            break
        time.sleep(0.1)
    assert engine is not None, "No se inició el motor gráfico"
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    windows = []
    @callback
    def visit(hwnd, unused):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == engine.pid and user.IsWindowVisible(hwnd):
            windows.append(hwnd)
        return True
    try:
        while time.monotonic() < deadline and not windows:
            user.EnumWindows(visit, 0)
            time.sleep(0.1)
        assert windows, "La GUI no tiene ventana visible"
        kernel.FreeConsole()
        attached = kernel.AttachConsole(engine.pid)
        error = ctypes.get_last_error()
        kernel.GetConsoleWindow.restype = wintypes.HWND
        user.IsWindowVisible.argtypes = [wintypes.HWND]
        console_visible = bool(attached and user.IsWindowVisible(kernel.GetConsoleWindow()))
        if attached:
            kernel.FreeConsole()
        assert not console_visible and (attached or error == 6), f"Consola visible o fallo de inspección: {error}"
        print("GUI visible sin ventana de consola: OK")
    finally:
        for hwnd in windows:
            user.PostMessageW(hwnd, 0x0010, 0, 0)
        try:
            engine.wait(timeout=10)
        except psutil.TimeoutExpired:
            engine.kill()
