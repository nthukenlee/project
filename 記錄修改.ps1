param([string]$Message = "")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$GitCommand = Get-Command git -ErrorAction SilentlyContinue
$GitExecutable = if ($GitCommand) { $GitCommand.Source } elseif (Test-Path -LiteralPath 'C:\Program Files\Git\cmd\git.exe') { 'C:\Program Files\Git\cmd\git.exe' } else { Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd\git.exe' }
if (-not (Test-Path -LiteralPath $GitExecutable)) { throw '找不到 Git，請先安裝 Git for Windows。' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.git'))) { throw '這個資料夾尚未建立 Git 儲存庫。' }

& $GitExecutable add --all
if ($LASTEXITCODE -ne 0) { throw '無法暫存修改。' }
& $GitExecutable diff --cached --quiet
if ($LASTEXITCODE -eq 0) { Write-Host '沒有新的原始碼修改需要記錄。'; exit 0 }
if ($LASTEXITCODE -ne 1) { throw '無法檢查修改內容。' }
if ([string]::IsNullOrWhiteSpace($Message)) { $Message = '更新遊戲：' + (Get-Date -Format 'yyyy-MM-dd HH:mm') }
& $GitExecutable commit -m $Message
if ($LASTEXITCODE -ne 0) { throw '建立版本紀錄失敗。' }
& $GitExecutable log -1 --oneline
