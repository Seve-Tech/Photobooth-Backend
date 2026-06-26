# -----------------------------------------------------------------------------
# PHOTOBOTH DEPLOYMENT & SETUP SCRIPT
# -----------------------------------------------------------------------------
# INSTRUCTIONS:
# 1. Edit backend\.env on your dev machine before running package_delivery.ps1.
# 2. Place this script, postgresql-*.exe, paywall-server.exe,
#    bill-acceptor.exe, .env, and the frontend-app\ folder in one directory.
# 3. Copy the folder to the client's Mini PC.
# 4. Double-click INSTALL.bat on the client's Mini PC (or run this script as Administrator).
# -----------------------------------------------------------------------------

# Deployment layout — not backend config (not stored in .env)
$FRONTEND_APP_DIR = "frontend-app"
$FRONTEND_EXE     = "Paywall dslrBooth.exe"

function Read-DotEnv {
    param([string]$Path)

    $vars = @{}
    Get-Content $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }

        $eqIndex = $line.IndexOf("=")
        if ($eqIndex -lt 1) { return }

        $key = $line.Substring(0, $eqIndex).Trim()
        $value = $line.Substring($eqIndex + 1).Trim()

        if ($value.Length -ge 2) {
            $quote = $value[0]
            if (($quote -eq '"' -or $quote -eq "'") -and $value.EndsWith($quote)) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        $commentIndex = $value.IndexOf(" #")
        if ($commentIndex -ge 0) { $value = $value.Substring(0, $commentIndex).Trim() }

        $vars[$key] = $value
    }
    return $vars
}

function Get-PostgresPasswordFromDatabaseUrl {
    param([string]$DatabaseUrl)

    if ($DatabaseUrl -match '^postgresql://[^:]+:([^@]+)@') {
        return $matches[1]
    }

    throw "Could not parse PostgreSQL password from DATABASE_URL. Expected format: postgresql://user:password@host:5432/dbname"
}

Clear-Host

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "         Photobooth System Handover Setup         " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "CRITICAL: This script MUST be run as Administrator."
    Read-Host "Press Enter to exit..."
    Exit 1
}

$TargetDir = "C:\Photobooth"
$FrontendTarget = Join-Path $TargetDir $FRONTEND_APP_DIR
$FrontendExePath = Join-Path $FrontendTarget $FRONTEND_EXE
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = Get-Location }

$bundledEnv = Join-Path $ScriptDir ".env"
if (-not (Test-Path $bundledEnv)) {
    Write-Error "[-] .env not found in $ScriptDir. Run package_delivery.ps1 on your dev machine first."
    Read-Host "Press Enter to exit..."
    Exit 1
}

$EnvVars = Read-DotEnv -Path $bundledEnv
if (-not $EnvVars.ContainsKey("DATABASE_URL") -or [string]::IsNullOrWhiteSpace($EnvVars["DATABASE_URL"])) {
    Write-Error "[-] DATABASE_URL is missing or empty in $bundledEnv"
    Read-Host "Press Enter to exit..."
    Exit 1
}
$PG_PASSWORD = Get-PostgresPasswordFromDatabaseUrl -DatabaseUrl $EnvVars["DATABASE_URL"]
$PORT = if ($EnvVars.ContainsKey("PORT")) { $EnvVars["PORT"] } else { "8000" }

Write-Host "[+] Loaded configuration from .env" -ForegroundColor Green

if (-not (Test-Path $TargetDir)) {
    Write-Host "[*] Creating target directory $TargetDir..." -ForegroundColor Yellow
    New-Item -Path $TargetDir -ItemType Directory | Out-Null
}

Write-Host "[*] Copying executables to $TargetDir..." -ForegroundColor Yellow
$backendSrc = Join-Path $ScriptDir "paywall-server.exe"
$bridgeSrc = Join-Path $ScriptDir "bill-acceptor.exe"

if (Test-Path $backendSrc) {
    Copy-Item $backendSrc -Destination "$TargetDir\paywall-server.exe" -Force
    Write-Host "[+] Copied paywall-server.exe" -ForegroundColor Green
} else {
    Write-Warning "[-] paywall-server.exe not found in $ScriptDir"
}

if (Test-Path $bridgeSrc) {
    Copy-Item $bridgeSrc -Destination "$TargetDir\bill-acceptor.exe" -Force
    Write-Host "[+] Copied bill-acceptor.exe" -ForegroundColor Green
} else {
    Write-Warning "[-] bill-acceptor.exe not found in $ScriptDir"
}

$frontendSrc = Join-Path $ScriptDir $FRONTEND_APP_DIR
if (Test-Path $frontendSrc) {
    Write-Host "[*] Copying kiosk app to $FrontendTarget ..." -ForegroundColor Yellow
    if (Test-Path $FrontendTarget) { Remove-Item $FrontendTarget -Recurse -Force }
    New-Item -Path $FrontendTarget -ItemType Directory | Out-Null
    Copy-Item -Path "$frontendSrc\*" -Destination $FrontendTarget -Recurse -Force
    Write-Host "[+] Copied kiosk app to $FrontendTarget" -ForegroundColor Green
} else {
    Write-Warning "[-] '$FRONTEND_APP_DIR' folder not found."
}

$PgInstaller = Get-ChildItem -Path $ScriptDir -Filter "postgresql-*.exe" | Select-Object -First 1
if ($null -eq $PgInstaller) {
    Write-Error "[-] PostgreSQL installer not found. Place postgresql-*.exe in this folder."
    Read-Host "Press Enter to exit..."
    Exit 1
}

$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pgService) {
    Write-Host "[~] PostgreSQL already installed ($($pgService.Name)). Skipping installer." -ForegroundColor Yellow
} else {
    Write-Host "[*] Installing PostgreSQL: $($PgInstaller.Name) ..." -ForegroundColor Yellow
    $installArgs = "--mode unattended --superpassword `"$PG_PASSWORD`" --disable-components pgAdmin,stackbuilder"
    $process = Start-Process -FilePath $PgInstaller.FullName -ArgumentList $installArgs -Wait -NoNewWindow -PassThru
    if ($process.ExitCode -ne 0) {
        Write-Error "[-] PostgreSQL installation failed. Exit code: $($process.ExitCode)"
        Read-Host "Press Enter to exit..."
        Exit 1
    }
    Write-Host "[+] PostgreSQL installed successfully." -ForegroundColor Green
}

$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pgService -and $pgService.Status -ne "Running") {
    Write-Host "[*] Starting PostgreSQL service $($pgService.Name)..." -ForegroundColor Yellow
    Start-Service $pgService.Name
}

Write-Host "[*] Waiting for PostgreSQL on port 5432..." -ForegroundColor Yellow
$retries = 20
$portOpen = $false
while ($retries -gt 0 -and -not $portOpen) {
    $connection = Test-NetConnection -ComputerName "localhost" -Port 5432 -WarningAction SilentlyContinue
    if ($connection.TcpTestSucceeded) {
        $portOpen = $true
        Write-Host "[+] PostgreSQL is listening on port 5432." -ForegroundColor Green
    } else {
        $retries--
        Start-Sleep -Seconds 3
    }
}
if (-not $portOpen) {
    Write-Error "[-] Timeout waiting for PostgreSQL."
    Read-Host "Press Enter to exit..."
    Exit 1
}

Write-Host "[*] Copying bundled .env to $TargetDir\.env ..." -ForegroundColor Yellow
Copy-Item $bundledEnv -Destination "$TargetDir\.env" -Force
Write-Host "[+] Copied .env" -ForegroundColor Green

Write-Host "`n[*] Running database migrations..." -ForegroundColor Yellow
if (Test-Path "$TargetDir\paywall-server.exe") {
    Push-Location $TargetDir
    $migrateProc = Start-Process -FilePath ".\paywall-server.exe" -ArgumentList "migrate" -Wait -NoNewWindow -PassThru
    if ($migrateProc.ExitCode -eq 0) { Write-Host "[+] Database migrated." -ForegroundColor Green }
    else { Write-Warning "[-] Migration exit code: $($migrateProc.ExitCode)" }
    $seedProc = Start-Process -FilePath ".\paywall-server.exe" -ArgumentList "seed" -Wait -NoNewWindow -PassThru
    if ($seedProc.ExitCode -eq 0) { Write-Host "[+] Database seeded." -ForegroundColor Green }
    else { Write-Warning "[-] Seed exit code: $($seedProc.ExitCode)" }
    Pop-Location
}

Write-Host "`n[*] Copying helper scripts to $TargetDir..." -ForegroundColor Yellow
$helperScripts = @("run_backend.ps1", "run_bridge.ps1", "start_photobooth.ps1")
foreach ($script in $helperScripts) {
    $src = Join-Path $ScriptDir $script
    if (Test-Path $src) {
        Copy-Item $src -Destination "$TargetDir\$script" -Force
        Write-Host "[+] Copied $script" -ForegroundColor Green
    } else {
        Write-Warning "[-] $script not found in $ScriptDir"
    }
}

Write-Host "`n[*] Configuring Task Scheduler..." -ForegroundColor Yellow
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Highest

$RunnerArgs = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File'
$TaskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -MultipleInstances IgnoreNew

# At logon (primary) + at startup with StartWhenAvailable if the user is already logged in
$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn
$StartupTrigger = New-ScheduledTaskTrigger -AtStartup

$BackendRunner = Join-Path $TargetDir "run_backend.ps1"
$BackendAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "$RunnerArgs `"$BackendRunner`"" `
    -WorkingDirectory $TargetDir
Register-ScheduledTask -TaskName "Photobooth-Backend" -Action $BackendAction -Trigger @($LogonTrigger, $StartupTrigger) -Settings $TaskSettings -Principal $Principal -Force | Out-Null
Write-Host "[+] Registered Photobooth-Backend (user: $CurrentUser, triggers: logon + startup)" -ForegroundColor Green

if (Test-Path "$TargetDir\bill-acceptor.exe") {
    $BridgeRunner = Join-Path $TargetDir "run_bridge.ps1"
    $BridgeAction = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "$RunnerArgs `"$BridgeRunner`"" `
        -WorkingDirectory $TargetDir
    Register-ScheduledTask -TaskName "Photobooth-ArduinoBridge" -Action $BridgeAction -Trigger @($LogonTrigger, $StartupTrigger) -Settings $TaskSettings -Principal $Principal -Force | Out-Null
    Write-Host "[+] Registered Photobooth-ArduinoBridge (user: $CurrentUser, triggers: logon + startup)" -ForegroundColor Green
}

Write-Host "`n[*] Creating Desktop shortcut..." -ForegroundColor Yellow
if (Test-Path $FrontendExePath) {
    try {
        $WshShell = New-Object -ComObject WScript.Shell
        $ShortcutPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), "Start Photobooth.lnk")
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = $FrontendExePath
        $Shortcut.WorkingDirectory = $FrontendTarget
        $Shortcut.Save()
        Write-Host "[+] Desktop shortcut created." -ForegroundColor Green
    } catch {
        Write-Warning "[-] Failed to create shortcut: $_"
    }
}

Write-Host "`n[*] Starting services..." -ForegroundColor Yellow
if (Test-Path "$TargetDir\run_backend.ps1") {
    & "$TargetDir\run_backend.ps1"
}
if (Test-Path "$TargetDir\run_bridge.ps1") {
    & "$TargetDir\run_bridge.ps1"
}

Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "      SUCCESS! Installation & Setup Complete      " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host " Verify API: http://localhost:${PORT}/health"
Write-Host " Kiosk: Desktop shortcut or C:\Photobooth\start_photobooth.ps1 -LaunchFrontend"
Write-Host "==================================================" -ForegroundColor Green
Read-Host "Press Enter to close..."
