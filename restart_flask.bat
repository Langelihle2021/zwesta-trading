@echo off
REM Quick Flask Restart Script
cd /d C:\zwesta-trader\xm_trading_system
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak
echo Starting Flask...
start /B C:\Python313\python.exe -B dashboard_enhanced.py > ..\flask.log 2>&1
timeout /t 3 /nobreak
tasklist | findstr "python" && echo Flask running! || echo Flask failed!
curl -s -I http://127.0.0.1:5000/ | findstr "200" && echo Dashboard OK! || echo Port not responding
