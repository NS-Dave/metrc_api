@echo off
echo Updating metrc_sync scheduled task...
schtasks /Change /TN "\Automation\metrc_sync" /TR "C:\python\metrc_api\run_daily_sync.bat"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Task updated successfully!
    echo.
    echo Task will now run: C:\python\metrc_api\run_daily_sync.bat
    echo Next scheduled run: Tomorrow at 6:00 AM
) else (
    echo.
    echo [ERROR] Failed to update task. Error code: %ERRORLEVEL%
    echo You may need to run this as Administrator.
)

pause
