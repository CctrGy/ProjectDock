[CmdletBinding()]
param([string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\ProjectDock'))
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'dist\ProjectDock'
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'ProjectDock.exe')) {
    $source = $PSScriptRoot
}
if (-not (Test-Path -LiteralPath (Join-Path $source 'ProjectDock.exe'))) {
    throw 'Compila primero con build.ps1.'
}
$destinationPath = [IO.Path]::GetFullPath($Destination)
if ($destinationPath -eq [IO.Path]::GetFullPath($source)) { throw 'Origen y destino coinciden.' }
if ($destinationPath.StartsWith([IO.Path]::GetFullPath($source).TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'El destino no puede estar dentro del origen.'
}
New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $destinationPath -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'integration') -Destination $destinationPath -Recurse -Force
$shell = New-Object -ComObject WScript.Shell
$linkPath = Join-Path ([Environment]::GetFolderPath('Programs')) 'ProjectDock.lnk'
$shortcut = $shell.CreateShortcut($linkPath)
$shortcut.TargetPath = Join-Path $destinationPath 'ProjectDock.exe'
$shortcut.WorkingDirectory = $destinationPath
$shortcut.Arguments = '--gui'
$shortcut.Save()
Write-Host "Instalado en $destinationPath. Acceso creado en el menú Inicio."
