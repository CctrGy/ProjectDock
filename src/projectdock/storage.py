from __future__ import annotations

import contextlib
import ctypes
import json
import os
import tempfile
import time
import uuid
from pathlib import Path


class DockError(Exception):
    pass


def read_json(path: Path, default=None):
    if not path.exists() and default is not None:
        return default
    try:
        def invalid_constant(value):
            raise ValueError(f"Valor JSON no finito: {value}")
        return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=invalid_constant)
    except (OSError, ValueError) as exc:
        raise DockError(f"No se puede leer {path}: {exc}") from exc


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".dock-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def lock(path: Path):
    """Bloqueo liberado por el sistema incluso si el proceso muere."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + 10
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise DockError("Archivo ocupado por otra instancia")
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)


def documents() -> Path:
    if os.name == "nt":
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
            return Path(buffer.value)
    return Path.home() / "Documents"


def settings_path() -> Path:
    base = Path(os.environ.get("PROJECTDOCK_HOME", str(Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".config"))) / "ProjectDock")))
    return base / "settings.json"


def catalog_path() -> Path:
    override = os.environ.get("PROJECTDOCK_CATALOG")
    if override:
        return Path(override).expanduser().resolve()
    settings = read_json(settings_path(), {})
    if not isinstance(settings, dict):
        raise DockError("settings.json debe contener un objeto")
    return Path(settings.get("catalog", str(documents() / "ProjectDock/projects.db")))


def catalog():
    value = read_json(catalog_path(), {"schema": 1, "projects": []})
    validate_catalog(value)
    return value


def validate_catalog(value):
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("projects"), list):
        raise DockError("Formato de catálogo no compatible")
    for row in value["projects"]:
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not row[key] for key in ["name", "path", "project_id", "instance_id"]):
            raise DockError("Entrada de catálogo incompleta o inválida")


def register(root: Path, config: dict):
    path = catalog_path()
    with lock(path.with_suffix(".lock")):
        db = catalog()
        row = next((r for r in db["projects"] if Path(r["path"]).resolve() == root.resolve()), None)
        if not row:
            row = next((r for r in db["projects"] if r["instance_id"] == config["instance_id"] and not Path(r["path"]).exists()), None)
        values = {"name": config["name"], "path": str(root.resolve()), "project_id": config["id"], "instance_id": config["instance_id"]}
        if row:
            row.update(values)
        else:
            db["projects"].append(values)
        write_json(path, db)


def resolve_project(value: str) -> Path:
    direct = Path(value).expanduser()
    if (direct / ".project/project.json").is_file():
        return direct.resolve()
    matches = [r for r in catalog()["projects"] if value.casefold() in (r["name"].casefold(), r["instance_id"].casefold())]
    if len(matches) != 1:
        raise DockError("Proyecto no encontrado o nombre ambiguo; usa su ruta o ID")
    root = Path(matches[0]["path"])
    if not root.is_dir():
        raise DockError(f"Proyecto desconectado o trasladado: {root}")
    return root


def change_catalog(destination: Path, copy_current=False):
    destination = destination.expanduser().resolve()
    if os.environ.get("PROJECTDOCK_CATALOG") and destination != catalog_path().resolve():
        raise DockError("PROJECTDOCK_CATALOG fija el catálogo; elimina esa variable antes de cambiarlo")
    if copy_current and destination != catalog_path().resolve():
        if destination.exists():
            raise DockError("El destino ya existe; ábrelo para conservar su contenido")
        write_json(destination, catalog())
    elif destination.exists():
        value = read_json(destination)
        validate_catalog(value)
    else:
        write_json(destination, {"schema": 1, "projects": []})
    settings = read_json(settings_path(), {})
    settings["catalog"] = str(destination)
    write_json(settings_path(), settings)


def new_id():
    return str(uuid.uuid4())
