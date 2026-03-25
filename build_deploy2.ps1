Set-Location "C:\zwesta-trader\Zwesta Flutter App"
$log = "C:\zwesta-trader\build_log.txt"
"BUILD START: $(Get-Date)" | Out-File $log
flutter build web --release 2>&1 | Out-File $log -Append
"BUILD END: $(Get-Date)" | Out-File $log -Append
Copy-Item -Path "build\web\*" -Destination "C:\zwesta-trader-web\" -Recurse -Force
"DEPLOY DONE" | Out-File $log -Append
git add -A 2>&1 | Out-File $log -Append
git commit -m "Use SSH tunnel URL for API connectivity" 2>&1 | Out-File $log -Append
git push origin main 2>&1 | Out-File $log -Append
"ALL DONE: $(Get-Date)" | Out-File $log -Append
