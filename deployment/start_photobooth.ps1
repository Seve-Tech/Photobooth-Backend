# -----------------------------------------------------------------------------
# PHOTOBOOTH DAILY START SCRIPT
# -----------------------------------------------------------------------------
param([switch]$LaunchFrontend)

$TargetDir = "C:\Photobooth"
$FrontendAppDir = Join-Path $TargetDir "frontend-app"
$FrontendExe = Join-Path $FrontendAppDir "Paywall dslrBooth.exe"
$EnvPath = Join-Path $TargetDir ".env"

function Write-Status {
    param([string]$Label, [bool]$Ok, [string]$Detail = "")
    $icon = if ($Ok) { "[+]" } else { "[-]" }
    $color = if ($Ok) { "Green" } else { "Red" }
    $suffix = if ($Detail) { " — $Detail" } else { "" }
    Write-Host "$icon $Label$suffix" -ForegroundColor $color
}

function Get-BackendPort {
    param([string]$Path)

    if (-not (Test-Path $Path)) { return 8000 }

    foreach ($line in Get-Content $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }

        $key, $value = $trimmed.Split("=", 2)
        if ($key.Trim() -ne "PORT") { continue }

        $value = $value.Trim()
        $commentIndex = $value.IndexOf(" #")
        if ($commentIndex -ge 0) { $value = $value.Substring(0, $commentIndex).Trim() }

        return [int]$value
    }

    return 8000
}

function Test-BackendHealth {
    param(
        [int]$Port = 8000,
        [int]$TimeoutSeconds = 3
    )

    $url = "http://127.0.0.1:$Port/health"

    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        try {
            $statusCode = & curl.exe -s -o NUL -w "%{http_code}" --max-time $TimeoutSeconds $url 2>$null
            if ($statusCode -eq "200") { return $true }
        } catch {}
    }

    try {
        $handler = [System.Net.Http.HttpClientHandler]::new()
        $handler.UseProxy = $false
        $client = [System.Net.Http.HttpClient]::new($handler)
        $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
        $response = $client.GetAsync($url).GetAwaiter().GetResult()
        $ok = $response.IsSuccessStatusCode
        $client.Dispose()
        return $ok
    } catch {
        return $false
    }
}

function Start-BackgroundService {
    param(
        [string]$RunnerScript,
        [string]$ProcessName,
        [string]$ExePath
    )

    if (Get-Process -Name $ProcessName -ErrorAction SilentlyContinue) {
        return $true
    }

    if (Test-Path $RunnerScript) {
        & $RunnerScript | Out-Null
        return $true
    }

    if (Test-Path $ExePath) {
        Start-Process -FilePath $ExePath -WorkingDirectory $TargetDir -WindowStyle Hidden | Out-Null
        return $true
    }

    return $false
}

$port = Get-BackendPort -Path $EnvPath
$HealthUrl = "http://127.0.0.1:$port/health"

Clear-Host
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "           Starting Photobooth Services           " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$pgOk = $false
$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pgService) {
    if ($pgService.Status -ne "Running") {
        try {
            Start-Service $pgService.Name -ErrorAction Stop
            Write-Host "[*] Started PostgreSQL service: $($pgService.Name)" -ForegroundColor Yellow
        } catch {
            Write-Warning "[-] Could not start PostgreSQL (Admin may be required): $_"
        }
    }
    $pgService = Get-Service -Name $pgService.Name
    $pgOk = $pgService.Status -eq "Running"
    Write-Status "PostgreSQL" $pgOk $pgService.Status
} else {
    $conn = Test-NetConnection -ComputerName "127.0.0.1" -Port 5432 -WarningAction SilentlyContinue
    $pgOk = $conn.TcpTestSucceeded
    Write-Status "PostgreSQL (port 5432)" $pgOk $(if ($pgOk) { "listening" } else { "service not found" })
}

$backendOk = Start-BackgroundService `
    -RunnerScript (Join-Path $TargetDir "run_backend.ps1") `
    -ProcessName "paywall-server" `
    -ExePath (Join-Path $TargetDir "paywall-server.exe")

if ($backendOk) {
    $detail = if (Get-Process -Name "paywall-server" -ErrorAction SilentlyContinue) { "running in background" } else { "start requested" }
    Write-Status "Photobooth-Backend" $true $detail
} else {
    Write-Status "Photobooth-Backend" $false "exe not found at $TargetDir"
}

$bridgeOk = Start-BackgroundService `
    -RunnerScript (Join-Path $TargetDir "run_bridge.ps1") `
    -ProcessName "bill-acceptor" `
    -ExePath (Join-Path $TargetDir "bill-acceptor.exe")

if ($bridgeOk) {
    $detail = if (Get-Process -Name "bill-acceptor" -ErrorAction SilentlyContinue) { "running in background" } else { "start requested" }
    Write-Status "Photobooth-ArduinoBridge" $true $detail
} else {
    Write-Status "Photobooth-ArduinoBridge" $false "skipped (exe not found)"
    $bridgeOk = $true
}

$apiOk = $false
$maxAttempts = 45
Write-Host "[*] Waiting for backend API at $HealthUrl (up to $($maxAttempts * 2)s)..." -ForegroundColor Yellow
for ($i = 1; $i -le $maxAttempts; $i++) {
    if (Test-BackendHealth -Port $port) {
        $apiOk = $true
        break
    }
    Write-Host "." -NoNewline -ForegroundColor Gray
    Start-Sleep -Seconds 2
}
Write-Host ""
Write-Status "Backend API ($HealthUrl)" $apiOk

if ($LaunchFrontend) {
    if (Test-Path $FrontendExe) {
        Start-Process -FilePath $FrontendExe -WorkingDirectory $FrontendAppDir
        Write-Status "Kiosk frontend launched" $true $FrontendExe
    } else {
        Write-Status "Kiosk frontend" $false "not found at $FrontendExe"
    }
}

Write-Host "`n==================================================" -ForegroundColor Cyan
if ($pgOk -and $apiOk) {
    Write-Host "  Photobooth is ready." -ForegroundColor Green
    if (-not $LaunchFrontend) {
        Write-Host "  Run: .\start_photobooth.ps1 -LaunchFrontend" -ForegroundColor Gray
    }
} else {
    Write-Host "  Some services failed to start." -ForegroundColor Yellow
    if (-not $apiOk) {
        Write-Host "  Tip: Open $HealthUrl in a browser to verify the backend manually." -ForegroundColor Gray
        Write-Host "  Check Task Manager for paywall-server.exe and bill-acceptor.exe." -ForegroundColor Gray
    }
}
Write-Host "==================================================" -ForegroundColor Cyan
