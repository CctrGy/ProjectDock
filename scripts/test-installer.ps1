[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$workspace = Join-Path $root ('work\installer-test-' + [guid]::NewGuid().ToString('N'))
$destination = Join-Path $workspace 'Program Files'
$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$uninstallerKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{D0C70C9F-7882-49D3-83F3-929EA0645173}_is1'
if (Test-Path $uninstallerKey) {
    throw 'Ya hay una instalación registrada: usa un equipo de pruebas para no alterarla.'
}
New-Item -ItemType Directory -Path $workspace -Force | Out-Null
$originalPath = [Environment]::GetEnvironmentVariable('Path', 'User')
try {
    $options = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/SP-', '/NORESTART', '/NOICONS', '/TASKS="addtopath"', ('/DIR="' + $destination + '"'))
    $setup = Start-Process -FilePath $installerPath -ArgumentList $options -Wait -PassThru -WindowStyle Hidden
    if ($setup.ExitCode -ne 0) { throw "Setup falló: $($setup.ExitCode)" }
    $exe = Join-Path $destination 'ProjectDock.exe'
    & $exe --version
    if ($LASTEXITCODE -ne 0) { throw 'El ejecutable instalado no funciona' }
    $pathAfter = [Environment]::GetEnvironmentVariable('Path', 'User') -split ';'
    if ($pathAfter -notcontains $destination) { throw 'No se añadió PATH' }
    $sentinel = Join-Path $workspace 'projects.db'
    [IO.File]::WriteAllText($sentinel, '{"preserve":true}')
    $second = Start-Process -FilePath $installerPath -ArgumentList $options -Wait -PassThru -WindowStyle Hidden
    if ($second.ExitCode -ne 0) { throw 'Falló reinstalar/actualizar' }
    if (@(([Environment]::GetEnvironmentVariable('Path', 'User') -split ';') | Where-Object { $_ -eq $destination }).Count -ne 1) {
        throw 'PATH duplicado después de actualizar'
    }
    $uninstaller = Join-Path $destination 'unins000.exe'
    $remove = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru -WindowStyle Hidden
    if ($remove.ExitCode -ne 0) { throw 'Falló desinstalar' }
    if (Test-Path -LiteralPath $exe) { throw 'No se eliminó el ejecutable instalado' }
    if ((Get-Content -LiteralPath $sentinel -Raw) -ne '{"preserve":true}') { throw 'Se alteró el catálogo externo' }
    if ([Environment]::GetEnvironmentVariable('Path', 'User') -ne $originalPath) { throw 'No se restauró correctamente PATH' }
    Write-Host 'Instalación, actualización, PATH, desinstalación y conservación de datos: OK'
} finally {
    # No se borra recursivamente: conservar evidencias de una posible instalación fallida.
    Write-Host "Evidencias de prueba: $workspace"
}
