@echo off
REM Backfill Metrc Data for February 3-5, 2026
REM Run this manually to sync the missing data from when automation was broken

cd /d C:\python\metrc_api

echo.
echo ======================================================================
echo METRC BACKFILL: February 3-5, 2026
echo ======================================================================
echo.
echo This will backfill data that was missed during the automation outage.
echo.
echo Press Ctrl+C to cancel, or
pause

echo.
echo Starting backfill...
echo.

REM Run the backfill script using virtual environment Python
.venv\Scripts\python.exe backfill_feb_3_5_simple.py

echo.
echo ======================================================================
echo Backfill completed with exit code: %ERRORLEVEL%
echo ======================================================================
echo.

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] All data from Feb 3-5 has been synced!
    echo.
    echo You can verify by checking:
    echo   - Database: metrc_packages, metrc_harvests tables
    echo   - Filter by last_modified dates in Feb 3-5 range
) else (
    echo [ERROR] Backfill failed. Check error messages above.
)

echo.
pause
