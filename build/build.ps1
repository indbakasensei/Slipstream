<#
.SYNOPSIS
    Build a standalone Slipstream Windows executable (one-folder) via
    PyInstaller.

.DESCRIPTION
    Prerequisites (see build/README.md for details):
      - A Python 3.11/3.12 virtual environment, activated
      - pip install -r requirements.txt -r requirements-gui.txt -r requirements-build.txt

    Runtime behavior is unchanged by packaging — this only wraps the
    existing gui_main.py entry point.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File build\build.ps1
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepoRoot
try {
    Write-Host "== Generating Windows version resource from cfdauto.__version__ ==" -ForegroundColor Cyan
    python build\make_version_info.py
    if ($LASTEXITCODE -ne 0) { throw "make_version_info.py failed" }

    Write-Host "== Running PyInstaller (one-folder build) ==" -ForegroundColor Cyan
    pyinstaller build\slipstream.spec `
        --distpath dist `
        --workpath .pyinstaller_cache `
        --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

    Write-Host ""
    Write-Host "Build complete: dist\Slipstream\Slipstream.exe" -ForegroundColor Green
}
finally {
    Pop-Location
}
