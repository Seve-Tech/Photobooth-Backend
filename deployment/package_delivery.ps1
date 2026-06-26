# -----------------------------------------------------------------------------
# PHOTOBOOTH USB DELIVERY PACKAGE BUILDER
# -----------------------------------------------------------------------------
param([switch]$SkipBuild)

$ErrorActionPreference = "Stop"
$DeploymentDir = $PSScriptRoot
$BackendDir = Split-Path $DeploymentDir -Parent
$ProjectRoot = Split-Path $BackendDir -Parent
$DeliveryDir = Join-Path $ProjectRoot "magnified-memories"
$FrontendUnpacked = Join-Path $ProjectRoot "frontend\dist-app\win-unpacked"
$FrontendExeName = "Paywall dslrBooth.exe"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Building Photobooth Delivery Package" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

if (-not $SkipBuild) {
    Write-Host "`n[*] Building backend executables..." -ForegroundColor Yellow
    & "$DeploymentDir\build.ps1"
} else {
    Write-Host "`n[*] Skipping build (-SkipBuild)." -ForegroundColor Gray
}

$missing = @()
$backendExe = Join-Path $BackendDir "dist\paywall-server.exe"
$bridgeExe = Join-Path $BackendDir "dist\bill-acceptor.exe"
$envFile = Join-Path $BackendDir ".env"
$pgInstaller = Get-ChildItem -Path $DeploymentDir -Filter "postgresql-*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
$frontendExe = Join-Path $FrontendUnpacked $FrontendExeName

if (-not (Test-Path $backendExe)) { $missing += "dist\paywall-server.exe" }
if (-not (Test-Path $bridgeExe)) { $missing += "dist\bill-acceptor.exe" }
if (-not (Test-Path $envFile)) { $missing += ".env in backend\ (copy .env.example and configure)" }
if (-not $pgInstaller) { $missing += "postgresql-*.exe in backend\deployment\" }
if (-not (Test-Path $frontendExe)) { $missing += "frontend\dist-app\win-unpacked\$FrontendExeName" }
if (-not (Test-Path "$DeploymentDir\setup_tasks.ps1")) { $missing += "deployment\setup_tasks.ps1" }
if (-not (Test-Path "$DeploymentDir\start_photobooth.ps1")) { $missing += "deployment\start_photobooth.ps1" }
if (-not (Test-Path "$DeploymentDir\run_backend.ps1")) { $missing += "deployment\run_backend.ps1" }
if (-not (Test-Path "$DeploymentDir\run_bridge.ps1")) { $missing += "deployment\run_bridge.ps1" }
if (-not (Test-Path "$DeploymentDir\INSTALL.bat")) { $missing += "deployment\INSTALL.bat" }

if ($missing.Count -gt 0) {
    Write-Host "`n[-] Missing required files:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    exit 1
}

Write-Host "`n[*] Creating delivery folder: $DeliveryDir" -ForegroundColor Yellow
if (Test-Path $DeliveryDir) { Remove-Item $DeliveryDir -Recurse -Force }
New-Item -Path $DeliveryDir -ItemType Directory | Out-Null

Copy-Item $backendExe -Destination "$DeliveryDir\paywall-server.exe"
Copy-Item $bridgeExe -Destination "$DeliveryDir\bill-acceptor.exe"
Copy-Item $envFile -Destination "$DeliveryDir\.env"
Copy-Item $pgInstaller.FullName -Destination "$DeliveryDir\$($pgInstaller.Name)"
Copy-Item "$DeploymentDir\setup_tasks.ps1" -Destination "$DeliveryDir\setup_tasks.ps1"
Copy-Item "$DeploymentDir\start_photobooth.ps1" -Destination "$DeliveryDir\start_photobooth.ps1"
Copy-Item "$DeploymentDir\run_backend.ps1" -Destination "$DeliveryDir\run_backend.ps1"
Copy-Item "$DeploymentDir\run_bridge.ps1" -Destination "$DeliveryDir\run_bridge.ps1"
Copy-Item "$DeploymentDir\INSTALL.bat" -Destination "$DeliveryDir\INSTALL.bat"

$frontendDest = Join-Path $DeliveryDir "frontend-app"
New-Item -Path $frontendDest -ItemType Directory | Out-Null
Copy-Item -Path "$FrontendUnpacked\*" -Destination $frontendDest -Recurse -Force

$sizeMb = [math]::Round((Get-ChildItem $DeliveryDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
$fileCount = (Get-ChildItem $DeliveryDir -Recurse -File).Count

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "[+] Delivery package ready!" -ForegroundColor Green
Write-Host "Location:  $DeliveryDir"
Write-Host "Size:      ~${sizeMb} MB ($fileCount files)"
Write-Host "=========================================" -ForegroundColor Green
