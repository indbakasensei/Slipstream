<#
.SYNOPSIS
    Clean, build, and package a versioned Slipstream release archive.

.DESCRIPTION
    Runs clean.ps1 then build.ps1, then zips the resulting dist\Slipstream\
    folder into release\Slipstream-v<version>-win64.zip, where <version>
    is read from cfdauto.__version__ (the single authoritative source) —
    never hand-typed, so the archive name can never drift from the app's
    own reported version.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File build\release.ps1
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepoRoot
try {
    & (Join-Path $PSScriptRoot "clean.ps1")
    & (Join-Path $PSScriptRoot "build.ps1")

    $Version = (python -c "from cfdauto import __version__; print(__version__)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Version) { throw "Could not read cfdauto.__version__" }

    $ReleaseDir = Join-Path $RepoRoot "release"
    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
    $ZipPath = Join-Path $ReleaseDir "Slipstream-v$Version-win64.zip"

    Write-Host "== Packaging $ZipPath ==" -ForegroundColor Cyan
    Compress-Archive -Path (Join-Path $RepoRoot "dist\Slipstream\*") `
        -DestinationPath $ZipPath -Force

    Write-Host ""
    Write-Host "Release archive ready: $ZipPath" -ForegroundColor Green
}
finally {
    Pop-Location
}
