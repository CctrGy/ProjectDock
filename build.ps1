[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.build-env\Scripts\python.exe')) {
        python -m venv --system-site-packages .build-env
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de compilación' }
    }
    $buildPython = Join-Path $PSScriptRoot '.build-env\Scripts\python.exe'
    & $buildPython -m pip install -e . 'pyinstaller>=6,<7' pytest
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar las dependencias' }
    & $buildPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Las pruebas han fallado' }
    & $buildPython -m PyInstaller --noconfirm --clean --onedir --name ProjectDock --paths src --collect-all lupa entrypoint.py
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación del Dock' }
    & $buildPython -m PyInstaller --noconfirm --clean --onefile --name Launcher launcher.py
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación del lanzador' }
    Copy-Item -LiteralPath 'dist\Launcher.exe' -Destination 'dist\ProjectDock\Launcher.exe' -Force
    Copy-Item -LiteralPath 'README.md' -Destination 'dist\ProjectDock\README.md' -Force
    foreach ($folder in @('docs', 'integration', 'examples')) {
        Copy-Item -LiteralPath $folder -Destination 'dist\ProjectDock' -Recurse -Force
    }
    Copy-Item -LiteralPath 'install.ps1' -Destination 'dist\ProjectDock\install.ps1' -Force
    & $buildPython scripts/smoke_portable.py dist/ProjectDock/ProjectDock.exe
    if ($LASTEXITCODE -ne 0) { throw 'La prueba del portable ha fallado' }
    Write-Host 'Portable disponible en dist\ProjectDock'
} finally { Pop-Location }
