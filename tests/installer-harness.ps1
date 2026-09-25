param([string]$InstallerScript, [string]$Mode)
$ErrorActionPreference = 'Stop'
$global:Executed = $false
$global:TestMode = $Mode
$payload = [Text.Encoding]::UTF8.GetBytes('test setup payload')
$sha = [Security.Cryptography.SHA256]::Create()
$global:Expected = ([BitConverter]::ToString($sha.ComputeHash($payload))).Replace('-', '').ToLowerInvariant()
$sha.Dispose()
function Invoke-RestMethod {
    param($Uri, $Headers)
    $prefix = if ($global:TestMode -eq 'origin') { 'https://example.invalid/' } else { 'https://github.com/CctrGy/ProjectDock/releases/download/v0.1.1/' }
    return [pscustomobject]@{
        tag_name='v0.1.1'; draft=$false; prerelease=($global:TestMode -eq 'prerelease')
        assets=@(
            [pscustomobject]@{ name='ProjectDock-0.1.1-windows-x64-setup.exe'; browser_download_url=($prefix + 'ProjectDock-0.1.1-windows-x64-setup.exe') },
            [pscustomobject]@{ name='SHA256SUMS.txt'; browser_download_url=($prefix + 'SHA256SUMS.txt') }
        )
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, $Uri, $OutFile)
    if ($OutFile.EndsWith('.exe')) {
        [IO.File]::WriteAllText($OutFile, 'test setup payload', [Text.UTF8Encoding]::new($false))
    } else {
        $hash = if ($global:TestMode -eq 'hash') { '0' * 64 } else { $global:Expected }
        $line = "$hash  ProjectDock-0.1.1-windows-x64-setup.exe"
        if ($global:TestMode -eq 'duplicate') { $line += [Environment]::NewLine + $line }
        [IO.File]::WriteAllText($OutFile, $line, [Text.UTF8Encoding]::new($false))
    }
}
function Start-Process {
    param($FilePath, $ArgumentList, [switch]$Wait, [switch]$PassThru, $WindowStyle)
    $global:Executed = $true
    return [pscustomobject]@{ExitCode=0}
}
try {
    & $InstallerScript -Version 0.1.1 -NoPath -NoShortcuts
    if ($Mode -ne 'success' -or -not $global:Executed) { throw 'Unexpected execution outcome' }
    Write-Output 'HARNESS OK'
} catch {
    if ($Mode -eq 'success' -or $global:Executed) { throw }
    $reason = @{ hash='SHA-256'; duplicate='Manifiesto'; origin='Origen'; prerelease='publicada' }[$Mode]
    if ($_.Exception.Message -notmatch $reason) { throw }
    Write-Output ('REJECTED: ' + $_.Exception.Message)
}
