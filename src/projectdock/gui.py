from __future__ import annotations

import json
import ctypes
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .engine import grant_trust, plan, public_plan, run, stop
from .project import available_connectors, detect, enable_tool, generate_launcher, initialize, load, recipes, save_recipe
from .storage import DockError, catalog, catalog_path, change_catalog, read_json, register, write_json

BG, PANEL, TEXT, MUTED, ACCENT = "#101820", "#182630", "#edf5fa", "#a5b8c7", "#68dfbb"


class DockWindow:
    def __init__(self, window, project=None):
        self.window = window
        self.root = project
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.editor_path = None
        window.title("ProjectDock · Centro de proyectos")
        window.geometry("1180x800")
        window.minsize(980, 650)
        window.configure(bg=BG)
        style = ttk.Style(window)
        style.theme_use("clam")
        style.configure(".", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG)
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground=ACCENT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", padding=(12, 8), background="#263d4c")
        style.map("TButton", background=[("active", "#34576a")])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, rowheight=30, borderwidth=0)
        style.map("Treeview", background=[("selected", "#285b59")])
        style.configure("TNotebook.Tab", padding=(14, 9))
        style.configure("TNotebook.Tab", background="#263d4c", foreground=TEXT)
        style.map("TNotebook.Tab", background=[("selected", "#285b59"), ("active", "#34576a")])
        style.configure("Treeview.Heading", background="#263d4c", foreground=TEXT)
        style.configure("TEntry", fieldbackground=PANEL, insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground=PANEL, arrowcolor=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], selectbackground=[("readonly", PANEL)])
        header = ttk.Frame(window, padding=(22, 18))
        header.pack(fill="x")
        ttk.Label(header, text="ProjectDock", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="PROYECTOS  /  RECETAS  /  CONECTORES", style="Muted.TLabel").pack(side="left", padx=24)
        ttk.Button(header, text="Catálogo…", command=self.catalog_settings).pack(side="right")
        body = ttk.Panedwindow(window, orient="horizontal")
        body.pack(fill="both", expand=True, padx=18)
        sidebar = ttk.Frame(body, padding=(0, 0, 14, 0))
        body.add(sidebar, weight=1)
        ttk.Label(sidebar, text="TU DOCK", style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        self.projects = tk.Listbox(sidebar, width=26, bg=PANEL, fg=TEXT, selectbackground="#285b59", relief="flat", highlightthickness=0, font=("Segoe UI", 11), exportselection=False)
        self.projects.pack(fill="both", expand=True)
        self.projects.bind("<<ListboxSelect>>", self.select_project)
        ttk.Button(sidebar, text="+ Incorporar proyecto", command=self.wizard).pack(fill="x", pady=(12, 5))
        ttk.Button(sidebar, text="Actualizar lista", command=self.refresh).pack(fill="x")
        content = ttk.Frame(body, padding=(12, 0))
        body.add(content, weight=4)
        self.heading = ttk.Label(content, text="Un lugar para tus proyectos", font=("Segoe UI", 19, "bold"))
        self.heading.pack(anchor="w")
        self.subtitle = ttk.Label(content, text="Incorpora una carpeta para configurar sus lanzadores.", style="Muted.TLabel")
        self.subtitle.pack(anchor="w", pady=(3, 12))
        bar = ttk.Frame(content)
        bar.pack(fill="x", pady=(0, 12))
        for text, command in [("▶ Ejecutar", self.execute), ("■ Detener", self.halt), ("Ver plan", self.preview), ("Autorizar", self.authorize), ("Generar lanzador", self.launcher)]:
            ttk.Button(bar, text=text, command=command).pack(side="left", padx=(0, 6))
        self.profile = ttk.Combobox(content, state="readonly", width=28)
        self.profile.pack(anchor="w", pady=(0, 10))
        self.tabs = ttk.Notebook(content)
        self.tabs.pack(fill="both", expand=True)
        actions_tab, configuration_tab, tools_tab, logs_tab = [ttk.Frame(self.tabs, padding=12) for _ in range(4)]
        for frame, title in [(actions_tab, "Recetas"), (configuration_tab, "Configuración y código"), (tools_tab, "Conectores"), (logs_tab, "Consola / historial")]:
            self.tabs.add(frame, text=title)
        self.actions = ttk.Treeview(actions_tab, columns=("command",), show="tree headings", selectmode="browse")
        self.actions.heading("#0", text="Receta")
        self.actions.column("#0", width=160)
        self.actions.heading("command", text="Comando o pasos")
        self.actions.pack(fill="both", expand=True)
        row = ttk.Frame(actions_tab)
        row.pack(fill="x", pady=10)
        ttk.Button(row, text="+ Receta", command=self.new_recipe).pack(side="left")
        ttk.Button(row, text="Editar receta", command=self.edit_recipe).pack(side="left", padx=8)
        ttk.Button(row, text="Usar por defecto", command=self.default_action).pack(side="left")
        ttk.Label(actions_tab, text="Los argumentos son listas JSON; los scripts vinculados se editan en Configuración.", style="Muted.TLabel", wraplength=680).pack(anchor="w")
        files_bar = ttk.Frame(configuration_tab)
        files_bar.pack(fill="x")
        self.files = ttk.Combobox(files_bar, state="readonly")
        self.files.pack(side="left", fill="x", expand=True)
        self.files.bind("<<ComboboxSelected>>", self.open_editor)
        ttk.Button(files_bar, text="Guardar", command=self.save_editor).pack(side="left", padx=6)
        ttk.Button(files_bar, text="+ Archivo", command=self.new_file).pack(side="left")
        self.editor = tk.Text(configuration_tab, height=16, bg=PANEL, fg=TEXT, insertbackground=ACCENT, undo=True, wrap="none", font=("Consolas", 11), relief="flat")
        self.editor.pack(fill="both", expand=True, pady=10)
        ttk.Label(configuration_tab, text="Los cambios de configuración invalidan la autorización anterior.", style="Muted.TLabel").pack(anchor="w")
        self.tools = ttk.Treeview(tools_tab, columns=("status", "exe"), show="tree headings", selectmode="browse")
        self.tools.heading("#0", text="Conector")
        self.tools.heading("status", text="Estado")
        self.tools.heading("exe", text="Ejecutable")
        self.tools.column("#0", width=150)
        self.tools.column("status", width=100)
        self.tools.pack(fill="both", expand=True)
        row = ttk.Frame(tools_tab)
        row.pack(fill="x", pady=10)
        ttk.Button(row, text="Habilitar", command=lambda: self.toggle_tool(True)).pack(side="left")
        ttk.Button(row, text="Deshabilitar", command=lambda: self.toggle_tool(False)).pack(side="left", padx=8)
        ttk.Label(tools_tab, text="Habilitar crea recetas. No instala ni ejecuta la herramienta.", style="Muted.TLabel").pack(anchor="w")
        row = ttk.Frame(logs_tab)
        row.pack(fill="x")
        ttk.Button(row, text="Última ejecución", command=self.last_log).pack(side="left")
        ttk.Button(row, text="Limpiar vista", command=lambda: self.console.delete("1.0", "end")).pack(side="left", padx=8)
        self.console = tk.Text(logs_tab, height=16, bg="#0a1118", fg=ACCENT, insertbackground=TEXT, wrap="word", font=("Consolas", 10), relief="flat")
        self.console.pack(fill="both", expand=True, pady=10)
        self.status = tk.StringVar(value="Listo · ProjectDock 0.1.0")
        ttk.Label(window, textvariable=self.status, style="Muted.TLabel", padding=(22, 12)).pack(fill="x")
        window.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        if project:
            self.display()
        window.after(100, self.poll)

    def guarded(self, function):
        try:
            return function()
        except (DockError, OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showerror("ProjectDock", str(exc), parent=self.window)
            self.status.set(str(exc))

    def refresh(self):
        def update():
            self.rows = catalog()["projects"]
            self.projects.delete(0, "end")
            for row in self.rows:
                self.projects.insert("end", ("● " if Path(row["path"]).is_dir() else "○ ") + row["name"])
        self.guarded(update)

    def select_project(self, _event=None):
        if self.projects.curselection():
            self.root = Path(self.rows[self.projects.curselection()[0]]["path"])
            self.guarded(self.display)

    def display(self):
        if not self.root:
            return
        config = load(self.root)
        self.heading.configure(text=config["name"])
        self.subtitle.configure(text=f"{self.root}  ·  {', '.join(config['languages'])}")
        self.actions.delete(*self.actions.get_children())
        for name, recipe in recipes(self.root).items():
            self.actions.insert("", "end", iid=name, text=name, values=(" → ".join(recipe.get("steps", [])) or " ".join(recipe.get("command", [])),))
        default = config.get("default_action")
        if default and self.actions.exists(default):
            self.actions.selection_set(default)
        profiles = [p.stem for p in (self.root / ".project/profiles").glob("*.json")]
        self.profile["values"] = profiles
        self.profile.set(config.get("default_profile", "development"))
        self.tools.delete(*self.tools.get_children())
        for name, connector in available_connectors(self.root).items():
            compatible = "*" in connector["languages"] or set(config["languages"]).intersection(connector["languages"])
            if compatible:
                setting = config.get("tools", {}).get(name, {})
                self.tools.insert("", "end", iid=name, text=name, values=("Activo" if setting.get("enabled") else "Inactivo", setting.get("executable", connector.get("executable", ""))))
        paths = [Path("project.json")]
        for folder in ["recipes", "profiles", "connectors", "rules", "scripts"]:
            paths.extend(p.relative_to(self.root / ".project") for p in (self.root / ".project" / folder).rglob("*") if p.is_file() and p.suffix in {".json", ".lua", ".py", ".ps1", ".sh", ".cmd"})
        self.files["values"] = [str(p) for p in paths]
        self.files.set("project.json")
        self.open_editor()
        self.status.set(f"{len(recipes(self.root))} recetas · {config['portability']} · catálogo: {catalog_path()}")

    def selected_action(self):
        selection = self.actions.selection()
        if not self.root or not selection:
            raise DockError("Selecciona un proyecto y una receta")
        return selection[0]

    def authorize(self):
        if self.root and messagebox.askyesno("Autorizar proyecto", "¿Has revisado las recetas, scripts y reglas? Autorizar permite ejecutar su código en tu equipo.", parent=self.window):
            self.guarded(lambda: grant_trust(self.root))
            self.status.set("Configuración actual autorizada")

    def execute(self):
        def start():
            if self.worker and self.worker.is_alive():
                raise DockError("Hay una ejecución en esta ventana; deténla antes de iniciar otra")
            action = self.selected_action()
            root, profile = self.root, self.profile.get()
            self.cancel = threading.Event()
            self.tabs.select(3)
            self.console.insert("end", f"\n▶ {action} · {profile}\n")
            self.status.set("Ejecutando…")
            def worker():
                try:
                    code = run(root, action, profile, output=lambda line: self.events.put(("line", line)), cancel=self.cancel)
                    self.events.put(("done", f"Finalizado · código {code}"))
                except Exception as exc:
                    self.events.put(("done", f"Error: {exc}"))
            self.worker = threading.Thread(target=worker, daemon=True)
            self.worker.start()
        self.guarded(start)

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                self.console.insert("end", value + "\n")
                self.console.see("end")
                if kind == "done":
                    self.status.set(value)
        except queue.Empty:
            pass
        self.window.after(100, self.poll)

    def halt(self):
        self.cancel.set()
        if self.root:
            self.guarded(lambda: stop(self.root))
        self.status.set("Parada solicitada")

    def preview(self):
        def preview():
            value = public_plan(plan(self.root, self.selected_action(), self.profile.get()))
            self.tabs.select(3)
            self.console.insert("end", json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        self.guarded(preview)

    def launcher(self):
        if self.root:
            result = self.guarded(lambda: generate_launcher(self.root))
            if result:
                self.status.set(f"Lanzador generado: {result}")

    def open_editor(self, _event=None):
        if not self.root or not self.files.get():
            return
        def read():
            self.editor_path = self.root / ".project" / self.files.get()
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", self.editor_path.read_text(encoding="utf-8"))
        self.guarded(read)

    def save_editor(self):
        def save():
            if not self.editor_path:
                return
            text = self.editor.get("1.0", "end-1c")
            if self.editor_path.suffix == ".json":
                value = json.loads(text)
                if not isinstance(value, dict):
                    raise DockError("El archivo debe contener un objeto JSON")
                write_json(self.editor_path, value)
            else:
                self.editor_path.write_text(text, encoding="utf-8")
            register(self.root, load(self.root))
            self.refresh()
            self.status.set("Guardado. Revisa y vuelve a autorizar antes de ejecutar.")
        self.guarded(save)

    def new_file(self):
        if not self.root:
            return
        name = simpledialog.askstring("Archivo modular", "Ruta relativa, por ejemplo rules/build.lua o profiles/demo.json:", parent=self.window)
        if not name:
            return
        def create():
            base = (self.root / ".project").resolve()
            path = (base / name).resolve()
            if not path.is_relative_to(base) or path.parts[len(base.parts)] not in {"profiles", "rules", "scripts", "connectors"}:
                raise DockError("Usa profiles/, rules/, scripts/ o connectors/ dentro de .project")
            if path.exists():
                raise DockError("Ese archivo ya existe")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n" if path.suffix == ".json" else "-- return context.args\n" if path.suffix == ".lua" else "", encoding="utf-8")
            self.display()
            self.files.set(str(path.relative_to(base)))
            self.open_editor()
        self.guarded(create)

    def edit_recipe(self):
        def edit():
            name = self.selected_action()
            paths = [p for p in (self.root / ".project/recipes").glob("*.json") if read_json(p).get("name", p.stem) == name]
            self.files.set(str(paths[0].relative_to(self.root / ".project")))
            self.open_editor()
            self.tabs.select(1)
        self.guarded(edit)

    def new_recipe(self):
        if not self.root:
            return
        name = simpledialog.askstring("Nueva receta", "Nombre corto:", parent=self.window)
        if not name:
            return
        command = simpledialog.askstring("Comando", 'Lista JSON, por ejemplo ["{python}", "{root}/main.py"]:', parent=self.window)
        if command:
            def create():
                parsed = json.loads(command)
                if not isinstance(parsed, list) or not parsed or not all(isinstance(x, str) for x in parsed):
                    raise DockError("Introduce una lista de argumentos de texto")
                save_recipe(self.root, name, parsed)
                self.display()
            self.guarded(create)

    def default_action(self):
        def save():
            config = load(self.root)
            config["default_action"] = self.selected_action()
            config["default_profile"] = self.profile.get()
            write_json(self.root / ".project/project.json", config)
            self.status.set("Arranque predeterminado guardado")
        self.guarded(save)

    def toggle_tool(self, enabled):
        selected = self.tools.selection()
        if self.root and selected:
            self.guarded(lambda: enable_tool(self.root, selected[0], enabled))
            self.guarded(self.display)

    def last_log(self):
        def show():
            if not self.root:
                return
            paths = sorted((self.root / ".project/logs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not paths:
                self.console.insert("end", "Sin registros.\n")
                return
            self.console.insert("end", paths[0].read_text(encoding="utf-8") + paths[0].with_suffix(".log").read_text(encoding="utf-8"))
        self.guarded(show)

    def catalog_settings(self):
        path = filedialog.asksaveasfilename(parent=self.window, title="Ubicación del catálogo", initialfile="projects.db", confirmoverwrite=False, filetypes=[("Catálogo ProjectDock", "*.db")])
        if path:
            copy = not Path(path).exists() and messagebox.askyesno("Catálogo", "¿Copiar el catálogo actual a esa ubicación?\nEl original se conservará como copia.", parent=self.window)
            self.guarded(lambda: change_catalog(Path(path), copy))
            self.refresh()

    def wizard(self):
        folder = filedialog.askdirectory(parent=self.window, title="Seleccionar proyecto")
        if not folder:
            return
        root = Path(folder)
        existing = load(root) if (root / ".project/project.json").exists() else {}
        default_recipe = recipes(root).get(existing.get("default_action", ""), {}) if existing else {}
        dialog = tk.Toplevel(self.window)
        dialog.title("Incorporar proyecto · ProjectDock")
        dialog.configure(bg=BG)
        dialog.geometry("650x630")
        dialog.transient(self.window)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Configura tu proyecto", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, text=str(root), style="Muted.TLabel", wraplength=590).pack(anchor="w", pady=(4, 12))
        fields = {}
        for key, label, value in [
            ("name", "Nombre", existing.get("name", root.name)),
            ("languages", "Lenguajes (separados por comas)", ",".join(existing.get("languages", detect(root)))),
            ("python", "Python externo para preparar entornos", existing.get("python", "python")),
            ("args", "Argumentos predeterminados (lista JSON)", json.dumps(default_recipe.get("args", []))),
        ]:
            ttk.Label(frame, text=label).pack(anchor="w", pady=(8, 2))
            variable = tk.StringVar(value=value)
            ttk.Entry(frame, textvariable=variable).pack(fill="x")
            fields[key] = variable
        ttk.Label(frame, text="Conectores iniciales", style="Muted.TLabel").pack(anchor="w", pady=(14, 5))
        checks = ttk.Frame(frame)
        checks.pack(fill="x")
        selected = {}
        for index, name in enumerate(["git", "pytest", "ruff", "npm", "gource", "adr", "github-actions", "docker"]):
            variable = tk.BooleanVar(value=existing.get("tools", {}).get(name, {}).get("enabled", False))
            ttk.Checkbutton(checks, text=name, variable=variable).grid(row=index // 4, column=index % 4, sticky="w", padx=5, pady=4)
            selected[name] = variable
        build_launcher = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Generar run.exe con su motor local", variable=build_launcher).pack(anchor="w", pady=(12, 3))
        ttk.Label(frame, text="Crear el entorno es una receta separada: environment-create.\nNo se instalarán herramientas ni se ejecutará el proyecto al registrarlo.", style="Muted.TLabel", wraplength=590).pack(anchor="w", pady=8)
        def save():
            def work():
                default_args = json.loads(fields["args"].get())
                if not isinstance(default_args, list) or not all(isinstance(x, str) for x in default_args):
                    raise DockError("Los argumentos deben ser una lista de textos")
                config = initialize(root, fields["name"].get(), [x.strip() for x in fields["languages"].get().split(",") if x.strip()], fields["python"].get())
                config.update(name=fields["name"].get(), languages=[x.strip() for x in fields["languages"].get().split(",") if x.strip()], python=fields["python"].get())
                write_json(root / ".project/project.json", config)
                for name, variable in selected.items():
                    if variable.get():
                        enable_tool(root, name)
                default = config.get("default_action")
                recipe_path = root / ".project/recipes" / f"{default}.json"
                if default and recipe_path.exists():
                    recipe = read_json(recipe_path)
                    recipe["args"] = default_args
                    write_json(recipe_path, recipe)
                register(root, config)
                self.root = root
                if build_launcher.get():
                    generate_launcher(root)
                dialog.destroy()
                self.refresh()
                self.display()
            self.guarded(work)
        ttk.Button(frame, text="Guardar proyecto", command=save).pack(anchor="e", pady=12)

    def close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Ejecución activa", "Cerrar detendrá la ejecución iniciada en esta ventana. ¿Continuar?", parent=self.window):
                return
            self.cancel.set()
            self.window.after(150, self.finish_close)
        else:
            self.window.destroy()

    def finish_close(self):
        if self.worker and self.worker.is_alive():
            self.window.after(150, self.finish_close)
        else:
            self.window.destroy()


def show(project=None):
    if os.name == "nt":
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    window = tk.Tk()
    DockWindow(window, project)
    window.mainloop()
