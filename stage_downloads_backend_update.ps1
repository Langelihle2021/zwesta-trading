$SourceBackend = 'C:\zwesta-trader\Zwesta Flutter App\multi_broker_backend_updated.py'
$SourceWorkerManager = 'C:\zwesta-trader\Zwesta Flutter App\worker_manager.py'
$SourceRuntimeInfrastructure = 'C:\zwesta-trader\Zwesta Flutter App\runtime_infrastructure.py'
$SourcePostgresSchema = 'C:\zwesta-trader\Zwesta Flutter App\postgres_schema.py'
$SourcePostgresMigration = 'C:\zwesta-trader\Zwesta Flutter App\migrate_sqlite_to_postgres.py'
$SourcePostgresGuide = 'C:\zwesta-trader\Zwesta Flutter App\POSTGRESQL_MIGRATION_GUIDE.md'
$SourceOnboarding = 'C:\zwesta-trader\Zwesta Flutter App\setup_exness_live_vps_users.ps1'
$SourceBinanceOnboarding = 'C:\zwesta-trader\Zwesta Flutter App\setup_binance_vps_users.ps1'
$SourceUserSetup = 'C:\zwesta-trader\Zwesta Flutter App\create_backend_test_user.py'
$SourceBinanceBulk = 'C:\zwesta-trader\Zwesta Flutter App\bulk_onboard_binance_users.py'
$SourceBinanceTemplate = 'C:\zwesta-trader\Zwesta Flutter App\binance_users_template.csv'

$TargetDir = 'C:\Users\zwexm\Downloads'
$TargetBackend = Join-Path $TargetDir 'multi_broker_backend_updated.py'
$TargetWorkerManager = Join-Path $TargetDir 'worker_manager.py'
$TargetRuntimeInfrastructure = Join-Path $TargetDir 'runtime_infrastructure.py'
$TargetPostgresSchema = Join-Path $TargetDir 'postgres_schema.py'
$TargetPostgresMigration = Join-Path $TargetDir 'migrate_sqlite_to_postgres.py'
$TargetPostgresGuide = Join-Path $TargetDir 'POSTGRESQL_MIGRATION_GUIDE.md'
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

if (-not (Test-Path $SourceWorkerManager)) {
    throw "Source worker manager not found: $SourceWorkerManager"
}

if (-not (Test-Path $SourceRuntimeInfrastructure)) {
    throw "Source runtime infrastructure module not found: $SourceRuntimeInfrastructure"
}

if (-not (Test-Path $SourcePostgresSchema)) {
    throw "Source PostgreSQL schema script not found: $SourcePostgresSchema"
}

if (-not (Test-Path $SourcePostgresMigration)) {
    throw "Source PostgreSQL migration script not found: $SourcePostgresMigration"
}

if (-not (Test-Path $SourcePostgresGuide)) {
    throw "Source PostgreSQL migration guide not found: $SourcePostgresGuide"
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
Copy-Item $SourceWorkerManager $TargetWorkerManager -Force
Copy-Item $SourceRuntimeInfrastructure $TargetRuntimeInfrastructure -Force
Copy-Item $SourcePostgresSchema $TargetPostgresSchema -Force
Copy-Item $SourcePostgresMigration $TargetPostgresMigration -Force
Copy-Item $SourcePostgresGuide $TargetPostgresGuide -Force
Copy-Item $SourceOnboarding $TargetOnboarding -Force
Copy-Item $SourceBinanceOnboarding $TargetBinanceOnboarding -Force
Copy-Item $SourceUserSetup $TargetUserSetup -Force
Copy-Item $SourceBinanceBulk $TargetBinanceBulk -Force
Copy-Item $SourceBinanceTemplate $TargetBinanceTemplate -Force

Write-Host "Staged updated backend to $TargetBackend" -ForegroundColor Green
Write-Host "Staged worker manager to $TargetWorkerManager" -ForegroundColor Green
Write-Host "Staged runtime infrastructure module to $TargetRuntimeInfrastructure" -ForegroundColor Green
Write-Host "Staged PostgreSQL schema script to $TargetPostgresSchema" -ForegroundColor Green
Write-Host "Staged PostgreSQL migration script to $TargetPostgresMigration" -ForegroundColor Green
Write-Host "Staged PostgreSQL migration guide to $TargetPostgresGuide" -ForegroundColor Green
Write-Host "Staged onboarding helper to $TargetOnboarding" -ForegroundColor Green
Write-Host "Staged Binance onboarding helper to $TargetBinanceOnboarding" -ForegroundColor Green
Write-Host "Staged API user setup helper to $TargetUserSetup" -ForegroundColor Green
Write-Host "Staged Binance bulk importer to $TargetBinanceBulk" -ForegroundColor Green
Write-Host "Staged Binance CSV template to $TargetBinanceTemplate" -ForegroundColor Green
Write-Host "Environment file remains at $TargetEnv" -ForegroundColor Cyan
Write-Host 'Restart the Downloads-based backend only when you are ready to activate the new per-user terminal-path support.' -ForegroundColor Cyan