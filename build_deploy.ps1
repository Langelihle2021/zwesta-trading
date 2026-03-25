Set-Location "C:\zwesta-trader\Zwesta Flutter App"
Write-Host "=== BUILDING ==="
flutter build web --release 2>&1 | Select-Object -Last 5
Write-Host "=== DEPLOYING ==="
Copy-Item -Path "build\web\*" -Destination "C:\zwesta-trader-web\" -Recurse -Force
Write-Host "=== PUSHING TO GIT ==="
git add -A
git commit -m "Use SSH tunnel URL for API connectivity" 2>&1
git push origin main 2>&1
Write-Host "=== ALL DONE ==="
