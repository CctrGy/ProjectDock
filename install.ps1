# Instalación remota por usuario. Windows PowerShell 5.1 o posterior.
[CmdletBinding()]
param(
    [string]$Version = 'latest',
    [string]$Destination = '',
    [switch]$Interactive,
    [switch]$NoPath,
    [switch]$NoShortcuts,
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'Este instalador requiere Windows 10/11 de 64 bits.'
}
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Se requiere Windows de 64 bits.' }
if ($Version -ne 'latest' -and $Version -notmatch '^v?\d+\.\d+\.\d+$') {
    throw 'Version debe ser latest o una versión publicada, por ejemplo 0.1.1.'
}
if ($Destination -match '["\r\n]') { throw 'Destino no válido.' }
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$repository = 'CctrGy/ProjectDock'
$headers = @{ 'User-Agent' = 'ProjectDock-Installer'; 'Accept' = 'application/vnd.github+json' }
$endpoint = if ($Version -eq 'latest') { 'latest' } else { 'tags/v' + $Version.TrimStart('v') }
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repository/releases/$endpoint" -Headers $headers
if ($release.draft -or $release.prerelease -or $release.tag_name -notmatch '^v(\d+\.\d+\.\d+)$') {
    throw 'No se ha encontrado una versión publicada de distribución general.'
}
$resolvedVersion = $Matches[1]
$fileName = "ProjectDock-$resolvedVersion-windows-x64-setup.exe"
$setupAsset = @($release.assets | Where-Object { $_.name -eq $fileName })
$hashAsset = @($release.assets | Where-Object { $_.name -eq 'SHA256SUMS.txt' })
if ($setupAsset.Count -ne 1 -or $hashAsset.Count -ne 1) {
    throw 'La versión no contiene un instalador y manifiesto de integridad completos.'
}
$prefix = "https://github.com/$repository/releases/download/$($release.tag_name)/"
foreach ($asset in @($setupAsset[0], $hashAsset[0])) {
    if (-not $asset.browser_download_url.StartsWith($prefix, [StringComparison]::Ordinal)) {
        throw 'Origen de descarga inesperado.'
    }
}
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('ProjectDock-Install-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $setupPath = Join-Path $temporary $fileName
    $hashPath = Join-Path $temporary 'SHA256SUMS.txt'
    Write-Host "Descargando ProjectDock $resolvedVersion..."
    Invoke-WebRequest -UseBasicParsing -Uri $hashAsset[0].browser_download_url -OutFile $hashPath
    Invoke-WebRequest -UseBasicParsing -Uri $setupAsset[0].browser_download_url -OutFile $setupPath
    $pattern = '^([a-fA-F0-9]{64})  ' + [regex]::Escape($fileName) + '$'
    $entries = @(Get-Content -LiteralPath $hashPath | Where-Object { $_ -match $pattern })
    if ($entries.Count -ne 1 -or $entries[0] -notmatch $pattern) { throw 'Manifiesto SHA-256 no válido.' }
    $expected = $Matches[1].ToLowerInvariant()
    $hasher = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($setupPath)
    try {
        $actual = ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $hasher.Dispose()
    }
    if ($actual -ne $expected) { throw 'El SHA-256 del instalador no coincide. No se ejecutará.' }
    if ($VerifyOnly) {
        Write-Host "Verificado: $fileName ($actual)"
        return
    }
    $setupArgs = @('/SP-', '/NORESTART')
    if (-not $Interactive) { $setupArgs += @('/VERYSILENT', '/SUPPRESSMSGBOXES') }
    if ($Destination) { $setupArgs += '/DIR="' + [IO.Path]::GetFullPath($Destination) + '"' }
    if ($NoPath) { $setupArgs += '/TASKS=""' } else { $setupArgs += '/TASKS="addtopath"' }
    if ($NoShortcuts) { $setupArgs += '/NOICONS' }
    $process = Start-Process -FilePath $setupPath -ArgumentList $setupArgs -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -notin @(0, 3010)) { throw "La instalación falló con código $($process.ExitCode)." }
    if (-not $NoPath) {
        $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        foreach ($entry in ($userPath -split ';')) {
            if ($entry -and ($env:Path -split ';') -notcontains $entry) { $env:Path += ';' + $entry }
        }
    }
    Write-Host "ProjectDock $resolvedVersion instalado. Ejecuta: projectdock"
} finally {
    $resolvedTemporary = [IO.Path]::GetFullPath($temporary)
    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($resolvedTemporary.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($resolvedTemporary).StartsWith('ProjectDock-Install-')) {
        Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
    }
}
