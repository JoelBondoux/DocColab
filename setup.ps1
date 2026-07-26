[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VirtualEnvironment = Join-Path $ProjectRoot ".venv"
$VirtualPython = Join-Path $VirtualEnvironment "Scripts\python.exe"

Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath $VirtualPython -PathType Leaf)) {
    $Launcher = Get-Command "py" -ErrorAction SilentlyContinue
    if (-not $Launcher) {
        $Launcher = Get-Command "python" -ErrorAction SilentlyContinue
    }
    if (-not $Launcher) {
        throw "Python 3.11 or later was not found. Install Python, then run setup.ps1 again."
    }
    Write-Host "Creating Python virtual environment..."
    & $Launcher.Source -m venv $VirtualEnvironment
}

if (-not $SkipInstall) {
    Write-Host "Installing DocColab and its dependencies..."
    & $VirtualPython -m pip install -e $ProjectRoot
}

Write-Host "Starting the DocColab guided setup..."
if ($OutputDirectory) {
    & $VirtualPython -m agent.setup_wizard --output-dir $OutputDirectory
}
else {
    & $VirtualPython -m agent.setup_wizard
}
exit $LASTEXITCODE
