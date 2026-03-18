# METRC Automation Fix - Summary

**Date:** February 5, 2026
**Status:** ✅ Script fixed and tested successfully | ⚠️ Scheduled task needs manual update

---

## What Was Fixed

### 1. Unicode Encoding Errors ✅
**Problem:** The script used Unicode checkmark symbols (✓ ✗) that Windows console couldn't display
**Fix:** Replaced all Unicode characters with ASCII equivalents ([OK], [ERROR], [SUCCESS])
**Result:** Script now runs without encoding errors

### 2. Database Transaction Handling ✅
**Problem:** Duplicate key errors weren't rolling back transactions properly
**Fix:** Added rollback logic before error logging
**Result:** Failed transactions are properly cleaned up

### 3. Package ID Conflicts ✅
**Problem:** Packages appearing in multiple endpoints caused duplicate key violations
**Fix:** Enhanced existence check to look up by both ID and label
**Result:** Packages are correctly updated regardless of which endpoint they come from

---

## Test Results ✅

Successfully ran full sync on **February 5, 2026 at 4:16 PM**:

**Cultivation License (MC281599):**
- 559 packages updated
- 30 transfers updated
- 1,859 plants updated
- 25 plant batches updated

**Processing License (MP281433):**
- 8 packages inserted, 534 updated
- 8 transfers inserted, 20 updated

**Exit Code:** 0 (Success)

---

## What Still Needs To Be Done

### Update the Windows Scheduled Task ⚠️

The scheduled task `\Automation\metrc_sync` still has the OLD configuration:
- Current: Executes `C:\python\metrc_api\metrc_daily_sync.py` (won't work)
- Needed: Execute `C:\python\metrc_api\run_daily_sync.bat` (proper wrapper with logging)

### Manual Update Instructions

**Option 1: Using Task Scheduler GUI** (Recommended)

1. Press `Win + R`, type `taskschd.msc`, press Enter
2. Navigate to: `Task Scheduler Library > Automation`
3. Find and double-click `metrc_sync`
4. Go to the **Actions** tab
5. Select the action and click **Edit**
6. Change:
   - **Program/script:** `C:\python\metrc_api\run_daily_sync.bat`
   - **Add arguments:** (leave empty)
   - **Start in:** `C:\python\metrc_api`
7. Click **OK** on all dialogs
8. Right-click the task → **Run** to test

**Option 2: Using PowerShell** (Run as Administrator)

```powershell
schtasks /Change /TN "\Automation\metrc_sync" /TR "C:\python\metrc_api\run_daily_sync.bat"
```

**Option 3: Using the Batch File**

1. Right-click `C:\python\metrc_api\update_scheduled_task.bat`
2. Select **Run as administrator**
3. Press any key when it completes

---

## Verification Steps

After updating the task:

### 1. Verify Task Configuration

```powershell
Get-ScheduledTask -TaskName "metrc_sync" -TaskPath "\Automation\" |
    Select-Object -ExpandProperty Actions |
    Format-List Execute, Arguments, WorkingDirectory
```

Should show:
```
Execute          : C:\python\metrc_api\run_daily_sync.bat
Arguments        :
WorkingDirectory : C:\python\metrc_api
```

### 2. Test Run

```powershell
Start-ScheduledTask -TaskName "metrc_sync" -TaskPath "\Automation\"
```

### 3. Check Log File

```powershell
Get-Content C:\python\metrc_api\logs\daily_sync.log -Tail 50
```

Should see:
```
========================================
Starting Metrc Daily Sync at [date/time]
========================================
[... sync output ...]
Completed at [date/time]
Exit code: 0
```

### 4. Verify in Database

```sql
SELECT entity_type, license_number, sync_type, sync_start, status,
       records_pulled, records_inserted, records_updated
FROM metrc_sync_log
WHERE sync_start > NOW() - INTERVAL '1 hour'
ORDER BY sync_start DESC;
```

---

## Files Created

1. **`run_daily_sync.bat`** - Proper wrapper script with logging
   - Calls Python with correct interpreter
   - Logs to `logs/daily_sync.log`
   - Captures exit codes

2. **`update_scheduled_task.bat`** - Batch file to update the scheduled task
   - Run as administrator to apply fix

3. **`logs/` directory** - Created for log files

4. **`metrc_daily_sync.py`** - Updated with fixes
   - No more Unicode characters
   - Better error handling
   - Proper transaction rollback

---

## Schedule Information

**Current Status:**
- Task Name: `metrc_sync`
- Path: `\Automation\`
- Schedule: Daily at 6:00 AM
- State: Ready
- Next Run: **February 6, 2026 at 6:00 AM**
- Last Successful Run: February 2, 2026 at 6:00 AM

**After Update:**
- The task will run tomorrow at 6 AM using the new batch file
- Logs will be written to `logs\daily_sync.log`
- Sync results will be in the `metrc_sync_log` database table

---

## Monitoring

### Check if automation runs tomorrow:

```powershell
# Check last run time
Get-ScheduledTaskInfo -TaskName "metrc_sync" -TaskPath "\Automation\" |
    Select-Object LastRunTime, LastTaskResult, NextRunTime

# View recent log entries
Get-Content C:\python\metrc_api\logs\daily_sync.log -Tail 100

# Check database
# (run in python REPL from metrc_api directory)
```

```python
import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()
cursor.execute("""
    SELECT sync_start, entity_type, license_number, status,
           records_pulled, records_inserted, records_updated
    FROM metrc_sync_log
    WHERE sync_start::date = CURRENT_DATE
    ORDER BY sync_start DESC
""")
for row in cursor.fetchall():
    print(row)
conn.close()
```

---

## Troubleshooting

**If the task fails tomorrow:**

1. Check the log file: `C:\python\metrc_api\logs\daily_sync.log`
2. Manually run the batch file to test:
   ```batch
   C:\python\metrc_api\run_daily_sync.bat
   ```
3. Check Task Scheduler History:
   - Open Task Scheduler
   - View → Show History (if not enabled)
   - Look for errors in the History tab

**If you see "File not found" errors:**
- Verify Python path: `C:\Python314\python.exe` exists
- Verify batch file exists: `C:\python\metrc_api\run_daily_sync.bat`

**If you see permission errors:**
- Task might need to run with administrator privileges
- Edit task → General tab → "Run with highest privileges"

---

## Next Steps

1. ✅ **Complete:** Fix Unicode encoding issues
2. ✅ **Complete:** Test sync script (works perfectly)
3. ⚠️ **TODO:** Update scheduled task (manual step required)
4. ⚠️ **TODO:** Verify automated run on February 6 at 6 AM
5. ⚠️ **TODO:** Consider backfilling missing data from Feb 3-5

---

## Contact & Support

**Log Files:** `C:\python\metrc_api\logs\daily_sync.log`
**Database:** `metrc_sync_log` table in Supabase
**Task Scheduler:** `\Automation\metrc_sync`

For questions or issues, check:
1. The daily sync log file
2. Windows Task Scheduler history
3. Database sync log table
4. `AUTOMATION_STATUS_REPORT.md` for initial diagnosis

---

**Script fixed and tested successfully! Just need to update the scheduled task using one of the methods above.**
