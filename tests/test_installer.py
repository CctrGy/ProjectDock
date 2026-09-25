import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Windows remote installer")
@pytest.mark.parametrize("mode", ["success", "hash", "duplicate", "origin", "prerelease"])
def test_remote_installer_validates_before_execution(mode):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(root / "tests/installer-harness.ps1"), "-InstallerScript",
        str(root / "install.ps1"), "-Mode", mode
    ], capture_output=True, text=True, errors="replace", timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("HARNESS OK" if mode == "success" else "REJECTED:") in result.stdout
