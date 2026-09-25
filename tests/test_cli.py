import sys

from projectdock.cli import main
from projectdock.project import initialize


def test_cli_full_flow(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PROJECTDOCK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PROJECTDOCK_CATALOG", str(tmp_path / "projects.db"))
    root = tmp_path / "demo"
    root.mkdir()
    (root / "main.py").write_text("print('CLI OK')")
    assert main(["register", str(root), "--python", sys.executable]) == 0
    assert main(["start", "demo"]) == 1
    assert main(["trust", "demo"]) == 0
    assert main(["start", "demo"]) == 0
    assert "CLI OK" in capsys.readouterr().out
    assert main(["info", "demo"]) == 0
    assert main(["path", "demo"]) == 0
    assert main(["cd", "demo"]) == 1


def test_cli_passthrough(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PROJECTDOCK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PROJECTDOCK_CATALOG", str(tmp_path / "projects.db"))
    (tmp_path / "main.py").write_text("import sys; print(sys.argv[1:])")
    initialize(tmp_path, python=sys.executable)
    main(["trust", str(tmp_path)])
    assert main(["start", str(tmp_path), "--", "--version", "two words"]) == 0
    assert "'--version', 'two words'" in capsys.readouterr().out
