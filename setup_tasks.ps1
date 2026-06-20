# -----------------------------------------------------------------------------
# PHOTOBOTH DEPLOYMENT & SETUP SCRIPT
# -----------------------------------------------------------------------------
# INSTRUCTIONS:
# 1. Edit the CONFIGURATION block below on your dev machine.
# 2. Place this script, postgresql-xx-installer.exe, photobooth-backend.exe,
#    and arduino-bridge.exe in a single folder.
# 3. Copy the folder to the client's Mini PC.
# 4. Right-click this script -> "Run with PowerShell" (as Administrator).
# -----------------------------------------------------------------------------

# --- CONFIGURATION (EDIT BEFORE DEPLOYMENT) ---
$PG_PASSWORD   = "photobooth2026"
$API_KEY       = "90a8c7f559cfce10b9dcf31e65762fd82561a6974625cf0e69f9d0e23f6c8159"
$BRANCH_ID     = 1
$UNIT_ID       = 1
$DSLR_PASSWORD = "Z-crRWyKaYgFLZyn"
$FRONTEND_URL  = "http://localhost:3000"
$PORT          = 8000
$FRONTEND_EXE  = "photobooth-frontend.exe"  # Change this to match your frontend exe filename
# ----------------------------------------------

# Clear the screen
Clear-Host

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "         Photobooth System Handover Setup         " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Ensure running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "CRITICAL: This script MUST be run as Administrator."
    Write-Host "Please close this window, right-click the script, and select 'Run as Administrator'." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    Exit
}

# 2. Create Target Directory
$TargetDir = "C:\Photobooth"
if (-not (Test-Path $TargetDir)) {
    Write-Host "[*] Creating target directory $TargetDir..." -ForegroundColor Yellow
    New-Item -Path $TargetDir -ItemType Directory | Out-Null
}

# 3. Copy Executables
Write-Host "[*] Copying executables to $TargetDir..." -ForegroundColor Yellow
if (Test-Path ".\photobooth-backend.exe") {
    Copy-Item ".\photobooth-backend.exe" -Destination "$TargetDir\photobooth-backend.exe" -Force
} else {
    Write-Warning "[-] 'photobooth-backend.exe' not found in current directory. Will skip copy."
}

if (Test-Path ".\arduino-bridge.exe") {
    Copy-Item ".\arduino-bridge.exe" -Destination "$TargetDir\arduino-bridge.exe" -Force
} elseif (Test-Path ".\dist\arduino-bridge.exe") {
    Copy-Item ".\dist\arduino-bridge.exe" -Destination "$TargetDir\arduino-bridge.exe" -Force
} else {
    Write-Warning "[-] 'arduino-bridge.exe' not found. Will skip copy."
}

if (Test-Path ".\$FRONTEND_EXE") {
    Copy-Item ".\$FRONTEND_EXE" -Destination "$TargetDir\$FRONTEND_EXE" -Force
    Write-Host "[+] Copied $FRONTEND_EXE to $TargetDir." -ForegroundColor Green
} else {
    Write-Warning "[-] '$FRONTEND_EXE' not found. Make sure to copy it to $TargetDir manually when ready."
}

# 4. Install PostgreSQL Server
$PgInstaller = Get-ChildItem -Filter "postgresql-*.exe" | Select-Object -First 1

if ($null -ne $PgInstaller) {
    # Method A: Local offline installer
    Write-Host "[*] Found local PostgreSQL installer: $($PgInstaller.Name)" -ForegroundColor Yellow
    Write-Host "[*] Installing PostgreSQL server silently (this may take a minute)..." -ForegroundColor Yellow
    
    $installArgs = "--mode unattended --superpassword `"$PG_PASSWORD`" --disable-components pgadmin,stackbuilder"
    $process = Start-Process -FilePath $PgInstaller.FullName -ArgumentList $installArgs -Wait -NoNewWindow -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Host "[+] PostgreSQL installed successfully." -ForegroundColor Green
    } else {
        Write-Error "[-] PostgreSQL installation failed. Exit code: $($process.ExitCode)"
        Read-Host "Press Enter to exit..."
        Exit
    }
} else {
    # Method B: Fallback to Winget if no local installer is found
    Write-Warning "[-] Local PostgreSQL installer not found. Attempting online installation via Winget..."
    
    $wingetArgs = "install --id PostgreSQL.PostgreSQL.16 --silent --accept-package-agreements --accept-source-agreements --override `"--superpassword $PG_PASSWORD --unattendedmodeui none --mode unattended --disable-components pgadmin,stackbuilder`""
    $process = Start-Process -FilePath "winget" -ArgumentList $wingetArgs -Wait -NoNewWindow -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Host "[+] PostgreSQL installed successfully via winget." -ForegroundColor Green
    } else {
        Write-Error "[-] Winget PostgreSQL installation failed or Winget is not installed."
        Read-Host "Press Enter to exit..."
        Exit
    }
}

# 5. Wait for PostgreSQL to start and listen on port 5432
Write-Host "[*] Waiting for PostgreSQL service to start..." -ForegroundColor Yellow
$retries = 20
$portOpen = $false
while ($retries -gt 0 -and -not $portOpen) {
    $connection = Test-NetConnection -ComputerName "localhost" -Port 5432 -WarningAction SilentlyContinue
    if ($connection.TcpTestSucceeded) {
        $portOpen = $true
        Write-Host "[+] PostgreSQL is running and listening on port 5432." -ForegroundColor Green
    } else {
        $retries--
        Write-Host "[*] Waiting for port 5432... ($retries attempts remaining)" -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }
}

if (-not $portOpen) {
    Write-Error "[-] Timeout waiting for PostgreSQL service to respond."
    Read-Host "Press Enter to exit..."
    Exit
}

# 6. Generate the .env file automatically
Write-Host "[*] Writing configuration .env file..." -ForegroundColor Yellow
$EnvContent = @"
# Generated automatically by setup_tasks.ps1 on $(Get-Date)

# ── App ──────────────────────────────────────────
DEBUG=false
HOST=0.0.0.0
PORT=$PORT

# ── Security ─────────────────────────────────────
API_KEY=$API_KEY
FRONTEND_ORIGIN=$FRONTEND_URL
WS_RATE_LIMIT=30

# ── Database ─────────────────────────────────────
DATABASE_URL=postgresql://postgres:$PG_PASSWORD@localhost:5432/photobooth_db
BRANCH_ID=$BRANCH_ID
UNIT_ID=$UNIT_ID

# ── DSLRBooth Integration ─────────────────────────
DSLRBOOTH_MOCK=false
DSLRBOOTH_HOST=http://localhost:1501
DSLRBOOTH_PASSWORD=$DSLR_PASSWORD
DSLRBOOTH_BOOTH_MODE=print
DSLRBOOTH_SESSION_TIMEOUT_S=300
DSLRBOOTH_MOCK_SESSION_DURATION_S=10
"@

$EnvContent | Out-File -FilePath "$TargetDir\.env" -Encoding utf8 -Force
Write-Host "[+] Created .env file at $TargetDir\.env" -ForegroundColor Green

# 7. Run database migration and seeding
Write-Host "`n[*] Running database migrations..." -ForegroundColor Yellow
if (Test-Path "$TargetDir\photobooth-backend.exe") {
    # Run the compiled backend with the migration CLI flag
    # We change directory to TargetDir so the exe can read the .env file locally
    Push-Location $TargetDir
    
    # Run migration
    $migrateProc = Start-Process -FilePath ".\photobooth-backend.exe" -ArgumentList "migrate" -Wait -NoNewWindow -PassThru
    if ($migrateProc.ExitCode -eq 0) {
        Write-Host "[+] Database migrated successfully." -ForegroundColor Green
    } else {
        Write-Warning "[-] Database migration exited with code: $($migrateProc.ExitCode)"
    }
    
    # Run seed
    $seedProc = Start-Process -FilePath ".\photobooth-backend.exe" -ArgumentList "seed" -Wait -NoNewWindow -PassThru
    if ($seedProc.ExitCode -eq 0) {
        Write-Host "[+] Database seeded successfully." -ForegroundColor Green
    } else {
        Write-Warning "[-] Database seeding exited with code: $($seedProc.ExitCode)"
    }
    
    Pop-Location
} else {
    Write-Warning "[-] 'photobooth-backend.exe' not found in $TargetDir. Cannot execute migrations."
}

# 8. Configure Auto-Start Tasks in Task Scheduler
Write-Host "`n[*] Configuring Windows Task Scheduler tasks..." -ForegroundColor Yellow

# Define task settings
$Principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Task 1: Photobooth Backend
$BackendAction = New-ScheduledTaskAction -Execute "$TargetDir\photobooth-backend.exe" -WorkingDirectory $TargetDir
$BackendTrigger = New-ScheduledTaskTrigger -AtStartup
$BackendSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "Photobooth-Backend" -Action $BackendAction -Trigger $BackendTrigger -Settings $BackendSettings -Principal $Principal -Force | Out-Null
Write-Host "[+] Registered task: Photobooth-Backend (Auto-starts at Windows Startup)" -ForegroundColor Green

# Task 2: Arduino Bridge
if (Test-Path "$TargetDir\arduino-bridge.exe") {
    $BridgeAction = New-ScheduledTaskAction -Execute "$TargetDir\arduino-bridge.exe" -WorkingDirectory $TargetDir
    $BridgeTrigger = New-ScheduledTaskTrigger -AtStartup
    $BridgeSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName "Photobooth-ArduinoBridge" -Action $BridgeAction -Trigger $BridgeTrigger -Settings $BridgeSettings -Principal $Principal -Force | Out-Null
    Write-Host "[+] Registered task: Photobooth-ArduinoBridge (Auto-starts at Windows Startup)" -ForegroundColor Green
} else {
    Write-Warning "[-] 'arduino-bridge.exe' not found. Startup task for bridge skipped."
}

# 9. Create Desktop Shortcut for Kiosk Frontend UI
Write-Host "`n[*] Creating Desktop shortcut for Kiosk Frontend..." -ForegroundColor Yellow
if (Test-Path "$TargetDir\$FRONTEND_EXE") {
    try {
        $WshShell = New-Object -ComObject WScript.Shell
        $ShortcutPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), "Start Photobooth.lnk")
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = "$TargetDir\$FRONTEND_EXE"
        $Shortcut.WorkingDirectory = $TargetDir
        $Shortcut.Save()
        Write-Host "[+] Desktop shortcut 'Start Photobooth' created successfully." -ForegroundColor Green
    } catch {
        Write-Warning "[-] Failed to create Desktop shortcut: $_"
    }
} else {
    Write-Warning "[-] '$FRONTEND_EXE' not found in $TargetDir. Desktop shortcut skipped."
}

# 10. Launch services now so everything is running immediately
Write-Host "`n[*] Starting Photobooth services immediately..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName "Photobooth-Backend" | Out-Null
if (Test-Path "$TargetDir\arduino-bridge.exe") {
    Start-ScheduledTask -TaskName "Photobooth-ArduinoBridge" | Out-Null
}

Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "      SUCCESS! Installation & Setup Complete      " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host " Both backend processes are running in the background."
Write-Host " They will auto-start whenever the PC turns on."
Write-Host " The frontend app can be launched via the Desktop icon."
Write-Host " Log files are generated inside C:\Photobooth\"
Write-Host "==================================================" -ForegroundColor Green

Read-Host "Press Enter to close..."
