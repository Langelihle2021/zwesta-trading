param(
    [string]$BackendPath = "C:\backend",
    [string]$RedisPort = "6379",
    [int]$WorkerCount = 5
)

$ErrorActionPreference = "Stop"
$LogFile = Join-Path $BackendPath "scaling_setup.log"

function Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Upsert-EnvValue {
    param([string]$Path, [string]$Key, [string]$Value)
    $content = ""
    if (Test-Path $Path) {
        $content = Get-Content $Path -Raw
    }

    if ($content -match "(?m)^$Key=") {
        $content = $content -replace "(?m)^$Key=.*$", "$Key=$Value"
    } else {
        if ($content.Length -gt 0 -and -not $content.EndsWith("`n")) {
            $content += "`n"
        }
        $content += "$Key=$Value`n"
    }

    Set-Content -Path $Path -Value $content
}

New-Item -ItemType Directory -Path $BackendPath -Force | Out-Null
Log "Starting Binance scaling quickfix setup"

# 1) Python packages
Log "Installing Python packages"
python -m pip install --quiet requests websocket-client redis psycopg2-binary

# 2) Update .env
$envFile = Join-Path $BackendPath ".env"
if (-not (Test-Path $envFile)) {
    New-Item -ItemType File -Path $envFile -Force | Out-Null
}

Log "Updating .env"
Upsert-EnvValue -Path $envFile -Key "REDIS_URL" -Value "redis://localhost:$RedisPort/0"
Upsert-EnvValue -Path $envFile -Key "MAX_CONCURRENT_ACTIVE_BOTS" -Value "500"
Upsert-EnvValue -Path $envFile -Key "BINANCE_WORKER_COUNT" -Value "$WorkerCount"
Upsert-EnvValue -Path $envFile -Key "MAX_BOTS_PER_BINANCE_WORKER" -Value "500"
Upsert-EnvValue -Path $envFile -Key "BINANCE_SYMBOLS" -Value "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,MATICUSDT,LINKUSDT"

# 3) Wrapper files
for ($i = 1; $i -le $WorkerCount; $i++) {
    $wrapper = Join-Path $BackendPath ("start_binance_worker_" + $i + ".bat")
    $wrapperContent = @(
        "@echo off",
        "set BINANCE_WORKER_ID=$i",
        "set DATABASE_PATH=$BackendPath\zwesta_trading.db",
        "set REDIS_URL=redis://localhost:$RedisPort/0",
        "python \"$BackendPath\binance_worker.py\""
    ) -join "`r`n"
    Set-Content -Path $wrapper -Value $wrapperContent -Encoding ASCII
}

$mdWrapper = Join-Path $BackendPath "start_binance_market_data.bat"
$mdContent = @(
    "@echo off",
    "set REDIS_URL=redis://localhost:$RedisPort/0",
    "python \"$BackendPath\binance_market_data.py\""
) -join "`r`n"
Set-Content -Path $mdWrapper -Value $mdContent -Encoding ASCII

# 4) Start processes now
Log "Starting Binance market data"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c \"$mdWrapper\"" -WindowStyle Hidden
Start-Sleep -Seconds 2

for ($i = 1; $i -le $WorkerCount; $i++) {
    $wrapper = Join-Path $BackendPath ("start_binance_worker_" + $i + ".bat")
    if (Test-Path $wrapper) {
        Log "Starting Binance worker $i"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c \"$wrapper\"" -WindowStyle Hidden
        Start-Sleep -Milliseconds 500
    }
}

# 5) Verify
Start-Sleep -Seconds 3
$py = @(Get-Process -Name python -ErrorAction SilentlyContinue)
Log ("Python processes: " + $py.Count)

Log "Quickfix setup complete"
Log "Next: restart backend service/process"
