# start_all.ps1

$ErrorActionPreference = "Stop"

Write-Host "Starting Crime Intelligence Platform Locally..." -ForegroundColor Cyan

# Define the 10 backend services and their ports
$Services = @(
    @{ Name = "auth-service"; Port = 8020 },
    @{ Name = "conversational-interface"; Port = 8022 },
    @{ Name = "crime-forecasting"; Port = 8014 },
    @{ Name = "explainable-ai"; Port = 8021 },
    @{ Name = "financial-crime-analysis"; Port = 8013 },
    @{ Name = "investigator-decision-support"; Port = 8018 },
    @{ Name = "network-analysis"; Port = 8010 },
    @{ Name = "offender-profiling"; Port = 8016 },
    @{ Name = "pattern-analytics"; Port = 8011 },
    @{ Name = "sociological-insights"; Port = 8012 }
)

$Pids = @()

foreach ($Service in $Services) {
    $Name = $Service.Name
    $Port = $Service.Port
    $ServiceDir = "backend\services\$Name"
    
    Write-Host "Starting $Name on port $Port..." -ForegroundColor Yellow
    
    # Check if .venv exists
    if (-not (Test-Path "$ServiceDir\.venv")) {
        Write-Host "Virtual environment not found for $Name. Creating one..." -ForegroundColor DarkGray
        Start-Process -NoNewWindow -Wait -FilePath "python" -ArgumentList "-m venv $ServiceDir\.venv"
        Write-Host "Installing dependencies for $Name..." -ForegroundColor DarkGray
        Start-Process -NoNewWindow -Wait -FilePath "$ServiceDir\.venv\Scripts\pip" -ArgumentList "install -r $ServiceDir\requirements.txt"
    }

    # Start the service in the background using start-process with its own window
    # so they don't block the powershell script
    $Process = Start-Process -PassThru -FilePath "$ServiceDir\.venv\Scripts\python" -ArgumentList "-m uvicorn app.main:app --port $Port" -WorkingDirectory $ServiceDir -WindowStyle Minimized
    $Pids += $Process.Id
}

Write-Host "All backend services started." -ForegroundColor Green
Write-Host "Starting Frontend (React/Vite)..." -ForegroundColor Cyan

Set-Location -Path "frontend\web-app"

# Start Frontend
$FrontendProcess = Start-Process -PassThru -FilePath "npm" -ArgumentList "run dev" -WindowStyle Normal
$Pids += $FrontendProcess.Id

Write-Host "Frontend is running! Check http://localhost:5173" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop all services and close the windows." -ForegroundColor Red

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "Stopping all services..." -ForegroundColor Yellow
    foreach ($pid_val in $Pids) {
        Stop-Process -Id $pid_val -Force -ErrorAction SilentlyContinue
    }
}
