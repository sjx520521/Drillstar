$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ProjectRoot)
$PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"
$ReleaseDir = Join-Path $ProjectRoot "release"
$FinalAppDir = Join-Path $ReleaseDir "DrillStar"
$ZipPath = Join-Path $ReleaseDir "DrillStar_release.zip"
$VenvCfg = Join-Path $ProjectRoot "venv\pyvenv.cfg"

if (-not (Test-Path $PythonExe)) {
    throw "Python interpreter not found: $PythonExe"
}

Remove-Item -LiteralPath $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $DistDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $FinalAppDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

Push-Location $ProjectRoot
try {
    & $PythonExe -m PyInstaller --noconfirm --clean "DrillStar.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE"
    }

    Copy-Item -LiteralPath (Join-Path $DistDir "DrillStar") -Destination $FinalAppDir -Recurse -Force
    if (Test-Path $VenvCfg) {
        $BaseHomeLine = Get-Content $VenvCfg | Where-Object { $_ -like "home = *" } | Select-Object -First 1
        if ($BaseHomeLine) {
            $BaseHome = $BaseHomeLine.Substring(7)
            $DllSourceDir = Join-Path $BaseHome "Library\bin"
            foreach ($DllName in @("ffi.dll", "libexpat.dll")) {
                $DllSource = Join-Path $DllSourceDir $DllName
                if (Test-Path $DllSource) {
                    Copy-Item -LiteralPath $DllSource -Destination (Join-Path $FinalAppDir $DllName) -Force
                }
            }
        }
    }

    $docChinese = Join-Path $ProjectRoot "softdoc\DrillStar软著说明书.docx"
    $docEnglish = Join-Path $ProjectRoot "softdoc\DrillStar_SoftDoc.docx"

    if (Test-Path $docChinese) {
        Copy-Item -LiteralPath $docChinese -Destination (Join-Path $FinalAppDir "DrillStar软著说明书.docx") -Force
    }
    elseif (Test-Path $docEnglish) {
        Copy-Item -LiteralPath $docEnglish -Destination (Join-Path $FinalAppDir "DrillStar_SoftDoc.docx") -Force
    }

    Compress-Archive -LiteralPath $FinalAppDir -DestinationPath $ZipPath -Force

    Write-Output "APP_DIR=$FinalAppDir"
    Write-Output "ZIP_FILE=$ZipPath"
}
finally {
    Pop-Location
}
