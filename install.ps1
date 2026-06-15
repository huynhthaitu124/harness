# Harness installer for Windows (PowerShell)
# Run once: .\install.ps1
# No admin required — adds scripts\ to user PATH only.

$ErrorActionPreference = "Stop"

$HarnessRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir  = Join-Path $HarnessRoot "scripts"

# Verify harness.bat exists
if (-not (Test-Path (Join-Path $ScriptsDir "harness.bat"))) {
    Write-Error "harness.bat not found in $ScriptsDir"
    exit 1
}

# Read current user PATH
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")

if ($currentPath -like "*$ScriptsDir*") {
    Write-Host "harness already on PATH: $ScriptsDir"
} else {
    $newPath = "$ScriptsDir;$currentPath"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    Write-Host "Added to user PATH: $ScriptsDir"
    Write-Host "Restart your terminal (or run: `$env:PATH = '$ScriptsDir;' + `$env:PATH)"
}

Write-Host ""
Write-Host "Usage (run from inside any project):"
Write-Host "  harness init"
Write-Host "  harness eject"
Write-Host "  harness status"
Write-Host "  harness grill"
