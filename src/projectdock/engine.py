from __future__ import annotations

import copy
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .project import load, recipes
from .storage import DockError, lock, new_id, read_json, settings_path, write_json
from . import validation
from .processes import ProcessTree


def trust_digest(root: Path):
    digest = hashlib.sha256()
    for folder in ["recipes", "profiles", "rules", "connectors", "scripts"]:
        for path in sorted((root / ".project" / folder).rglob("*")):
            if path.is_file():
                digest.update(str(path.relative_to(root)).encode())
                digest.update(path.read_bytes())
    config = load(root)
    config.pop("trusted", None)
    digest.update(json.dumps(config, sort_keys=True).encode())
    return digest.hexdigest()


def grant_trust(root: Path):
    # Confiar es una decisión de esta máquina; nunca se importa desde el proyecto.
    path = settings_path().parent / "trust.json"
    with lock(path.with_suffix(".lock")):
        trusted = read_json(path, {})
        trusted[str(root.resolve())] = trust_digest(root)
        write_json(path, trusted)


def require_trust(root: Path):
    trusted = read_json(settings_path().parent / "trust.json", {})
    if trusted.get(str(root.resolve())) != trust_digest(root):
        raise DockError("Configuración nueva o modificada. Revísala y usa 'trust' antes de ejecutar.")


def project_python(root: Path, config: dict):
    for folder in [root / ".project/python", root / ".venv"]:
        candidate = folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if candidate.is_file():
            return str(candidate)
    return config.get("python", "python")


def expand(value: str, root: Path, config: dict, environment: dict, profile: dict, secret_values: list[str]):
    value = value.replace("{root}", str(root)).replace("{python}", project_python(root, config))
    def substitute(match):
        kind, name = match.group(1), match.group(2)
        if kind == "env":
            if name not in environment:
                raise DockError(f"Falta la variable de entorno {name}")
            return environment[name]
        if kind == "secret":
            key = "PROJECTDOCK_SECRET_" + name.upper()
            if key not in os.environ:
                raise DockError(f"Falta el secreto {key}")
            secret_values.append(os.environ[key])
            return os.environ[key]
        tools = {**config.get("tools", {})}
        for tool, values in profile.get("tools", {}).items():
            tools[tool] = {**tools.get(tool, {}), **values}
        setting = tools.get(name, {})
        if not setting.get("enabled"):
            raise DockError(f"Herramienta deshabilitada: {name}")
        executable = setting.get("executable", "")
        if not executable:
            raise DockError(f"Configura el ejecutable del conector {name}")
        executable = executable.replace("{root}", str(root)).replace("{python}", project_python(root, config))
        local = root / ".project/tools" / name / executable
        global_path = shutil.which(executable, path=environment.get("PATH"))
        priority = setting.get("priority", "local-first")
        candidates = [global_path, str(local) if local.is_file() else None] if priority == "global-first" else [str(local) if local.is_file() else None, global_path]
        if priority == "manual":
            manual = Path(executable)
            if not manual.is_absolute():
                manual = root / manual
            candidates = [str(manual) if manual.is_file() else None]
        found = next((item for item in candidates if item), None)
        if not found:
            raise DockError(f"No se encuentra la herramienta {name}: {executable}")
        return found
    return re.sub(r"\{(env|secret|tool):([^{}]+)\}", substitute, value)


def plan(root: Path, action=None, profile_name=None, extra=None, replace_args=False, apply_rules=False):
    root = root.resolve()
    config = load(root)
    action = action or config["default_action"]
    recipe = recipes(root).get(action)
    if not recipe:
        raise DockError(f"No existe la receta '{action}'; configúrala con 'run dock'")
    recipe = copy.deepcopy(recipe)
    profile_name = profile_name or config["default_profile"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", profile_name):
        raise DockError("Nombre de perfil inválido")
    profile = validation.profile(read_json(root / ".project/profiles" / f"{profile_name}.json"))
    if recipe.get("tool"):
        tool = recipe["tool"]
        enabled = profile.get("tools", {}).get(tool, {}).get("enabled", config.get("tools", {}).get(tool, {}).get("enabled", False))
        if not enabled:
            raise DockError(f"Herramienta deshabilitada: {tool}")
    if "steps" in recipe:
        return {"action": action, "profile": profile_name, "steps": recipe["steps"], "mode": recipe.get("mode", "sequence"), "recipe": recipe}
    command = recipe.get("command", [])
    if not isinstance(command, list) or not command or not all(isinstance(s, str) for s in command):
        raise DockError("command debe ser una lista no vacía de argumentos")
    defaults = profile.get("args", {}).get(action, recipe.get("args", []))
    args = list(extra or []) if replace_args else [*defaults, *(extra or [])]
    schema = recipe.get("options", {})
    values = {name: item["default"] for name, item in schema.items() if "default" in item}
    values.update(profile.get("options", {}).get(action, {}))
    unknown_options = set(values) - set(schema)
    if unknown_options:
        raise DockError("Opciones de perfil desconocidas: " + ", ".join(sorted(unknown_options)))
    # Las opciones declaradas se resuelven una sola vez: CLI prevalece sobre perfil.
    flags = {spec.get("flag", "--" + name): name for name, spec in schema.items()}
    for token in defaults if not replace_args else []:
        if token.split("=", 1)[0] in flags:
            raise DockError("Define las opciones tipadas en options, no en args: " + token)
    remaining = []
    incoming = list(extra or [])
    position = 0
    while position < len(incoming):
        token = incoming[position]
        flag, separator, inline = token.partition("=")
        name = flags.get(flag)
        if name is None:
            remaining.append(token)
            position += 1
            continue
        spec = schema[name]
        if spec.get("type", "string") == "boolean":
            if separator and inline not in {"true", "false"}:
                raise DockError(f"{flag} admite true o false")
            values[name] = inline != "false" if separator else True
        else:
            if separator:
                value = inline
            else:
                position += 1
                if position >= len(incoming):
                    raise DockError(f"Falta valor para {flag}")
                value = incoming[position]
            try:
                values[name] = int(value) if spec.get("type") == "integer" else value
            except ValueError as exc:
                raise DockError(f"Se esperaba un entero para {flag}") from exc
        position += 1
    args = [*([] if replace_args else defaults), *remaining]
    for name, spec in schema.items():
        if name not in values:
            if spec.get("required"):
                raise DockError(f"Falta opción requerida: {name}")
            continue
        value = values[name]
        expected = {"string": str, "integer": int, "boolean": bool}.get(spec.get("type", "string"))
        if expected is None or type(value) is not expected:
            raise DockError(f"Tipo incorrecto para {name}")
        if "choices" in spec and value not in spec["choices"]:
            raise DockError(f"Valor no permitido para {name}")
        if value not in (False, None) and any(values.get(other) not in (False, None) for other in spec.get("conflicts", [])):
            raise DockError(f"Opción incompatible: {name}")
        flag = spec.get("flag", "--" + name)
        if expected is bool:
            if value:
                args.append(flag)
        else:
            args.extend([flag, str(value)])
    if recipe.get("lua"):
        if not apply_rules:
            raise DockError("Esta receta usa Lua: autoriza el proyecto y usa 'plan --rules' para evaluarla")
        require_trust(root)
        rule = (root / ".project" / recipe["lua"]).resolve()
        if not rule.is_relative_to((root / ".project/rules").resolve()):
            raise DockError("Las reglas Lua deben estar en .project/rules")
        payload = {"source": rule.read_text(encoding="utf-8"), "context": {"system": sys.platform, "profile": profile_name, "options": values, "args": args}}
        worker = [sys.executable, "--lua-worker"] if getattr(sys, "frozen", False) else [sys.executable, "-m", "projectdock", "--lua-worker"]
        try:
            result = subprocess.run(worker, input=json.dumps(payload), text=True, capture_output=True, timeout=3, creationflags=0x08000000 if os.name == "nt" else 0)
            if result.returncode:
                raise DockError("Regla Lua rechazada: " + result.stderr.strip())
            args = json.loads(result.stdout)
            if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
                raise DockError("Lua debe devolver una lista de argumentos de texto")
        except subprocess.TimeoutExpired as exc:
            raise DockError("Regla Lua excedió 3 segundos") from exc
    environment = dict(os.environ)
    secrets = []
    for layer in [config.get("environment", {}), recipe.get("environment", {}), profile.get("environment", {})]:
        for key, value in layer.items():
            environment[key] = expand(str(value), root, config, environment, profile, secrets)
    resolved = [expand(s, root, config, environment, profile, secrets) for s in [*command, *args]]
    cwd = Path(expand(recipe.get("cwd", "{root}"), root, config, environment, profile, secrets))
    if not cwd.is_absolute():
        cwd = root / cwd
    cwd = cwd.resolve()
    if not cwd.is_dir():
        raise DockError(f"Directorio de trabajo inexistente: {cwd}")
    executable = shutil.which(resolved[0], path=environment.get("PATH"))
    if not executable:
        candidate = Path(resolved[0])
        if not candidate.is_absolute():
            candidate = cwd / candidate
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        raise DockError(f"Ejecutable no encontrado: {resolved[0]}")
    resolved[0] = executable
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        # Evita expansión accidental al cruzar la frontera de cmd.exe.
        if any(any(c in s for c in '\r\n&|<>^%!\"') for s in resolved):
            raise DockError("Argumento no seguro para un archivo CMD/BAT; usa un ejecutable directo")
        resolved = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", " ".join('"' + s + '"' for s in resolved)]
    return {"action": action, "profile": profile_name, "command": resolved, "cwd": str(cwd), "environment": environment, "secrets": secrets, "recipe": recipe}


def redact(text: str, secrets):
    for value in sorted(set(secrets), key=len, reverse=True):
        if value:
            text = text.replace(value, "***")
    return text


def public_plan(value):
    def clean(item):
        if isinstance(item, str):
            return redact(item, value.get("secrets", []))
        if isinstance(item, list):
            return [clean(part) for part in item]
        if isinstance(item, dict):
            return {key: clean(part) for key, part in item.items()}
        return item
    return {key: clean(item) for key, item in value.items() if key in {"action", "profile", "command", "cwd", "steps", "mode"}}


def lua_worker():
    from lupa.lua54 import LuaRuntime
    payload = json.load(sys.stdin)
    lua = LuaRuntime(max_memory=8 * 1024 * 1024, register_eval=False, register_builtins=False)
    # Solo bibliotecas de cálculo; no acceso a Python, archivos, módulos o procesos.
    for name in ["python", "os", "io", "package", "require", "dofile", "loadfile", "debug", "load", "print", "warn"]:
        lua.globals()[name] = None
    def table(value):
        if isinstance(value, dict):
            return lua.table_from({k: table(v) for k, v in value.items()})
        if isinstance(value, list):
            return lua.table_from([table(v) for v in value])
        return value
    lua.globals()["context"] = table(payload["context"])
    result = lua.execute(payload["source"])
    print(json.dumps([result[i] for i in range(1, len(result) + 1)]))


def process_alive(pid, created):
    import psutil
    try:
        process = psutil.Process(pid)
        return abs(process.create_time() - created) < 0.01 and process.is_running()
    except psutil.Error:
        return False


def terminate_tree(pid):
    import psutil
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.Error:
                pass
        parent.terminate()
        _, alive = psutil.wait_procs([*children, parent], timeout=2)
        for process in alive:
            try:
                process.kill()
            except psutil.Error:
                pass
    except psutil.Error:
        pass


def stop(root: Path, action=None):
    for path in (root / ".project/state").glob("*.json"):
        record = read_json(path)
        if (not action or record["action"] == action) and record.get("status") in {"STARTING", "RUNNING"}:
            if process_alive(record["pid"], record["created"]):
                # El supervisor observa esta señal y mata su propio árbol.
                write_json(path.with_suffix(".stop"), {"stop": True})


def preflight(root, action=None, profile=None, chain=()):
    """Valida el grafo completo antes de iniciar el primer proceso del grupo."""
    config = load(root)
    action = action or config["default_action"]
    if action in chain:
        raise DockError("Dependencia circular: " + " → ".join([*chain, action]))
    all_recipes = recipes(root)
    if action not in all_recipes:
        raise DockError(f"No existe la receta '{action}'")
    for step in all_recipes[action].get("steps", []):
        preflight(root, step, profile, (*chain, action))
    # Las hojas se resuelven al ejecutarlas: un paso anterior puede crear su entorno.


def run(root: Path, action=None, profile=None, extra=None, replace_args=False, output=print, cancel=None, chain=()):
    import psutil
    require_trust(root)
    if cancel and cancel.is_set():
        return 130
    if not chain:
        preflight(root, action, profile)
    resolved = plan(root, action, profile, extra, replace_args, apply_rules=True)
    action = resolved["action"]
    if action in chain:
        raise DockError("Dependencia circular: " + " → ".join([*chain, action]))
    if "steps" in resolved:
        steps = resolved["steps"]
        if resolved["mode"] == "parallel":
            from concurrent.futures import ThreadPoolExecutor, as_completed
            group_cancel = cancel or threading.Event()
            with ThreadPoolExecutor(max_workers=max(1, min(len(steps), 16))) as pool:
                futures = [pool.submit(run, root, step, resolved["profile"], output=output, cancel=group_cancel, chain=(*chain, action)) for step in steps]
                codes = []
                try:
                    for future in as_completed(futures):
                        code = future.result()
                        codes.append(code)
                        if code:
                            group_cancel.set()
                except BaseException:
                    group_cancel.set()
                    raise
            return next((code for code in codes if code), 0)
        for step in steps:
            code = run(root, step, resolved["profile"], output=output, cancel=cancel, chain=(*chain, action))
            if code:
                return code
        return 0
    recipe = resolved["recipe"]
    run_id = new_id()
    state_dir = root / ".project/state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{run_id}.json"
    record = {"id": run_id, "action": action, "profile": resolved["profile"], "status": "STARTING", "pid": os.getpid(), "created": psutil.Process().create_time(), "started": datetime.now(timezone.utc).isoformat()}
    with lock(state_dir / "actions.lock"):
        if recipe.get("instance", "block") != "allow":
            for path in state_dir.glob("*.json"):
                previous = read_json(path)
                if previous["action"] == action and previous["status"] in {"STARTING", "RUNNING"} and process_alive(previous["pid"], previous["created"]):
                    raise DockError(f"La receta {action} ya está en ejecución")
        write_json(state_file, record)
    logs = root / ".project/logs"
    logs.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    process = None
    tree = None
    code = 1
    log_limit = int(load(root).get("logs", {}).get("max_bytes_per_run", 10 * 1024 * 1024))
    written = 0
    reader_stop = threading.Event()
    reader = None
    pending = ""
    secrets = resolved["secrets"]
    secret_tail = max([len(s) for s in secrets] or [1]) - 1
    def clean_chunk(chunk, final=False):
        nonlocal pending
        pending += chunk
        cut = len(pending) if final else max(0, len(pending) - secret_tail)
        if not final:
            for secret in secrets:
                if not secret:
                    continue
                start = pending.find(secret)
                while start != -1:
                    if start < cut < start + len(secret):
                        cut = start
                    start = pending.find(secret, start + 1)
        clean = redact(pending[:cut], secrets)
        pending = pending[cut:]
        return clean
    try:
        invocation = resolved["command"]
        if os.name == "nt" and invocation[1:4] == ["/d", "/s", "/c"]:
            # cmd no usa las reglas de escape del runtime C de list2cmdline.
            invocation = subprocess.list2cmdline(invocation[:4]) + ' "' + invocation[4] + '"'
        process = subprocess.Popen(invocation, cwd=resolved["cwd"], env=resolved["environment"], stdin=None if recipe.get("interactive") else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            creationflags=0x08000000 if os.name == "nt" else 0, start_new_session=os.name != "nt")
        tree = ProcessTree(process)
        record.update(status="RUNNING", child_pid=process.pid)
        write_json(state_file, record)
        messages = queue.Queue(maxsize=128)
        def send(item):
            while not reader_stop.is_set():
                try:
                    messages.put(item, timeout=0.1)
                    return
                except queue.Full:
                    continue
        def read_output():
            try:
                while not reader_stop.is_set():
                    line = process.stdout.readline(8192)
                    if not line:
                        break
                    send(line)
            except (OSError, ValueError):
                pass
            finally:
                send(None)
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        done = False
        with (logs / f"{run_id}.log").open("wb") as stream:
            def emit(line):
                nonlocal written
                if not line:
                    return
                encoded = line.encode("utf-8")
                if written < log_limit:
                    # No corta una secuencia UTF-8 al alcanzar el límite.
                    data = encoded[:log_limit - written].decode("utf-8", errors="ignore").encode("utf-8")
                    stream.write(data)
                    stream.flush()
                    written += len(data)
                output(line.rstrip("\r\n"))
            while not done or process.poll() is None:
                timeout = recipe.get("timeout", 0)
                if (cancel and cancel.is_set()) or state_file.with_suffix(".stop").exists() or (timeout and time.monotonic() - started > timeout):
                    tree.terminate()
                    record["reason"] = "cancelled" if not timeout or time.monotonic() - started <= timeout else "timeout"
                    code = 130 if record["reason"] == "cancelled" else 124
                    emit(clean_chunk("", final=True))
                    break
                if process.poll() is not None and not done:
                    # No mantener huérfanos que retengan la salida del padre.
                    tree.terminate()
                try:
                    line = messages.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line is None:
                    done = True
                    emit(clean_chunk("", final=True))
                else:
                    emit(clean_chunk(line))
            if done and "reason" not in record:
                code = process.wait()
    except KeyboardInterrupt:
        code = 130
        if process:
            tree.terminate() if tree else terminate_tree(process.pid)
    except Exception as exc:
        if process:
            tree.terminate() if tree else terminate_tree(process.pid)
        record["reason"] = redact(str(exc), secrets)
        if not (logs / f"{run_id}.log").exists():
            (logs / f"{run_id}.log").write_text(record["reason"] + "\n", encoding="utf-8")
        raise DockError(record["reason"]) from exc
    finally:
        reader_stop.set()
        if tree:
            tree.close()
        if process:
            if process.poll() is None:
                terminate_tree(process.pid)
            process.wait(timeout=5)
        if reader:
            reader.join(timeout=1)
        if process and process.stdout and (not reader or not reader.is_alive()):
            process.stdout.close()
        record.update(status="STOPPED" if code == 130 else "EXITED" if code == 0 else "FAILED", exit_code=code, duration=round(time.monotonic() - started, 3))
        write_json(state_file, record)
        write_json(logs / f"{run_id}.json", record)
        state_file.with_suffix(".stop").unlink(missing_ok=True)
        keep = max(1, int(load(root).get("logs", {}).get("keep_runs", 100)))
        with lock(logs / "retention.lock"):
            for old in sorted(logs.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[keep:]:
                old.with_suffix(".log").unlink(missing_ok=True)
                (state_dir / old.name).unlink(missing_ok=True)
                old.unlink(missing_ok=True)
    return code
