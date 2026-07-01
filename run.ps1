Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  What model does my API key support (wmd-my-API-ks)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
try {
    $pythonVersion = python --version
    Write-Host "[INFO] Found $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python was not found in your system PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.8+ and ensure it is added to your environment variables." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Create venv if not exists
if (-not (Test-Path -Path ".venv")) {
    Write-Host "[INFO] Virtual environment (.venv) not found. Creating it..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "[INFO] Virtual environment created successfully." -ForegroundColor Green
}

# Activate and install dependencies
Write-Host "[INFO] Activating virtual environment and updating dependencies..." -ForegroundColor Yellow
& .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install dependencies." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Run app
Write-Host "[INFO] Launching TUI Application..." -ForegroundColor Green
Write-Host ""
python app.py
Write-Host ""
Write-Host "[INFO] Application exited." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
