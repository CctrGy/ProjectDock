import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from projectdock import validation
from projectdock.engine import grant_trust, plan, public_plan, run
from projectdock.project import generate_launcher, initialize, load, recipes, save_recipe
from projectdock.storage import DockError, catalog, catalog_path, change_catalog, read_json, write_json


@pytest.mark.parametrize("payload", [[], None, {"command": "python"}, {"command": ["python"], "timeout": -1},
    {"command": ["python"], "args": "oops"}, {"steps": []}, {"steps": ["start"], "mode": "typo"},
    {"command": ["python"], "environment": {"BAD=KEY": "x"}},
    {"command": ["python"], "options": {"a": {"flag": "-x"}, "b": {"flag": "-x"}}}])
def test_bad_recipe_is_rejected_before_execution(project, payload):
    write_json(project / ".project/recipes/bad.json", payload)
    with pytest.raises(DockError):
        recipes(project)


def test_bad_profile_is_diagnostic(project):
    write_json(project / ".project/profiles/development.json", [])
    with pytest.raises(DockError, match="Perfil"):
        plan(project)


def test_broken_catalog_is_diagnostic(project):
    write_json(catalog_path(), {"schema": 1, "projects": [{}]})
    with pytest.raises(DockError, match="catálogo"):
        catalog()


def test_env_catalog_override_is_not_silently_ignored(project):
    with pytest.raises(DockError, match="PROJECTDOCK_CATALOG"):
        change_catalog(project / "another.db")


def test_moved_project_reuses_registry_entry(project):
    instance = load(project)["instance_id"]
    moved = project.with_name("renamed")
    project.rename(moved)
    initialize(moved)
    assert len(catalog()["projects"]) == 1
    assert catalog()["projects"][0]["instance_id"] == instance
    assert catalog()["projects"][0]["path"] == str(moved)


def test_eof_does_not_disable_timeout(project):
    save_recipe(project, "closed-output", [sys.executable, "-c",
        "import os,time; os.close(1); os.close(2); time.sleep(30)"], timeout=0.3)
    grant_trust(project)
    started = time.monotonic()
    assert run(project, "closed-output") == 124
    assert time.monotonic() - started < 5


def test_cancelled_group_does_not_start_anything(project):
    output = []
    grant_trust(project)
    cancelled = threading.Event()
    cancelled.set()
    assert run(project, cancel=cancelled, output=output.append) == 130
    assert output == []
    assert not list((project / ".project/state").glob("*.json"))


def test_missing_group_step_has_no_partial_effects(project):
    marker = project / "should-not-exist"
    save_recipe(project, "write-marker", [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])
    save_recipe(project, "group", [], steps=["write-marker", "missing"])
    grant_trust(project)
    with pytest.raises(DockError, match="missing"):
        run(project, "group")
    assert not marker.exists()


def test_secret_with_json_escapes_is_redacted(project, monkeypatch):
    secret = 'pass"word\\ñ'
    monkeypatch.setenv("PROJECTDOCK_SECRET_TOKEN", secret)
    save_recipe(project, "secret-json", [sys.executable, "-c", "pass", "{secret:TOKEN}"])
    result = public_plan(plan(project, "secret-json"))
    assert result["command"][-1] == "***"


def test_log_is_byte_limited_and_valid_utf8(project):
    config = load(project)
    config["logs"]["max_bytes_per_run"] = 1001
    write_json(project / ".project/project.json", config)
    save_recipe(project, "noisy", [sys.executable, "-c", "print('ñ'*10000)"],
                environment={"PYTHONIOENCODING": "utf-8"})
    grant_trust(project)
    assert run(project, "noisy", output=lambda _: None) == 0
    path = next((project / ".project/logs").glob("*.log"))
    assert path.stat().st_size <= 1001
    assert path.read_text(encoding="utf-8") == "ñ" * 500


def test_secret_crossing_reader_boundary_is_hidden(project, monkeypatch):
    secret = "do-not-expose-this"
    monkeypatch.setenv("PROJECTDOCK_SECRET_TOKEN", secret)
    save_recipe(project, "split-secret", [sys.executable, "-c",
        "import sys; print('x'*8185 + sys.argv[1])", "{secret:TOKEN}"])
    grant_trust(project)
    assert run(project, "split-secret", output=lambda _: None) == 0
    log = next((project / ".project/logs").glob("*.log")).read_text()
    assert secret not in log
    assert log == "x" * 8185 + "***\n"


def test_callback_error_records_failure(project):
    def fail(_):
        raise RuntimeError("callback failed")
    grant_trust(project)
    with pytest.raises(DockError, match="callback failed"):
        run(project, output=fail)
    record = read_json(next((project / ".project/logs").glob("*.json")))
    assert record["status"] == "FAILED"


def fake_distribution(tmp_path):
    source = tmp_path / "fake-distribution"
    source.mkdir()
    (source / "ProjectDock.exe").write_bytes(b"engine-v1")
    (source / "Launcher.exe").write_bytes(b"launcher-v1")
    (source / "_internal").mkdir()
    (source / "_internal/data").write_bytes(b"data-v1")
    return source


def test_launcher_copy_failure_preserves_working_runtime(project, tmp_path, monkeypatch):
    source = fake_distribution(tmp_path)
    generate_launcher(project, source)
    (source / "ProjectDock.exe").write_bytes(b"engine-v2")
    import projectdock.project as module
    copy2 = module.shutil.copy2
    def fail(source_path, target, *args, **kwargs):
        if Path(source_path).name == "Launcher.exe":
            raise OSError("simulated disk failure")
        return copy2(source_path, target, *args, **kwargs)
    monkeypatch.setattr(module.shutil, "copy2", fail)
    with pytest.raises(OSError, match="disk"):
        generate_launcher(project, source)
    assert (project / ".project/runtime/ProjectDock.exe").read_bytes() == b"engine-v1"
    assert (project / "run.exe").read_bytes() == b"launcher-v1"


def test_launcher_rolls_back_metadata_failure(project, tmp_path, monkeypatch):
    source = fake_distribution(tmp_path)
    generate_launcher(project, source)
    original = (project / ".project/project.json").read_bytes()
    (source / "ProjectDock.exe").write_bytes(b"engine-v2")
    import projectdock.project as module
    original_write = module.write_json
    failed = False
    def write(path, value):
        nonlocal failed
        if path.name == "launcher.json" and not failed:
            failed = True
            raise OSError("metadata failure")
        return original_write(path, value)
    monkeypatch.setattr(module, "write_json", write)
    with pytest.raises(OSError, match="metadata"):
        generate_launcher(project, source)
    assert (project / ".project/runtime/ProjectDock.exe").read_bytes() == b"engine-v1"
    assert (project / ".project/project.json").read_bytes() == original


def test_launcher_does_not_replace_unknown_binary(project, tmp_path):
    source = fake_distribution(tmp_path)
    generate_launcher(project, source)
    (project / "run.exe").write_bytes(b"someone else's program")
    with pytest.raises(DockError, match="fuera"):
        generate_launcher(project, source)


def test_json_nan_rejected(project):
    path = project / "bad.json"
    path.write_text('{"value": NaN}')
    with pytest.raises(DockError):
        read_json(path)


def test_invalid_editor_project_can_be_validated_without_writing(project):
    before = (project / ".project/project.json").read_bytes()
    with pytest.raises(DockError):
        validation.project({"schema": 1})
    assert (project / ".project/project.json").read_bytes() == before
