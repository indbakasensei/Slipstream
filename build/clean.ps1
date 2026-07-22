<#
.SYNOPSIS
    Remove all generated Slipstream packaging artifacts.

.DESCRIPTION
    Safe to run at any time. Only removes generated output (dist/,
    PyInstaller's work cache, the generated version resource, and any
    packaged release archives) — never touches anything under version
    control, including build/slipstream.spec and this script itself.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File build\clean.ps1
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$Targets = @(
    (Join-Path $RepoRoot "dist"),
    (Join-Path $RepoRoot ".pyinstaller_cache"),
    (Join-Path $RepoRoot "release"),
    (Join-Path $RepoRoot "build\version_info.txt")
)

foreach ($t in $Targets) {
    if (Test-Path $t) {
        Write-Host "Removing $t"
        Remove-Item -Recurse -Force $t
    }
}

Write-Host "Clean complete."
