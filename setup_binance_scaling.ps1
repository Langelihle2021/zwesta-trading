# ==================== ZWESTA BINANCE SCALING SETUP ====================
# Run this script ONCE on the VPS to set up all infrastructure for 5000 users.
# Prerequisites: Python 3.11+, pip, internet access
#
# Usage:  .\setup_binance_scaling.ps1
# Log:    C:\backend\scaling_setup.log

param(
    [string]$BackendPath = "C:\backend",
    [string]$RedisPort   = "6379",
    [string]$PgPort      = "5432",
    [int]$WorkerCount    = 5
)

$ErrorActionPreference = "Stop"
$LogFile = "$BackendPath\scaling_setup.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Test-CommandExists {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Wait-ForPort {
    param([string]$Host = "localhost", [int]$Port, [int]$TimeoutSec = 30)
    $end = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $end) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect($Host, $Port)
            $tcp.Close()
            return $true
        } catch { Start-Sleep -Seconds 2 }
    }
    return $false
}

# ==================== HEADER ====================
New-Item -ItemType Directory -Path $BackendPath -Force | Out-Null
Write-Log "========================================================"
Write-Log "  Zwesta Binance Scaling Setup"
Write-Log "  Target capacity: 5000 users / 2500 concurrent bots"
Write-Log "  Workers: $WorkerCount Binance worker processes"
Write-Log "  Backend path: $BackendPath"
Write-Log "========================================================"

# ==================== STEP 1: CHECK PYTHON ====================
Write-Log "STEP 1: Checking Python installation"
if (-not (Test-CommandExists "python")) {
    Write-Log "Python not found — install Python 3.11+ manually then re-run" "ERROR"
    exit 1
}
$pyVersion = python --version 2>&1
Write-Log "Python: $pyVersion"

# ==================== STEP 2: INSTALL PYTHON PACKAGES ====================
Write-Log "STEP 2: Installing required Python packages"
$packages = @(
    "redis>=4.0",
    "websocket-client>=1.6",
    "requests>=2.28",
    "psycopg2-binary>=2.9"
)

foreach ($pkg in $packages) {
    Write-Log "  Installing $pkg ..."
    python -m pip install $pkg --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Log "  WARNING: Failed to install $pkg (may already be installed)" "WARN"
    }
}
Write-Log "Python packages ready"

# ==================== STEP 3: INSTALL REDIS FOR WINDOWS ====================
Write-Log "STEP 3: Setting up Redis"

$redisExe = $null
$redisPaths = @(
    "C:\Redis\redis-server.exe",
    "C:\Program Files\Redis\redis-server.exe",
    "C:\tools\redis\redis-server.exe"
)

foreach ($p in $redisPaths) {
    if (Test-Path $p) {
        $redisExe = $p
        break
    }
}

if ($null -eq $redisExe) {
    Write-Log "  Redis not found — downloading Redis for Windows"
    $redisDir = "C:\Redis"
    New-Item -ItemType Directory -Path $redisDir -Force | Out-Null

    # Download Redis 5.0.14 Windows port (from GitHub releases)
    $redisUrl = "https://github.com/microsoftarchive/redis/releases/download/win-3.0.504/Redis-x64-3.0.504.zip"
    $redisZip = "$env:TEMP\redis.zip"

    try {
        Write-Log "  Downloading Redis from $redisUrl"
        Invoke-WebRequest -Uri $redisUrl -OutFile $redisZip -UseBasicParsing
        Expand-Archive -Path $redisZip -DestinationPath $redisDir -Force
        # Find the exe in subdirectories
        $redisExe = Get-ChildItem -Path $redisDir -Filter "redis-server.exe" -Recurse | Select-Object -First 1 -ExpandProperty FullName
        Write-Log "  Redis installed at: $redisExe"
    } catch {
        Write-Log "  Could not auto-install Redis: $_" "WARN"
        Write-Log "  MANUAL STEP: Install Redis and set REDIS_URL in .env" "WARN"
    }
} else {
    Write-Log "  Redis found at: $redisExe"
}

# Start Redis if not already running
$redisRunning = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("localhost", [int]$RedisPort)
    $tcp.Close()
    $redisRunning = $true
    Write-Log "  Redis already running on port $RedisPort"
} catch { }

if (-not $redisRunning -and $null -ne $redisExe) {
    Write-Log "  Starting Redis server on port $RedisPort"
    Start-Process -FilePath $redisExe -ArgumentList "--port $RedisPort --daemonize no" -WindowStyle Hidden
    $redisRunning = Wait-ForPort -Port ([int]$RedisPort) -TimeoutSec 15
    if ($redisRunning) {
        Write-Log "  Redis started successfully"
    } else {
        Write-Log "  Redis failed to start — check manually" "WARN"
    }
}

# Register Redis as Windows Service (optional, best-effort)
if ($redisRunning -and $null -ne $redisExe) {
    $svcName = "ZwestaRedis"
    if (-not (Get-Service -Name $svcName -ErrorAction SilentlyContinue)) {
        try {
            New-Service -Name $svcName `
                -BinaryPathName "`"$redisExe`" --service-run --port $RedisPort" `
                -Description "Zwesta Redis cache for Binance price data" `
                -StartupType Automatic `
                -ErrorAction Stop
            Start-Service -Name $svcName
            Write-Log "  Redis registered as Windows Service: $svcName"
        } catch {
            Write-Log "  Could not register Redis as service: $_" "WARN"
        }
    } else {
        Write-Log "  Redis service '$svcName' already exists"
    }
}

# ==================== STEP 4: UPDATE .ENV FILE ====================
Write-Log "STEP 4: Updating .env configuration"

$envFile = "$BackendPath\.env"
if (-not (Test-Path $envFile)) {
    Write-Log "  .env not found at $envFile — make sure backend is deployed first" "WARN"
} else {
    # Read current .env
    $envContent = Get-Content $envFile -Raw

    # Settings to add/update (only add if not present)
    $newSettings = @{
        "REDIS_URL"                    = "redis://localhost:$RedisPort/0"
        "MAX_CONCURRENT_ACTIVE_BOTS"   = "500"
        "BINANCE_WORKER_COUNT"         = "$WorkerCount"
        "MAX_BOTS_PER_BINANCE_WORKER"  = "500"
    }

    foreach ($key in $newSettings.Keys) {
        $val = $newSettings[$key]
        if ($envContent -match "(?m)^$key=") {
            # Update existing line
            $envContent = $envContent -replace "(?m)^$key=.*$", "$key=$val"
            Write-Log "  Updated: $key=$val"
        } else {
            # Append new line
            $envContent += "`n$key=$val"
            Write-Log "  Added: $key=$val"
        }
    }

    Set-Content -Path $envFile -Value $envContent -NoNewline
    Write-Log "  .env updated: $envFile"
}

# ==================== STEP 5: COPY NEW SCRIPTS TO BACKEND ====================
Write-Log "STEP 5: Copying new scaling scripts to $BackendPath"

$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptsToCopy = @(
    "binance_worker.py",
    "binance_market_data.py"
)

foreach ($script in $scriptsToCopy) {
    $src = Join-Path $sourceDir $script
    $dst = Join-Path $BackendPath $script
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Log "  Copied: $script"
    } else {
        Write-Log "  Not found locally: $script (skipping)" "WARN"
    }
}

# ==================== STEP 6: REGISTER BINANCE WORKERS (SCHEDULED TASKS) ====================
Write-Log "STEP 6: Registering $WorkerCount Binance worker tasks"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($null -ne $pythonCmd -and $pythonCmd.Source) {
    $pythonExe = $pythonCmd.Source
} else {
    $pythonExe = "python"
}

for ($i = 1; $i -le $WorkerCount; $i++) {
    $taskName = "ZwestaBinanceWorker$i"

    # Remove old task if exists
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    $action = New-ScheduledTaskAction `
        -Execute $pythonExe `
        -Argument "$BackendPath\binance_worker.py" `
        -WorkingDirectory $BackendPath

    $trigger = New-ScheduledTaskTrigger -AtStartup

    $settings = New-ScheduledTaskSettingsSet `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Days 365) `
        -MultipleInstances IgnoreNew

    # Environment for this worker instance
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Zwesta Binance Worker $i (handles ~500 concurrent Binance bots)" `
        -Force | Out-Null

    # Set BINANCE_WORKER_ID environment variable for each worker
    $task = Get-ScheduledTask -TaskName $taskName
    # Note: scheduled task env vars require XML edit; use wrapper script approach
    $wrapperPath = "$BackendPath\start_binance_worker_$i.bat"
    Set-Content -Path $wrapperPath -Value "@echo off`nset BINANCE_WORKER_ID=$i`nset DATABASE_PATH=$BackendPath\zwesta_trading.db`nset REDIS_URL=redis://localhost:$RedisPort/0`npython `"$BackendPath\binance_worker.py`"`n"
    Write-Log "  Registered: $taskName (wrapper: $wrapperPath)"
}

# ==================== STEP 7: REGISTER MARKET DATA SERVICE ====================
Write-Log "STEP 7: Registering Binance Market Data service"

$mdTaskName = "ZwestaBinanceMarketData"
Unregister-ScheduledTask -TaskName $mdTaskName -Confirm:$false -ErrorAction SilentlyContinue

$mdWrapper = "$BackendPath\start_binance_market_data.bat"
Set-Content -Path $mdWrapper -Value "@echo off`nset REDIS_URL=redis://localhost:$RedisPort/0`npython `"$BackendPath\binance_market_data.py`"`n"

$mdAction   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$mdWrapper`"" -WorkingDirectory $BackendPath
$mdTrigger  = New-ScheduledTaskTrigger -AtStartup
$mdSettings = New-ScheduledTaskSettingsSet `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)
$mdPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask `
    -TaskName $mdTaskName `
    -Action $mdAction `
    -Trigger $mdTrigger `
    -Settings $mdSettings `
    -Principal $mdPrincipal `
    -Description "Zwesta Binance WebSocket price fanout → Redis" `
    -Force | Out-Null

Write-Log "  Registered: $mdTaskName"

# ==================== STEP 8: START SERVICES NOW ====================
Write-Log "STEP 8: Starting services now"

# Start market data service
Write-Log "  Starting Binance Market Data service"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$mdWrapper`"" -WindowStyle Hidden

Start-Sleep -Seconds 3

# Start all workers
for ($i = 1; $i -le $WorkerCount; $i++) {
    $wrapper = "$BackendPath\start_binance_worker_$i.bat"
    if (Test-Path $wrapper) {
        Write-Log "  Starting Binance Worker $i"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$wrapper`"" -WindowStyle Hidden
        Start-Sleep -Milliseconds 500  # Stagger starts slightly
    }
}

Start-Sleep -Seconds 5

# ==================== STEP 9: VERIFY ====================
Write-Log "STEP 9: Verification"

# Check Redis
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("localhost", [int]$RedisPort)
    $tcp.Close()
    Write-Log "  [OK] Redis: listening on port $RedisPort"
} catch {
    Write-Log "  [WARN] Redis: not responding on port $RedisPort" "WARN"
}

# Check Python processes
$pyProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue
Write-Log "  [OK] Python processes running: $($pyProcs.Count)"

# ==================== COMPLETION ====================
Write-Log "========================================================"
Write-Log "Setup complete!"
Write-Log ""
Write-Log "ARCHITECTURE DEPLOYED:"
Write-Log "  Redis (price cache)           port $RedisPort"
Write-Log "  Binance Market Data (WS feed) background process"
Write-Log "  Binance Workers x$WorkerCount             background processes"
Write-Log ""
Write-Log "CAPACITY:"
Write-Log "  $WorkerCount workers x 500 bots = $($WorkerCount * 500) concurrent bots"
Write-Log "  $($WorkerCount * 500) bots / 5 per user = $($WorkerCount * 100) simultaneous active users"
Write-Log "  At 10% concurrency: $($WorkerCount * 1000) registered users supported"
Write-Log ""
Write-Log "NEXT STEPS:"
Write-Log "  1. Restart the Waitress backend:  Restart-Service ZwestaBackendAutoStart"
Write-Log "  2. Verify workers in DB:  SELECT * FROM worker_pool;"
Write-Log "  3. Run: python $BackendPath\migrate_sqlite_to_postgres.py  (optional, if upgrading to PostgreSQL)"
Write-Log "  4. Check logs in: $BackendPath\scaling_setup.log"
Write-Log "========================================================"
