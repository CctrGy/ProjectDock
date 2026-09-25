[CmdletBinding()]
param([string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $match = [regex]::Match((Get-Content src\projectdock\__init__.py -Raw), '__version__ = "(\d+\.\d+\.\d+)"')
    if (-not $match.Success) { throw 'Versión no válida' }
    $version = $match.Groups[1].Value
    $builtVersion = (& .\dist\ProjectDock\ProjectDock.exe --version).Trim()
    if ($LASTEXITCODE -ne 0 -or $builtVersion -ne $version) { throw 'El ejecutable no coincide con el código' }
    if (-not $Compiler) {
        $candidates = @(
            (Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Inno Setup 6\ISCC.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
        )
        $Compiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $Compiler) { throw 'No se encuentra Inno Setup 6; indica -Compiler RUTA.' }
    & $Compiler "/DAppVersion=$version" packaging\ProjectDock.iss
    if ($LASTEXITCODE -ne 0) { throw 'Falló el compilador del instalador' }
    $release = Join-Path $root 'dist\release'
    $zipName = "ProjectDock-$version-windows-x64-portable.zip"
    Compress-Archive -Path dist\ProjectDock\* -DestinationPath (Join-Path $release $zipName) -Force
    Copy-Item -LiteralPath install.ps1 -Destination (Join-Path $release 'install.ps1') -Force
    $names = @("ProjectDock-$version-windows-x64-setup.exe", $zipName, 'install.ps1')
    $lines = foreach ($name in $names) {
        $hash = (Get-FileHash -LiteralPath (Join-Path $release $name) -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $name"
    }
    [IO.File]::WriteAllLines((Join-Path $release 'SHA256SUMS.txt'), $lines, [Text.UTF8Encoding]::new($false))
    Write-Host "Release $version preparada en $release"
} finally { Pop-Location }
