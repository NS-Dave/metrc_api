# Metrc Automation Health Check Script
# Verifies scheduled task configuration and recent sync history

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "METRC AUTOMATION HEALTH CHECK" -ForegroundColor Cyan
Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Check 1: Scheduled Task Configuration
Write-Host "TASK CONFIGURATION" -ForegroundColor Yellow
Write-Host "-" * 80

$taskInfo = schtasks /Query /TN "\Automation\metrc_sync" /FO LIST /V 2>&1

if ($LASTEXITCODE -eq 0) {
    $taskPathLine = ($taskInfo | Select-String "Task To Run:" | Out-String).Trim()
    $taskPath = $taskPathLine -replace "^.*Task To Run:\s*", ""
    $taskPath = ($taskPath -split "`n")[0].Trim()
    
    $lastRunLine = ($taskInfo | Select-String "Last Run Time:" | Out-String).Trim()
    $lastRun = $lastRunLine -replace "^.*Last Run Time:\s*", ""
    $lastRun = ($lastRun -split "`n")[0].Trim()
    
    $nextRunLine = ($taskInfo | Select-String "Next Run Time:" | Out-String).Trim()
    $nextRun = $nextRunLine -replace "^.*Next Run Time:\s*", ""
    $nextRun = ($nextRun -split "`n")[0].Trim()
    
    $statusLine = ($taskInfo | Select-String "^Status:" | Out-String).Trim()
    $status = $statusLine -replace "^.*Status:\s*", ""
    $status = ($status -split "`n")[0].Trim()
    
    Write-Host "Task Name:     \Automation\metrc_sync" -ForegroundColor White
    Write-Host "Status:        $status" -ForegroundColor $(if ($status -eq "Ready") { "Green" } else { "Red" })
    Write-Host "Command:       $taskPath" -ForegroundColor White
    
    # Verify it's using the batch file
    if ($taskPath -like "*run_daily_sync.bat*") {
        Write-Host "Configuration: [OK] Using batch file" -ForegroundColor Green
    } else {
        Write-Host "Configuration: [WARNING] Not using batch file!" -ForegroundColor Red
        Write-Host "               Should be: C:\python\metrc_api\run_daily_sync.bat" -ForegroundColor Yellow
    }
    
    Write-Host "Last Run:      $lastRun" -ForegroundColor White
    Write-Host "Next Run:      $nextRun" -ForegroundColor White
} else {
    Write-Host "[ERROR] Scheduled task '\Automation\metrc_sync' not found!" -ForegroundColor Red
}

Write-Host ""

# Check 2: Virtual Environment
Write-Host "VIRTUAL ENVIRONMENT" -ForegroundColor Yellow
Write-Host "-" * 80

if (Test-Path "C:\python\metrc_api\.venv\Scripts\python.exe") {
    Write-Host "[OK] Virtual environment exists" -ForegroundColor Green
    
    # Check installed packages
    $pipList = & "C:\python\metrc_api\.venv\Scripts\pip.exe" list 2>&1 | Out-String
    $requiredPackages = @{
        "requests" = $false
        "urllib3" = $false
        "python-dotenv" = $false
        "psycopg2-binary" = $false
    }
    
    foreach ($pkg in $requiredPackages.Keys) {
        if ($pipList -match $pkg) {
            $requiredPackages[$pkg] = $true
        }
    }
    
    $missingPackages = @($requiredPackages.Keys | Where-Object { -not $requiredPackages[$_] })
    
    if ($missingPackages.Count -eq 0) {
        Write-Host "[OK] All required packages installed" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Missing packages: $($missingPackages -join ', ')" -ForegroundColor Red
    }
} else {
    Write-Host "[ERROR] Virtual environment not found!" -ForegroundColor Red
    Write-Host "Run: python -m venv .venv" -ForegroundColor Yellow
}

Write-Host ""

# Check 3: Configuration Files
Write-Host "CONFIGURATION FILES" -ForegroundColor Yellow
Write-Host "-" * 80

$configFiles = @(
    @{Path="C:\python\metrc_api\.env"; Required=$true},
    @{Path="C:\python\metrc_api\run_daily_sync.bat"; Required=$true},
    @{Path="C:\python\metrc_api\metrc_daily_sync.py"; Required=$true}
)

foreach ($file in $configFiles) {
    if (Test-Path $file.Path) {
        Write-Host "[OK] $($file.Path)" -ForegroundColor Green
    } else {
        $status = if ($file.Required) { "[ERROR]" } else { "[WARNING]" }
        $color = if ($file.Required) { "Red" } else { "Yellow" }
        Write-Host "$status $($file.Path) - NOT FOUND" -ForegroundColor $color
    }
}

Write-Host ""

# Check 4: Log Files
Write-Host "LOG FILES" -ForegroundColor Yellow
Write-Host "-" * 80

if (Test-Path "C:\python\metrc_api\logs\daily_sync.log") {
    $logFile = Get-Item "C:\python\metrc_api\logs\daily_sync.log"
    $logSize = "{0:N2} KB" -f ($logFile.Length / 1KB)
    $logModified = $logFile.LastWriteTime
    
    Write-Host "Log File:      C:\python\metrc_api\logs\daily_sync.log" -ForegroundColor White
    Write-Host "Size:          $logSize" -ForegroundColor White
    Write-Host "Last Modified: $logModified" -ForegroundColor White
    
    # Check for recent activity
    $hoursSinceUpdate = (Get-Date) - $logModified
    if ($hoursSinceUpdate.TotalHours -lt 24) {
        Write-Host "Status:        [OK] Updated in last 24 hours" -ForegroundColor Green
    } else {
        Write-Host "Status:        [WARNING] Not updated in $([int]$hoursSinceUpdate.TotalHours) hours" -ForegroundColor Yellow
    }
    
    # Check last few lines
    Write-Host ""
    Write-Host "Last 10 lines:" -ForegroundColor Cyan
    Get-Content "C:\python\metrc_api\logs\daily_sync.log" -Tail 10 | ForEach-Object {
        if ($_ -match "SUCCESS") {
            Write-Host "  $_" -ForegroundColor Green
        } elseif ($_ -match "ERROR|Failed|Traceback") {
            Write-Host "  $_" -ForegroundColor Red
        } else {
            Write-Host "  $_" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "[WARNING] No log file found" -ForegroundColor Yellow
    Write-Host "The task may not have run yet, or logging is not working." -ForegroundColor Gray
}

Write-Host ""

# Check 5: Database Connection (quick test)
Write-Host "DATABASE CONNECTION" -ForegroundColor Yellow
Write-Host "-" * 80

if ($env:SUPABASE_PASSWORD) {
    Write-Host "[OK] SUPABASE_PASSWORD environment variable is set" -ForegroundColor Green
    
    # Try to query recent syncs
    try {
        $pythonCmd = "C:\python\metrc_api\.venv\Scripts\python.exe"
        $checkScript = @"
import os
os.chdir('C:\\python\\metrc_api')
from supabase_config import get_connection_string
import psycopg2
conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()
cursor.execute('SELECT sync_start, entity_type, license_number, status FROM metrc_sync_log ORDER BY sync_start DESC LIMIT 5')
rows = cursor.fetchall()
for row in rows:
    print(f'{row[0]} | {row[1]:15} | {row[2]} | {row[3]}')
conn.close()
"@
        
        Write-Host ""
        Write-Host "Recent sync operations (last 5):" -ForegroundColor Cyan
        Write-Host "-" * 80
        $result = & $pythonCmd -c $checkScript 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $result | ForEach-Object {
                if ($_ -match "completed") {
                    Write-Host $_ -ForegroundColor Green
                } elseif ($_ -match "error|failed") {
                    Write-Host $_ -ForegroundColor Red
                } else {
                    Write-Host $_ -ForegroundColor White
                }
            }
        } else {
            Write-Host "[ERROR] Database query failed" -ForegroundColor Red
            Write-Host $result -ForegroundColor Gray
        }
    } catch {
        Write-Host "[ERROR] Failed to connect to database: $_" -ForegroundColor Red
    }
} else {
    Write-Host "[WARNING] SUPABASE_PASSWORD not set in environment" -ForegroundColor Yellow
    Write-Host "Set with: `$env:SUPABASE_PASSWORD = 'your_password'" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "HEALTH CHECK COMPLETE" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
