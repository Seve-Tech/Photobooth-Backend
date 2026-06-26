# PowerShell script to build the Photobooth executables

$BackendDir = Split-Path $PSScriptRoot -Parent
Push-Location $BackendDir

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Building Photobooth Executables" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Ensure virtual environment is activated
if ($null -eq $env:VIRTUAL_ENV) {
    if (Test-Path ".\.venv\Scripts\Activate.ps1") {
        Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
        . .\.venv\Scripts\Activate.ps1
    } else {
        Write-Warning "[-] Virtual environment not found in .\.venv. Proceeding with system Python..."
    }
}

# Ensure PyInstaller is installed
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "[*] PyInstaller not found. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Build the Arduino bridge
Write-Host "`n[*] Building bill-acceptor.exe..." -ForegroundColor Yellow
pyinstaller --onefile --name bill-acceptor arduino_bridge.py

# Build the FastAPI backend
Write-Host "`n[*] Building paywall-server.exe..." -ForegroundColor Yellow
pyinstaller --onefile --name paywall-server main.py

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "[+] Build complete!" -ForegroundColor Green
Write-Host "Executables are located in: $BackendDir\dist\" -ForegroundColor Green
Write-Host " - dist\bill-acceptor.exe" -ForegroundColor Green
Write-Host " - dist\paywall-server.exe" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green

Pop-Location
