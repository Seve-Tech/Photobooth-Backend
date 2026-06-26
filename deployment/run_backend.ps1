# Starts paywall-server.exe as a hidden background process (safe for Task Scheduler).
$TargetDir = if ($PSScriptRoot) { $PSScriptRoot } else { "C:\Photobooth" }
$ExePath = Join-Path $TargetDir "paywall-server.exe"
$ProcessName = "paywall-server"

if (-not (Test-Path $ExePath)) { exit 1 }
if (Get-Process -Name $ProcessName -ErrorAction SilentlyContinue) { exit 0 }

Start-Process -FilePath $ExePath -WorkingDirectory $TargetDir -WindowStyle Hidden | Out-Null
exit 0
