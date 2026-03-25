@echo off
REM ==================== MT5 Multi-Terminal Setup for Multi-User Trading ====================
REM This script sets up separate MT5 terminal installations in portable mode
REM so different broker accounts can run in parallel without conflicts.
REM
REM USAGE: Run as Administrator on the VPS
REM
REM Each broker gets its own MT5 folder under C:\MT5\{BrokerName}\
REM The backend auto-detects these paths via get_known_mt5_paths()
REM ========================================================================================

echo ============================================================
echo   Zwesta Trader - MT5 Multi-Terminal Setup
echo ============================================================
echo.

REM Create directory structure
echo [1/3] Creating MT5 directory structure...
if not exist "C:\MT5" mkdir "C:\MT5"
if not exist "C:\MT5\Exness" mkdir "C:\MT5\Exness"
if not exist "C:\MT5\PXBT" mkdir "C:\MT5\PXBT"
if not exist "C:\MT5\XM" mkdir "C:\MT5\XM"
echo   Created: C:\MT5\Exness\
echo   Created: C:\MT5\PXBT\
echo   Created: C:\MT5\XM\
echo.

echo [2/3] Checking for existing MT5 installations...
echo.

REM Check Exness
if exist "C:\MT5\Exness\terminal64.exe" (
    echo   [OK] Exness MT5 terminal found at C:\MT5\Exness\terminal64.exe
) else if exist "C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe" (
    echo   [OK] Exness MT5 found in Program Files
) else (
    echo   [MISSING] Exness MT5 not found
    echo   Download from: https://www.exness.com/trading-platforms/metatrader-5/
    echo   Install to: C:\MT5\Exness\
)

REM Check PXBT
if exist "C:\MT5\PXBT\terminal64.exe" (
    echo   [OK] PXBT MT5 terminal found at C:\MT5\PXBT\terminal64.exe
) else if exist "C:\Program Files\PXBT Trading MT5 Terminal\terminal64.exe" (
    echo   [OK] PXBT MT5 found in Program Files
) else (
    echo   [MISSING] PXBT MT5 not found
    echo   Download from: https://www.primexbt.com/
    echo   Install to: C:\MT5\PXBT\
)

REM Check XM
if exist "C:\MT5\XM\terminal64.exe" (
    echo   [OK] XM MT5 terminal found at C:\MT5\XM\terminal64.exe
) else if exist "C:\Program Files\MetaTrader 5 XM\terminal64.exe" (
    echo   [OK] XM MT5 found in Program Files
) else (
    echo   [MISSING] XM MT5 not found
    echo   Download from: https://www.xm.com/platforms
    echo   Install to: C:\MT5\XM\
)

echo.
echo [3/3] Configuration Summary
echo ============================================================
echo.
echo   CURRENT MODE: Single-process account switching
echo   - All bots share one MT5 process
echo   - Bots on different accounts take turns (3-5s switch)
echo   - Works for up to ~5 active accounts
echo.
echo   FUTURE MODE: Multi-process parallel (requires setup)
echo   - Each broker gets its own MT5 terminal
echo   - Install terminals to C:\MT5\{Broker}\ in portable mode
echo   - Backend auto-detects per-broker terminals
echo   - True parallel trading across all accounts
echo.
echo   .env variables (set per broker):
echo     EXNESS_PATH=C:\MT5\Exness\terminal64.exe
echo     PXBT_PATH=C:\MT5\PXBT\terminal64.exe
echo     XM_PATH=C:\MT5\XM\terminal64.exe
echo.
echo ============================================================
echo   Setup complete! Install missing MT5 terminals above.
echo ============================================================
pause
