#Requires -Version 7
# build_windows.ps1 — Build a self-contained Windows distribution for hash-turbo.
#
# Produces:
#   dist\hash-turbo\                     — unified onedir bundle (CLI + GUI)
#   dist\hash-turbo-<version>-windows.msi    — distributable MSI installer
#
# Requirements:
#   pip install pyinstaller
#   dotnet tool install --global wix          (WiX Toolset v4)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# ── Verify required tools ──────────────────────────────────────────────────────
foreach ($tool in @('pyinstaller', 'wix')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "Required tool '$tool' not found. See script header for install instructions."
        exit 1
    }
}

# ── Read version ───────────────────────────────────────────────────────────────
$initFile = 'src\hash_turbo\__init__.py'
$match = Select-String -Path $initFile -Pattern '__version__\s*=\s*[''"]([^''"]+)[''"]'
if (-not $match) {
    Write-Error "Could not read __version__ from $initFile"
    exit 1
}
$VERSION = $match.Matches[0].Groups[1].Value
Write-Host "Building hash-turbo $VERSION for Windows ..."

# ── Build with PyInstaller ─────────────────────────────────────────────────────
pyinstaller hash-turbo.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed"; exit 1 }
Write-Host "  PyInstaller build complete."

# ── Build MSI with WiX ────────────────────────────────────────────────────────
$AppDir   = (Resolve-Path "dist\hash-turbo").Path
$IconFile  = (Resolve-Path "assets\icon.ico").Path
$MsiOut   = "dist\hash-turbo-$VERSION-windows.msi"

wix build installer\hash-turbo.wxs `
    -d Version=$VERSION `
    -d AppDir=$AppDir `
    -d IconFile=$IconFile `
    -out $MsiOut

if ($LASTEXITCODE -ne 0) { Write-Error "WiX build failed"; exit 1 }

Write-Host ""
Write-Host "Done! Artifacts:"
Write-Host "  dist\hash-turbo\"
Write-Host "  $MsiOut"
