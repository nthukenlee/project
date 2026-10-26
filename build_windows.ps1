$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputPath = Join-Path $ProjectRoot "outputs"
$DataPath = Join-Path $ProjectRoot "data"
$AssetsPath = Join-Path $ProjectRoot "assets"

Set-Location -LiteralPath $ProjectRoot
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name "NTHUWalk2D" `
  --add-data "$DataPath;data" `
  --add-data "$AssetsPath;assets" `
  --distpath $OutputPath `
  --workpath (Join-Path $ProjectRoot "work\pyinstaller") `
  --specpath (Join-Path $ProjectRoot "work") `
  main.py

if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Built: $OutputPath\NTHUWalk2D.exe"
