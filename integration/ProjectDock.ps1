# Dot-source: . 'C:\ruta\ProjectDock\integration\ProjectDock.ps1'
# PROJECTDOCK_EXE permite elegir la distribución antes de cargar la integración.
if (-not $env:PROJECTDOCK_EXE) {
    $installed = Join-Path $PSScriptRoot '..\ProjectDock.exe'
    $env:PROJECTDOCK_EXE = if (Test-Path -LiteralPath $installed) {
        $installed
    } else {
        Join-Path $PSScriptRoot '..\dist\ProjectDock\ProjectDock.exe'
    }
}
function global:projectdock {
    if ($args.Count -ge 2 -and $args[0] -eq 'cd') {
        $target = & $env:PROJECTDOCK_EXE path $args[1]
        if ($LASTEXITCODE -eq 0) { Set-Location -LiteralPath $target }
    } else {
        & $env:PROJECTDOCK_EXE @args
    }
}
function global:run {
    $candidate = Join-Path (Get-Location).Path 'run.exe'
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw 'No existe run.exe en el directorio actual.'
    }
    & $candidate @args
}
