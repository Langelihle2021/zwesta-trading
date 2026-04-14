$BackendUrl = 'http://127.0.0.1:9000'
$BrokerName = 'Binance'
$DefaultZwestaPassword = 'Zwesta1985'
$PythonCmd = 'python'

$Users = @(
    @{
        Email = 'client1@example.com'
        Name = 'Client 1'
        UserPassword = $DefaultZwestaPassword
        ApiKey = '<SET_BINANCE_API_KEY>'
        ApiSecret = '<SET_BINANCE_API_SECRET>'
        Market = 'spot'
        Live = $true
        AccountNumber = 'SPOT'
    },
    @{
        Email = 'client2@example.com'
        Name = 'Client 2'
        UserPassword = $DefaultZwestaPassword
        ApiKey = '<SET_BINANCE_API_KEY>'
        ApiSecret = '<SET_BINANCE_API_SECRET>'
        Market = 'spot'
        Live = $true
        AccountNumber = 'SPOT'
    }
)

function Test-PlaceholderValue {
    param(
        [string]$Value
    )

    return [string]::IsNullOrWhiteSpace($Value) -or $Value.StartsWith('<SET_')
}

foreach ($User in $Users) {
    if (Test-PlaceholderValue $User.UserPassword) {
        Write-Warning ("Skipping {0} because the Zwesta password is not set." -f $User.Email)
        continue
    }

    $Args = @(
        '.\create_backend_test_user.py',
        '--backend-url', $BackendUrl,
        '--email', $User.Email,
        '--name', $User.Name,
        '--user-password', $User.UserPassword,
        '--broker-name', $BrokerName
    )

    if (-not (Test-PlaceholderValue $User.ApiKey) -and -not (Test-PlaceholderValue $User.ApiSecret)) {
        $Args += @(
            '--api-key', $User.ApiKey,
            '--api-secret', $User.ApiSecret,
            '--market', $User.Market,
            '--account-number', $User.AccountNumber
        )

        if ($User.Live) {
            $Args += '--live'
        }
    } else {
        Write-Host ("Creating Zwesta user only for {0}; Binance API credentials not filled yet." -f $User.Email) -ForegroundColor Yellow
    }

    Write-Host ("Onboarding Binance user {0}" -f $User.Email) -ForegroundColor Green
    & $PythonCmd @Args

    if ($LASTEXITCODE -ne 0) {
        Write-Error ("Binance onboarding failed for {0}" -f $User.Email)
        exit $LASTEXITCODE
    }
}

Write-Host 'Binance user onboarding completed.' -ForegroundColor Green