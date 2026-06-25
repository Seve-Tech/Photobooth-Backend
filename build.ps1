# PowerShell script to build the Photobooth executables

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
Write-Host "`n[*] Building arduino-bridge.exe..." -ForegroundColor Yellow
pyinstaller --clean --noconfirm arduino-bridge.spec

# Build the FastAPI backend
Write-Host "`n[*] Building photobooth-backend.exe..." -ForegroundColor Yellow
pyinstaller --clean --noconfirm main.spec

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "[+] Build complete!" -ForegroundColor Green
Write-Host "Executables are located in: $(Get-Location)\dist\" -ForegroundColor Green
Write-Host " - dist\arduino-bridge.exe" -ForegroundColor Green
Write-Host " - dist\photobooth-backend.exe" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
