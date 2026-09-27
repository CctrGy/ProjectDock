"""Alta y edición mediante widgets reales, con catálogo temporal."""
import os
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from projectdock.gui import DockWindow
from projectdock.storage import catalog


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def button(widget, text):
    return next(child for child in descendants(widget)
                if child.winfo_class() == "TButton" and child.cget("text") == text)


with tempfile.TemporaryDirectory(prefix="projectdock-dialog-") as directory:
    base = Path(directory)
    os.environ["PROJECTDOCK_HOME"] = str(base / "home")
    os.environ["PROJECTDOCK_CATALOG"] = str(base / "projects.db")
    project = (base / "First project").resolve()
    project.mkdir()
    (project / "main.py").write_text("print('fixture')", encoding="utf-8")
    window = tk.Tk()
    app = DockWindow(window)
    try:
        assert app.project_button.cget("text") == "+ Incorporar proyecto"
        with patch("projectdock.gui.filedialog.askdirectory", return_value=str(project)), \
             patch("projectdock.gui.generate_launcher") as generate:
            app.project_button.invoke()
            dialog = next(child for child in window.winfo_children() if isinstance(child, tk.Toplevel))
            dialog.geometry("540x400")
            window.update()
            add = button(dialog, "add")
            assert add.winfo_ismapped()
            assert add.winfo_rooty() + add.winfo_height() <= dialog.winfo_rooty() + dialog.winfo_height()
            add.invoke()
            window.update()
            generate.assert_called_once_with(project)
        rows = catalog()["projects"]
        assert len(rows) == 1 and rows[0]["name"] == "First project"
        identity = rows[0]["instance_id"]
        assert app.project_button.cget("text") == "# editar proyecto"
        assert app.new_project_button.winfo_ismapped()
        with patch("projectdock.gui.filedialog.askdirectory") as choose, \
             patch("projectdock.gui.generate_launcher") as generate:
            app.project_button.invoke()
            dialog = next(child for child in window.winfo_children() if isinstance(child, tk.Toplevel))
            name = next(child for child in descendants(dialog) if child.winfo_class() == "TEntry")
            name.delete(0, "end")
            name.insert(0, "Renamed project")
            button(dialog, "Guardar cambios").invoke()
            window.update()
            choose.assert_not_called()
            generate.assert_not_called()
        rows = catalog()["projects"]
        assert len(rows) == 1 and rows[0]["name"] == "Renamed project"
        assert rows[0]["instance_id"] == identity
        with patch("projectdock.gui.filedialog.askdirectory", return_value="") as choose:
            app.new_project_button.invoke()
            choose.assert_called_once()
        print("Visible add + registration + editing without duplicates + new project: OK")
    finally:
        window.destroy()
