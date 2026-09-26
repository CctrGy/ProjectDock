[CmdletBinding()]
param([switch]$Release)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $environmentName = if ($Release) { '.release-env' } else { '.build-env' }
    $buildPython = Join-Path $PSScriptRoot "$environmentName\Scripts\python.exe"
    if (-not (Test-Path $buildPython)) {
        python -m venv $environmentName
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de compilación' }
    }
    & $buildPython -m pip install -e . -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar las dependencias' }
    & $buildPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Las pruebas han fallado' }
    & $buildPython -m PyInstaller --noconfirm --clean --onedir --name ProjectDock --icon src/projectdock/assets/projectdock.ico --add-data 'src/projectdock/assets;projectdock/assets' --paths src --collect-all lupa entrypoint.py
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación del Dock' }
    & $buildPython -m PyInstaller --noconfirm --clean --onefile --name Launcher --icon src/projectdock/assets/projectdock.ico launcher.py
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación del lanzador' }
    Copy-Item -LiteralPath 'dist\Launcher.exe' -Destination 'dist\ProjectDock\Launcher.exe' -Force
    & $buildPython -m PyInstaller --noconfirm --clean --onefile --windowed --name ProjectDockGUI --icon src/projectdock/assets/projectdock.ico gui_launcher.py
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación de la entrada gráfica' }
    Copy-Item -LiteralPath 'dist\ProjectDockGUI.exe' -Destination 'dist\ProjectDock\ProjectDockGUI.exe' -Force
    Copy-Item -LiteralPath 'README.md' -Destination 'dist\ProjectDock\README.md' -Force
    foreach ($folder in @('docs', 'integration', 'examples')) {
        Copy-Item -LiteralPath $folder -Destination 'dist\ProjectDock' -Recurse -Force
    }
    Copy-Item -LiteralPath 'install.ps1' -Destination 'dist\ProjectDock\install.ps1' -Force
    & $buildPython scripts/smoke_portable.py dist/ProjectDock/ProjectDock.exe
    if ($LASTEXITCODE -ne 0) { throw 'La prueba del portable ha fallado' }
    Write-Host 'Portable disponible en dist\ProjectDock'
} finally { Pop-Location }
