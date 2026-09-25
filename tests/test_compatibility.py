import os
import sys
import threading
import time

import pytest

from projectdock.engine import grant_trust, project_python, run
from projectdock.migration import preview
from projectdock.project import initialize, recipes, save_recipe
from projectdock.storage import DockError


def test_explicit_python_and_managed_environment_do_not_change_selection(project):
    suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    for directory in [".project/python", ".venv"]:
        candidate = project / directory / suffix
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(b"placeholder")
    assert project_python(project, {"python": sys.executable}) == sys.executable
    assert project_python(project, {"python": "python"}) == str(project / ".venv" / suffix)
    assert project_python(project, {"python": "{root}/chosen/python"}) == str(project) + "/chosen/python"


def test_inherited_output_is_not_captured_or_logged(project, capfd):
    save_recipe(project, "interactive-test", [sys.executable, "-c", "print('private terminal content');raise SystemExit(7)"], io="inherit")
    grant_trust(project)
    captured = []
    assert run(project, "interactive-test", output=captured.append) == 7
    assert "private terminal content" in capfd.readouterr().out
    assert captured == []
    assert all("private terminal content" not in p.read_text() for p in (project / ".project/logs").glob("*.log"))


def test_inherited_process_timeout(project):
    save_recipe(project, "interactive-timeout", [sys.executable, "-c", "import time;time.sleep(30)"], io="inherit", timeout=0.2)
    grant_trust(project)
    assert run(project, "interactive-timeout") == 124


def test_shared_resource_blocks_different_actions(project):
    ready = project / "ready"
    save_recipe(project, "builder", [sys.executable, "-c",
        "from pathlib import Path;import time;Path('ready').touch();time.sleep(30)"], resources=["build"])
    save_recipe(project, "installer", [sys.executable, "-c", "pass"], resources=["build"])
    grant_trust(project)
    cancel = threading.Event()
    worker = threading.Thread(target=run, args=(project, "builder"), kwargs={"cancel": cancel})
    worker.start()
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists()
        with pytest.raises(DockError, match="Recurso ocupado"):
            run(project, "installer")
    finally:
        cancel.set()
        worker.join(timeout=5)
    assert not worker.is_alive()


def test_lanctl_initialization_and_read_only_preview(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTDOCK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PROJECTDOCK_CATALOG", str(tmp_path / "projects.db"))
    root = tmp_path / "lanctl"
    root.mkdir()
    (root / "lanctl.py").write_text("pass")
    (root / "run.cmd").write_text("@python lanctl.py %*")
    (root / "pyproject.toml").write_text('[project.optional-dependencies]\ndev = ["pytest"]\n')
    (root / "scripts").mkdir()
    (root / "scripts/build-windows.ps1").write_text("param([switch]$AllowDirty)")
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    report = preview(root)
    assert report["read_only"] and "/.project/" in report["gitignore_suggested"]
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    initialize(root, python=sys.executable)
    configured = recipes(root)
    assert configured["start"]["io"] == "inherit"
    assert "-AllowDirty" not in configured["build"]["command"]
    assert "-AllowDirty" in configured["build-development"]["command"]
    assert configured["environment-install-dev"]["command"][-1] == "{root}[dev]"
