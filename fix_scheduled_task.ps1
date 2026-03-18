# Fix Metrc Scheduled Task Configuration
# Run this script as Administrator

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Metrc Automation Fix Script" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] This script requires Administrator privileges" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please right-click PowerShell and select 'Run as Administrator', then run:" -ForegroundColor Yellow
    Write-Host "  cd C:\python\metrc_api" -ForegroundColor Yellow
    Write-Host "  .\fix_scheduled_task.ps1" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "[INFO] Running as Administrator - OK" -ForegroundColor Green
Write-Host ""

# Verify batch file exists
$batchFile = "C:\python\metrc_api\run_daily_sync.bat"
if (-not (Test-Path $batchFile)) {
    Write-Host "[ERROR] Batch file not found: $batchFile" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "[INFO] Batch file found - OK" -ForegroundColor Green

# Update the scheduled task
Write-Host ""
Write-Host "Updating scheduled task..." -ForegroundColor Yellow

try {
    schtasks /Change /TN "\Automation\metrc_sync" /TR $batchFile | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Scheduled task updated successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Task Configuration:" -ForegroundColor Cyan
        Write-Host "  Name: \Automation\metrc_sync" -ForegroundColor White
        Write-Host "  Command: $batchFile" -ForegroundColor White
        Write-Host "  Schedule: Daily at 6:00 AM" -ForegroundColor White
    } else {
        Write-Host "[ERROR] Failed to update task (exit code: $LASTEXITCODE)" -ForegroundColor Red
        pause
        exit 1
    }
} catch {
    Write-Host "[ERROR] Failed to update task: $_" -ForegroundColor Red
    pause
    exit 1
}

# Verify the change
Write-Host ""
Write-Host "Verifying configuration..." -ForegroundColor Yellow
$taskInfo = schtasks /Query /TN "\Automation\metrc_sync" /FO LIST /V | Select-String "Task To Run"
Write-Host $taskInfo -ForegroundColor White

# Offer to test run
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
$response = Read-Host "Would you like to test run the task now? (Y/N)"
if ($response -eq 'Y' -or $response -eq 'y') {
    Write-Host ""
    Write-Host "Starting test run..." -ForegroundColor Yellow
    Write-Host "(This will take 5-10 minutes to sync all data)" -ForegroundColor Yellow
    Write-Host ""
    
    Start-ScheduledTask -TaskName "metrc_sync" -TaskPath "\Automation\"
    
    Write-Host "[INFO] Task started. Check the log file:" -ForegroundColor Green
    Write-Host "  C:\python\metrc_api\logs\daily_sync.log" -ForegroundColor White
    Write-Host ""
    Write-Host "Wait 30 seconds for task to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
    
    # Show recent log output
    if (Test-Path "C:\python\metrc_api\logs\daily_sync.log") {
        Write-Host ""
        Write-Host "Recent log output:" -ForegroundColor Cyan
        Write-Host "-" * 70
        Get-Content "C:\python\metrc_api\logs\daily_sync.log" -Tail 20
        Write-Host "-" * 70
    }
}

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Green
Write-Host "FIX COMPLETE!" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Green
Write-Host ""
Write-Host "Next automatic run: Tomorrow at 6:00 AM" -ForegroundColor Cyan
Write-Host ""
pause
