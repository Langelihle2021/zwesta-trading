$BackendUrl = 'http://127.0.0.1:9000'
$Server = 'Exness-Real'
$BrokerName = 'Exness'
$PythonCmd = 'python'
$DefaultZwestaPassword = 'Zwesta1985'

$Users = @(
    @{
        Email = 'billionaire.mogul@yahoo.com'
        Name = 'Billionaire Mogul'
        UserPassword = $DefaultZwestaPassword
        Mt5Account = '<SET_MT5_ACCOUNT>'
        Mt5Password = '<SET_MT5_PASSWORD>'
        TerminalPath = 'C:\MT5\Exness-Live\User1\terminal64.exe'
    },
    @{
        Email = 'lisabelezandala@gmail.com'
        Name = 'Lisabelezandala'
        UserPassword = $DefaultZwestaPassword
        Mt5Account = '<SET_MT5_ACCOUNT>'
        Mt5Password = '<SET_MT5_PASSWORD>'
        TerminalPath = 'C:\MT5\Exness-Live\User2\terminal64.exe'
    },
    @{
        Email = 'bongiwemcimeli@yahoo.com'
        Name = 'Bongiwe Mcimeli'
        UserPassword = $DefaultZwestaPassword
        Mt5Account = '<SET_MT5_ACCOUNT>'
        Mt5Password = '<SET_MT5_PASSWORD>'
        TerminalPath = 'C:\MT5\Exness-Live\User3\terminal64.exe'
    }
)

$ReservedExtras = @(
    'C:\MT5\Exness-Live\User4\terminal64.exe',
    'C:\MT5\Exness-Live\User5\terminal64.exe',
    'C:\MT5\Exness-Live\User6\terminal64.exe',
    'C:\MT5\Exness-Live\User7\terminal64.exe',
    'C:\MT5\Exness-Live\User8\terminal64.exe',
    'C:\MT5\Exness-Live\User9\terminal64.exe',
    'C:\MT5\Exness-Live\User10\terminal64.exe'
)

function Test-PlaceholderValue {
    param(
        [string]$Value
    )

    return [string]::IsNullOrWhiteSpace($Value) -or $Value.StartsWith('<SET_')
}

Write-Host 'Configured live users:' -ForegroundColor Cyan
$Users | ForEach-Object {
    Write-Host (" - {0} -> {1}" -f $_.Email, $_.TerminalPath)
}

Write-Host 'Reserved extra terminals:' -ForegroundColor DarkCyan
$ReservedExtras | ForEach-Object {
    Write-Host (" - {0}" -f $_)
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
        '--user-password', $User.UserPassword
    )

    $HasMt5Credentials = -not (Test-PlaceholderValue $User.Mt5Account) -and -not (Test-PlaceholderValue $User.Mt5Password)

    if ($HasMt5Credentials) {
        if (-not (Test-Path $User.TerminalPath)) {
            Write-Warning ("Skipping MT5 linking for {0} because terminal path was not found: {1}" -f $User.Email, $User.TerminalPath)
        } else {
            $Args += @(
                '--broker-name', $BrokerName,
                '--mt5-account', $User.Mt5Account,
                '--mt5-password', $User.Mt5Password,
                '--server', $Server,
                '--live',
                '--mt5-terminal-path', $User.TerminalPath
            )
        }
    } else {
        Write-Host ("Creating Zwesta user only for {0}; MT5 credentials not filled yet." -f $User.Email) -ForegroundColor Yellow
    }

    Write-Host ("Onboarding {0} with terminal {1}" -f $User.Email, $User.TerminalPath) -ForegroundColor Green
    & $PythonCmd @Args

    if ($LASTEXITCODE -ne 0) {
        Write-Error ("Onboarding failed for {0}" -f $User.Email)
        exit $LASTEXITCODE
    }
}

Write-Host 'Live user onboarding completed.' -ForegroundColor Green