@echo off
REM Metrc Daily Sync - Automated Task
REM Runs daily at 6:00 AM via Windows Task Scheduler

cd /d C:\python\metrc_api

REM Log start time
echo ======================================== >> logs\daily_sync.log
echo Starting Metrc Daily Sync at %DATE% %TIME% >> logs\daily_sync.log
echo ======================================== >> logs\daily_sync.log

REM Run the sync script using virtual environment Python
.venv\Scripts\python.exe metrc_daily_sync.py >> logs\daily_sync.log 2>&1

REM Log completion
echo. >> logs\daily_sync.log
echo Completed at %DATE% %TIME% >> logs\daily_sync.log
echo Exit code: %ERRORLEVEL% >> logs\daily_sync.log
echo. >> logs\daily_sync.log

exit /b %ERRORLEVEL%
