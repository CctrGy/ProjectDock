import sys

import pytest

from projectdock.project import initialize


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTDOCK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PROJECTDOCK_CATALOG", str(tmp_path / "registry/projects.db"))
    root = tmp_path / "project with spaces"
    root.mkdir()
    (root / "main.py").write_text("import sys; print('hello', *sys.argv[1:])\n", encoding="utf-8")
    initialize(root, python=sys.executable)
    return root
