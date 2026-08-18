@echo off
REM Metrc Daily Sync - Automated Task
REM Runs daily at 6:00 AM via Windows Task Scheduler

cd /d C:\python\metrc_api

REM Heartbeat: record run start in Supabase pipeline_runs (fail-safe; see C:\python\heartbeat.py)
set HB_RUN=-
for /f "usebackq delims=" %%i in (`.venv\Scripts\python.exe C:\python\heartbeat.py start metrc 2^>nul`) do set HB_RUN=%%i

REM Log start time
echo ======================================== >> logs\daily_sync.log
echo Starting Metrc Daily Sync at %DATE% %TIME% >> logs\daily_sync.log
echo ======================================== >> logs\daily_sync.log

REM Run the sync script using virtual environment Python
.venv\Scripts\python.exe metrc_daily_sync.py >> logs\daily_sync.log 2>&1
set SYNC_EXIT=%ERRORLEVEL%

REM Heartbeat: record completion
.venv\Scripts\python.exe C:\python\heartbeat.py finish metrc %HB_RUN% %SYNC_EXIT% >> logs\daily_sync.log 2>&1

REM Log completion
echo. >> logs\daily_sync.log
echo Completed at %DATE% %TIME% >> logs\daily_sync.log
echo Exit code: %SYNC_EXIT% >> logs\daily_sync.log
echo. >> logs\daily_sync.log

exit /b %SYNC_EXIT%
