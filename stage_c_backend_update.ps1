param(
    [string]$SourceRoot = $PSScriptRoot,
    [string]$TargetDir = 'C:\backend',
    [switch]$AllowPartial
)

$ScriptVersion = '2026-04-14.4'

$SourceBackend = Join-Path $SourceRoot 'multi_broker_backend_updated.py'
$SourceWorkerManager = Join-Path $SourceRoot 'worker_manager.py'
$SourceRuntimeInfrastructure = Join-Path $SourceRoot 'runtime_infrastructure.py'
$SourcePostgresSchema = Join-Path $SourceRoot 'postgres_schema.py'
$SourcePostgresMigration = Join-Path $SourceRoot 'migrate_sqlite_to_postgres.py'
$SourcePostgresGuide = Join-Path $SourceRoot 'POSTGRESQL_MIGRATION_GUIDE.md'
$SourceOnboarding = Join-Path $SourceRoot 'setup_exness_live_vps_users.ps1'
$SourceBinanceOnboarding = Join-Path $SourceRoot 'setup_binance_vps_users.ps1'
$SourceUserSetup = Join-Path $SourceRoot 'create_backend_test_user.py'
$SourceBinanceBulk = Join-Path $SourceRoot 'bulk_onboard_binance_users.py'
$SourceBinanceTemplate = Join-Path $SourceRoot 'binance_users_template.csv'
$SourceBinanceWorker = Join-Path $SourceRoot 'binance_worker.py'
$SourceBinanceMarketData = Join-Path $SourceRoot 'binance_market_data.py'
$SourceBinanceScalingSetup = Join-Path $SourceRoot 'setup_binance_scaling.ps1'
$SourceDockerCompose = Join-Path $SourceRoot 'docker-compose.yml'

Write-Host "Staging backend update" -ForegroundColor Cyan
Write-Host "ScriptVersion: $ScriptVersion" -ForegroundColor Cyan
Write-Host "SourceRoot: $SourceRoot" -ForegroundColor Cyan
Write-Host "TargetDir : $TargetDir" -ForegroundColor Cyan
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
$TargetBinanceWorker = Join-Path $TargetDir 'binance_worker.py'
$TargetBinanceMarketData = Join-Path $TargetDir 'binance_market_data.py'
$TargetBinanceScalingSetup = Join-Path $TargetDir 'setup_binance_scaling.ps1'
$TargetDockerCompose = Join-Path $TargetDir 'docker-compose.yml'
$BackupDir = Join-Path $TargetDir 'zwesta-backup'

$RequiredSources = @(
    $SourceBackend,
    $SourceWorkerManager,
    $SourceRuntimeInfrastructure,
    $SourcePostgresSchema,
    $SourcePostgresMigration,
    $SourcePostgresGuide,
    $SourceOnboarding,
    $SourceBinanceOnboarding,
    $SourceUserSetup,
    $SourceBinanceBulk,
    $SourceBinanceTemplate,
    $SourceBinanceWorker,
    $SourceBinanceMarketData,
    $SourceBinanceScalingSetup,
    $SourceDockerCompose
)

foreach ($Path in $RequiredSources) {
    if (-not (Test-Path $Path)) {
        if ($AllowPartial) {
            Write-Warning "Source file not found (skipping due to -AllowPartial): $Path"
            continue
        }

        throw "Source file not found: $Path`nCheck SourceRoot: $SourceRoot`nTip: run with -AllowPartial to stage only files that exist."
    }
}

if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    Write-Warning "Target directory did not exist. Created: $TargetDir"
}

if (-not (Test-Path $TargetEnv)) {
    Write-Warning ".env not found at $TargetEnv. Confirm environment settings before restarting the backend."
}

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

if (Test-Path $TargetBackend) {
    $BackendBackup = Join-Path $BackupDir ("multi_broker_backend_updated.$Timestamp.py.bak")
    Copy-Item $TargetBackend $BackendBackup -Force
    Write-Host "Backed up C:\backend runtime backend to $BackendBackup" -ForegroundColor Yellow
}

function Copy-IfDifferent {
    param(
        [string]$Source,
        [string]$Target
    )

    if (-not (Test-Path $Source)) {
        Write-Warning "Skipping missing source: $Source"
        return 'skipped-missing'
    }

    $SourceResolved = [System.IO.Path]::GetFullPath($Source)
    $TargetResolved = [System.IO.Path]::GetFullPath($Target)

    if ($SourceResolved -ieq $TargetResolved) {
        Write-Warning "Skipping copy (same path): $SourceResolved"
        return 'skipped-same'
    }

    Copy-Item $Source $Target -Force
    return 'copied'
}

$FileMap = @(
    @{ Label = 'backend'; Source = $SourceBackend; Target = $TargetBackend },
    @{ Label = 'worker manager'; Source = $SourceWorkerManager; Target = $TargetWorkerManager },
    @{ Label = 'runtime infrastructure'; Source = $SourceRuntimeInfrastructure; Target = $TargetRuntimeInfrastructure },
    @{ Label = 'PostgreSQL schema script'; Source = $SourcePostgresSchema; Target = $TargetPostgresSchema },
    @{ Label = 'PostgreSQL migration script'; Source = $SourcePostgresMigration; Target = $TargetPostgresMigration },
    @{ Label = 'PostgreSQL guide'; Source = $SourcePostgresGuide; Target = $TargetPostgresGuide },
    @{ Label = 'Exness onboarding helper'; Source = $SourceOnboarding; Target = $TargetOnboarding },
    @{ Label = 'Binance onboarding helper'; Source = $SourceBinanceOnboarding; Target = $TargetBinanceOnboarding },
    @{ Label = 'API user setup helper'; Source = $SourceUserSetup; Target = $TargetUserSetup },
    @{ Label = 'Binance bulk importer'; Source = $SourceBinanceBulk; Target = $TargetBinanceBulk },
    @{ Label = 'Binance CSV template'; Source = $SourceBinanceTemplate; Target = $TargetBinanceTemplate },
    @{ Label = 'Binance worker process'; Source = $SourceBinanceWorker; Target = $TargetBinanceWorker },
    @{ Label = 'Binance market data service'; Source = $SourceBinanceMarketData; Target = $TargetBinanceMarketData },
    @{ Label = 'Binance scaling VPS setup script'; Source = $SourceBinanceScalingSetup; Target = $TargetBinanceScalingSetup },
    @{ Label = 'Docker compose stack'; Source = $SourceDockerCompose; Target = $TargetDockerCompose }
)

$CopiedCount = 0
$SkippedSameCount = 0
$SkippedMissingCount = 0

foreach ($Entry in $FileMap) {
    $Result = Copy-IfDifferent -Source $Entry.Source -Target $Entry.Target

    if ($Result -eq 'copied') {
        $CopiedCount++
        Write-Host "Staged $($Entry.Label) to $($Entry.Target)" -ForegroundColor Green
    } elseif ($Result -eq 'skipped-same') {
        $SkippedSameCount++
        Write-Host "Skipped $($Entry.Label) (source and target are identical): $($Entry.Target)" -ForegroundColor Yellow
    } elseif ($Result -eq 'skipped-missing') {
        $SkippedMissingCount++
        Write-Host "Skipped $($Entry.Label) (missing source): $($Entry.Source)" -ForegroundColor Yellow
    }
}

Write-Host "Summary: copied=$CopiedCount skipped-same=$SkippedSameCount skipped-missing=$SkippedMissingCount" -ForegroundColor Cyan
Write-Host "Existing environment file remains at $TargetEnv" -ForegroundColor Cyan