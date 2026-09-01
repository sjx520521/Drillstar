param(
    [string]$PythonExe = ".\\venv\\Scripts\\python.exe"
)

$ErrorActionPreference = "Stop"
$PackageDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VerifiedRequirements = Join-Path $PackageDir "requirements_bundle_verified.txt"
$Requirements = Join-Path $PackageDir "requirements_doc.txt"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

if (Test-Path $VerifiedRequirements) {
    $Requirements = $VerifiedRequirements
}

if (-not (Test-Path $Requirements)) {
    throw "Requirements file not found: $Requirements"
}

& $PythonExe -m pip install --no-index --find-links $PackageDir -r $Requirements
