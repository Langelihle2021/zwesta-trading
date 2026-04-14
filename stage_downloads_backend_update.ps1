$SourceBackend = 'C:\zwesta-trader\Zwesta Flutter App\multi_broker_backend_updated.py'
$SourceOnboarding = 'C:\zwesta-trader\Zwesta Flutter App\setup_exness_live_vps_users.ps1'
$SourceBinanceOnboarding = 'C:\zwesta-trader\Zwesta Flutter App\setup_binance_vps_users.ps1'
$SourceUserSetup = 'C:\zwesta-trader\Zwesta Flutter App\create_backend_test_user.py'
$SourceBinanceBulk = 'C:\zwesta-trader\Zwesta Flutter App\bulk_onboard_binance_users.py'
$SourceBinanceTemplate = 'C:\zwesta-trader\Zwesta Flutter App\binance_users_template.csv'

$TargetDir = 'C:\Users\zwexm\Downloads'
$TargetBackend = Join-Path $TargetDir 'multi_broker_backend_updated.py'
$TargetEnv = Join-Path $TargetDir '.env'
$TargetOnboarding = Join-Path $TargetDir 'setup_exness_live_vps_users.ps1'
$TargetBinanceOnboarding = Join-Path $TargetDir 'setup_binance_vps_users.ps1'
$TargetUserSetup = Join-Path $TargetDir 'create_backend_test_user.py'
$TargetBinanceBulk = Join-Path $TargetDir 'bulk_onboard_binance_users.py'
$TargetBinanceTemplate = Join-Path $TargetDir 'binance_users_template.csv'
$BackupDir = Join-Path $TargetDir 'zwesta-backup'

if (-not (Test-Path $SourceBackend)) {
    throw "Source backend not found: $SourceBackend"
}

if (-not (Test-Path $SourceOnboarding)) {
    throw "Source onboarding script not found: $SourceOnboarding"
}

if (-not (Test-Path $SourceBinanceOnboarding)) {
    throw "Source Binance onboarding script not found: $SourceBinanceOnboarding"
}

if (-not (Test-Path $SourceUserSetup)) {
    throw "Source user setup helper not found: $SourceUserSetup"
}

if (-not (Test-Path $SourceBinanceBulk)) {
    throw "Source Binance bulk importer not found: $SourceBinanceBulk"
}

if (-not (Test-Path $SourceBinanceTemplate)) {
    throw "Source Binance CSV template not found: $SourceBinanceTemplate"
}

if (-not (Test-Path $TargetDir)) {
    throw "Target directory not found: $TargetDir"
}

if (-not (Test-Path $TargetEnv)) {
    Write-Warning ".env not found at $TargetEnv. The backend loads .env from its own folder, so confirm the target environment file exists before restart."
}

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

if (Test-Path $TargetBackend) {
    $BackendBackup = Join-Path $BackupDir ("multi_broker_backend_updated.$Timestamp.py.bak")
    Copy-Item $TargetBackend $BackendBackup -Force
    Write-Host "Backed up running backend to $BackendBackup" -ForegroundColor Yellow
}

Copy-Item $SourceBackend $TargetBackend -Force
Copy-Item $SourceOnboarding $TargetOnboarding -Force
Copy-Item $SourceBinanceOnboarding $TargetBinanceOnboarding -Force
Copy-Item $SourceUserSetup $TargetUserSetup -Force
Copy-Item $SourceBinanceBulk $TargetBinanceBulk -Force
Copy-Item $SourceBinanceTemplate $TargetBinanceTemplate -Force

Write-Host "Staged updated backend to $TargetBackend" -ForegroundColor Green
Write-Host "Staged onboarding helper to $TargetOnboarding" -ForegroundColor Green
Write-Host "Staged Binance onboarding helper to $TargetBinanceOnboarding" -ForegroundColor Green
Write-Host "Staged API user setup helper to $TargetUserSetup" -ForegroundColor Green
Write-Host "Staged Binance bulk importer to $TargetBinanceBulk" -ForegroundColor Green
Write-Host "Staged Binance CSV template to $TargetBinanceTemplate" -ForegroundColor Green
Write-Host "Environment file remains at $TargetEnv" -ForegroundColor Cyan
Write-Host 'Restart the Downloads-based backend only when you are ready to activate the new per-user terminal-path support.' -ForegroundColor Cyan