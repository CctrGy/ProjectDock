import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

from projectdock.engine import grant_trust, plan, public_plan, run
from projectdock.project import detect, enable_tool, initialize, load, recipes, save_recipe
from projectdock.storage import DockError, catalog, change_catalog, read_json, resolve_project, write_json


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTDOCK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PROJECTDOCK_CATALOG", str(tmp_path / "registry/projects.db"))
    root = tmp_path / "project with spaces"
    root.mkdir()
    (root / "main.py").write_text("import sys; print('hello', *sys.argv[1:])\n", encoding="utf-8")
    initialize(root, python=sys.executable)
    return root


def test_registration_is_idempotent(project):
    first = load(project)
    initialize(project)
    assert load(project) == first
    assert len(catalog()["projects"]) == 1
    assert resolve_project(first["name"]) == project


def test_copy_has_own_instance(project):
    duplicate = project.parent / "copy"
    shutil.copytree(project, duplicate)
    initialize(duplicate)
    assert load(duplicate)["id"] == load(project)["id"]
    assert load(duplicate)["instance_id"] != load(project)["instance_id"]


def test_detect_multiple_languages(project):
    (project / "package.json").write_text("{}")
    (project / "Cargo.toml").write_text("")
    assert set(detect(project)) == {"python", "javascript", "rust"}


def test_unknown_project_never_falls_back(project):
    with pytest.raises(DockError):
        resolve_project("nonexistent")


def test_custom_start_becomes_default(project):
    config = load(project)
    config["default_action"] = ""
    write_json(project / ".project/project.json", config)
    (project / ".project/recipes/start.json").unlink()
    save_recipe(project, "start", [sys.executable, "-c", "pass"])
    assert load(project)["default_action"] == "start"


def test_profile_args_and_replacement(project):
    write_json(project / ".project/profiles/demo.json", {"environment": {"HELLO": "world"}, "args": {"start": ["one", "two"]}})
    result = plan(project, profile_name="demo", extra=["three"])
    assert result["command"][-3:] == ["one", "two", "three"]
    assert result["environment"]["HELLO"] == "world"
    replaced = plan(project, profile_name="demo", extra=["three"], replace_args=True)
    assert replaced["command"][-1:] == ["three"]
    assert "one" not in replaced["command"]


def test_trust_and_changes(project):
    with pytest.raises(DockError, match="Configuración"):
        run(project)
    grant_trust(project)
    lines = []
    assert run(project, extra=["space argument"], output=lines.append) == 0
    assert "hello space argument" in lines
    profile = project / ".project/profiles/development.json"
    write_json(profile, {"environment": {"NEW": "value"}})
    with pytest.raises(DockError, match="Configuración"):
        run(project)


def test_tool_scope_and_disable(project):
    with pytest.raises(DockError, match="compatible"):
        enable_tool(project, "cargo")
    enable_tool(project, "pytest")
    assert "test" in recipes(project)
    enable_tool(project, "pytest", False)
    with pytest.raises(DockError, match="deshabilitada"):
        plan(project, "test")


def test_timeout_records_failure(project):
    save_recipe(project, "slow", [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.3)
    grant_trust(project)
    assert run(project, "slow", output=lambda _: None) == 124
    records = [read_json(p) for p in (project / ".project/logs").glob("*.json")]
    assert records[-1]["status"] == "FAILED"
    assert records[-1]["reason"] == "timeout"


def test_cancellation(project):
    save_recipe(project, "slow", [sys.executable, "-c", "import time; time.sleep(30)"])
    grant_trust(project)
    event = threading.Event()
    timer = threading.Timer(0.3, event.set)
    timer.start()
    assert run(project, "slow", cancel=event, output=lambda _: None) == 130
    timer.join()


def test_groups_and_cycles(project):
    save_recipe(project, "fail", [sys.executable, "-c", "raise SystemExit(7)"])
    save_recipe(project, "sequence", [], steps=["fail", "start"])
    save_recipe(project, "cycle", [], steps=["cycle"])
    grant_trust(project)
    assert run(project, "sequence") == 7
    with pytest.raises(DockError, match="circular"):
        run(project, "cycle")


def test_secrets_not_logged_or_in_plan(project, monkeypatch):
    monkeypatch.setenv("PROJECTDOCK_SECRET_TOKEN", "private-value-123")
    save_recipe(project, "secret-test", [sys.executable, "-c", "import sys; print(sys.argv[1])", "{secret:TOKEN}"])
    grant_trust(project)
    assert "private-value-123" not in json.dumps(public_plan(plan(project, "secret-test")))
    lines = []
    assert run(project, "secret-test", output=lines.append) == 0
    assert lines == ["***"]
    assert all("private-value-123" not in p.read_text() for p in (project / ".project/logs").glob("*"))


def test_typed_options_conflict(project):
    save_recipe(project, "flags", [sys.executable, "-c", "pass"], options={
        "fast": {"type": "boolean", "default": True, "conflicts": ["safe"]},
        "safe": {"type": "boolean", "default": True}})
    with pytest.raises(DockError, match="incompatible"):
        plan(project, "flags")


def test_lua_rule(project):
    rule = project / ".project/rules/args.lua"
    rule.write_text('local a = context.args; table.insert(a, "from-lua"); return a', encoding="utf-8")
    save_recipe(project, "lua-test", [sys.executable, "-c", "import sys; print(sys.argv[1])"], lua="rules/args.lua")
    grant_trust(project)
    lines = []
    assert run(project, "lua-test", output=lines.append) == 0
    assert lines == ["from-lua"]


def test_typed_cli_option_overrides_without_duplication(project):
    save_recipe(project, "serve", [sys.executable, "-c", "pass"],
                options={"port": {"type": "integer", "default": 8000}})
    result = plan(project, "serve", extra=["--port", "9000"])
    assert result["command"].count("--port") == 1
    assert result["command"][-2:] == ["--port", "9000"]
    with pytest.raises(DockError, match="entero"):
        plan(project, "serve", extra=["--port", "no"])


def test_parallel_failure_cancels_other_processes(project):
    save_recipe(project, "long", [sys.executable, "-c", "import time; time.sleep(30)"])
    save_recipe(project, "fail-fast", [sys.executable, "-c", "raise SystemExit(7)"])
    save_recipe(project, "group", [], steps=["long", "fail-fast"], mode="parallel")
    grant_trust(project)
    started = time.monotonic()
    assert run(project, "group") != 0
    assert time.monotonic() - started < 10


def test_lua_has_no_os_access(project):
    (project / ".project/rules/blocked.lua").write_text('return {os.getenv("USER")}')
    save_recipe(project, "blocked", [sys.executable, "-c", "pass"], lua="rules/blocked.lua")
    grant_trust(project)
    with pytest.raises(DockError, match="Lua"):
        plan(project, "blocked", apply_rules=True)


def test_lua_timeout(project):
    (project / ".project/rules/loop.lua").write_text("while true do end")
    save_recipe(project, "loop", [sys.executable, "-c", "pass"], lua="rules/loop.lua")
    grant_trust(project)
    with pytest.raises(DockError, match="3 segundos"):
        plan(project, "loop", apply_rules=True)


def test_catalog_copy_keeps_original(project, monkeypatch):
    original = Path(os.environ["PROJECTDOCK_CATALOG"])
    monkeypatch.delenv("PROJECTDOCK_CATALOG")
    from projectdock.storage import settings_path
    write_json(settings_path(), {"catalog": str(original)})
    destination = project.parent / "new/projects.db"
    change_catalog(destination, copy_current=True)
    assert original.read_bytes() == destination.read_bytes()
    assert len(catalog()["projects"]) == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows CMD adapter")
def test_cmd_paths_with_spaces(project):
    script = project / "echo args.cmd"
    script.write_text("@echo off\necho %~1\n", encoding="utf-8")
    save_recipe(project, "batch", [str(script), "two words"])
    grant_trust(project)
    output = []
    assert run(project, "batch", output=output.append) == 0
    assert output == ["two words"]
