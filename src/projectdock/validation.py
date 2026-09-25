"""Validación de los contratos antes de escribir o ejecutar configuración."""
import math
import re

from .storage import DockError

RESERVED = {"dock", "info", "logs", "stop", "plan", "tools", "trust", "update-launcher", "tui", "status"}


def mapping(value, label):
    if not isinstance(value, dict):
        raise DockError(f"{label} debe ser un objeto JSON")
    return value


def strings(value, label, nonempty=False):
    if not isinstance(value, list) or not all(isinstance(x, str) and "\0" not in x for x in value) or (nonempty and not value):
        raise DockError(f"{label} debe ser una lista de textos" + (" no vacía" if nonempty else ""))


def name(value, label, allow_empty=False):
    if allow_empty and value == "":
        return
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise DockError(f"{label} inválido")


def environment(value):
    mapping(value, "environment")
    for key, item in value.items():
        if not isinstance(key, str) or not key or any(x in key for x in "=\0"):
            raise DockError("Nombre de variable de entorno inválido")
        if not isinstance(item, (str, int, float, bool)) or "\0" in str(item):
            raise DockError(f"Valor de entorno inválido: {key}")


def tools(value):
    mapping(value, "tools")
    for key, item in value.items():
        name(key, "Nombre de conector")
        mapping(item, f"tools.{key}")
        if "enabled" in item and type(item["enabled"]) is not bool:
            raise DockError(f"tools.{key}.enabled debe ser booleano")
        if item.get("priority", "local-first") not in {"local-first", "global-first", "manual"}:
            raise DockError(f"Prioridad desconocida para {key}")
        if "executable" in item and not isinstance(item["executable"], str):
            raise DockError(f"Ejecutable inválido para {key}")


def project(value):
    mapping(value, "project.json")
    if value.get("schema") != 1:
        raise DockError("Versión de configuración no compatible")
    for key in ["id", "instance_id", "name", "default_action", "default_profile"]:
        if not isinstance(value.get(key), str) or (key != "default_action" and not value[key].strip()):
            raise DockError(f"project.json requiere un campo de texto '{key}'")
    strings(value.get("languages"), "languages", nonempty=True)
    name(value["default_action"], "Acción predeterminada", allow_empty=True)
    name(value["default_profile"], "Perfil predeterminado")
    tools(value.get("tools"))
    environment(value.get("environment", {}))
    logs = mapping(value.get("logs", {}), "logs")
    for key in ["keep_runs", "max_bytes_per_run"]:
        if key in logs and (type(logs[key]) is not int or logs[key] < 1):
            raise DockError(f"logs.{key} debe ser un entero positivo")
    if not isinstance(value.get("python", "python"), str):
        raise DockError("python debe ser una ruta o nombre de ejecutable")
    return value


def recipe(value, fallback=""):
    mapping(value, "Receta")
    key = value.get("name", fallback)
    name(key, "Nombre de receta")
    if key in RESERVED:
        raise DockError(f"Nombre de receta reservado: {key}")
    if "steps" in value:
        strings(value["steps"], "steps", nonempty=True)
        if value.get("command"):
            raise DockError("Una receta no puede tener command y steps simultáneamente")
        if value.get("mode", "sequence") not in {"sequence", "parallel"}:
            raise DockError("Modo de grupo desconocido")
    else:
        strings(value.get("command"), "command", nonempty=True)
    strings(value.get("args", []), "args")
    environment(value.get("environment", {}))
    if value.get("instance", "block") not in {"block", "allow"}:
        raise DockError("instance debe ser block o allow")
    timeout = value.get("timeout", 0)
    if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout < 0:
        raise DockError("timeout debe ser un número finito no negativo")
    if not isinstance(value.get("cwd", "{root}"), str):
        raise DockError("cwd debe ser una ruta")
    if "lua" in value and not isinstance(value["lua"], str):
        raise DockError("lua debe ser una ruta")
    options = mapping(value.get("options", {}), "options")
    flags = set()
    for option, spec in options.items():
        name(option, "Nombre de opción")
        mapping(spec, f"options.{option}")
        if spec.get("type", "string") not in {"string", "integer", "boolean"}:
            raise DockError(f"Tipo de opción desconocido: {option}")
        flag = spec.get("flag", "--" + option)
        if not isinstance(flag, str) or not flag.startswith("-") or flag in flags:
            raise DockError(f"Flag inválido o duplicado: {flag}")
        flags.add(flag)
        strings(spec.get("conflicts", []), "conflicts")
        if any(other not in options for other in spec.get("conflicts", [])):
            raise DockError(f"Conflicto con opción inexistente: {option}")
        if "choices" in spec and not isinstance(spec["choices"], list):
            raise DockError("choices debe ser una lista")
    return value


def profile(value):
    mapping(value, "Perfil")
    environment(value.get("environment", {}))
    tools(value.get("tools", {}))
    for key, args in mapping(value.get("args", {}), "args de perfil").items():
        name(key, "Receta de perfil")
        strings(args, f"args.{key}")
    for key, options in mapping(value.get("options", {}), "options de perfil").items():
        name(key, "Receta de perfil")
        mapping(options, f"options.{key}")
    return value


def connector(value):
    mapping(value, "Conector")
    strings(value.get("languages"), "languages", nonempty=True)
    if not isinstance(value.get("executable"), str):
        raise DockError("El conector requiere executable")
    for key, command in mapping(value.get("recipes", {}), "recipes").items():
        recipe({"name": key, "command": command})
    return value
