# Backfill Script: February 3-5, 2026

## Purpose

This backfill script syncs data that was missed during the automation outage from **February 3-5, 2026** when the Windows Task Scheduler was misconfigured.

## What Gets Backfilled

### For Each Day (Feb 3, 4, 5):

**Cultivation License (MC281599):**
- All active harvests
- Harvests modified on that day
- All active packages  
- Packages modified on that day

**Processing License (MP281433):**
- All active packages
- Packages modified on that day

**Note:** Transfers are NOT included in this backfill because:
1. The current daily sync already pulls the last 7 days of transfers
2. Feb 6 sync would have captured transfers from Jan 30 - Feb 6 (includes Feb 3-5)
3. Plants are full syncs (not time-based), so they're always current

## How to Run

### Option 1: Batch File (Recommended)

```cmd
cd C:\python\metrc_api
run_backfill_feb_3_5.bat
```

This will:
- Prompt for confirmation before starting
- Run the backfill for all 3 days
- Show progress and results
- Display success/error message

### Option 2: Direct Python

```powershell
cd C:\python\metrc_api
.\.venv\Scripts\Activate.ps1
python backfill_feb_3_5_simple.py
```

## Expected Runtime

- **Per day:** 1-2 minutes
- **Total:** 3-6 minutes for all 3 days

## What You'll See

```
======================================================================
METRC BACKFILL: February 3-5, 2026
======================================================================

METRC DATA BACKFILL: 2026-02-03 to 2026-02-03
======================================================================

CULTIVATION LICENSE: MC281599
----------------------------------------------------------------------
Fetching harvests modified between 2026-02-03 and 2026-02-03...
  Found 0 active, 0 inactive = 0 total
  [OK] No harvests to sync
Fetching packages modified between 2026-02-03 and 2026-02-03...
  Found 302 active, 15 inactive = 317 total
  [OK] Inserted 0, Updated 317

PROCESSING LICENSE: MP281433
----------------------------------------------------------------------
Fetching packages modified between 2026-02-03 and 2026-02-03...
  Found 259 active, 8 inactive = 267 total
  [OK] Inserted 0, Updated 267

======================================================================
[SUCCESS] BACKFILL COMPLETED
======================================================================
```

## Verification

After running, verify the backfill:

```powershell
# Check in database
cd C:\python\metrc_api
.\.venv\Scripts\Activate.ps1
python -c "
from supabase_config import get_connection_string
import psycopg2

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# Check packages modified in Feb 3-5 range
cursor.execute('''
    SELECT DATE(last_modified) as date, COUNT(*) 
    FROM metrc_packages 
    WHERE last_modified >= '2026-02-03' 
      AND last_modified < '2026-02-06'
    GROUP BY DATE(last_modified)
    ORDER BY date
''')

print('Packages synced by date:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]} packages')

conn.close()
"
```

## Files

- **`backfill_feb_3_5_simple.py`** - Main backfill script (uses existing sync logic)
- **`run_backfill_feb_3_5.bat`** - Batch file to run the backfill
- **`BACKFILL_README.md`** - This documentation

## Technical Details

### API Calls Made

For each day, the script calls:
- `/harvests/v1/active` (Cultivation)
- `/harvests/v1/inactive?lastModifiedStart=...&lastModifiedEnd=...` (Cultivation)
- `/packages/v2/active` (Cultivation)
- `/packages/v2/inactive?lastModifiedStart=...&lastModifiedEnd=...` (Cultivation)
- `/packages/v2/active` (Processing)
- `/packages/v2/inactive?lastModifiedStart=...&lastModifiedEnd=...` (Processing)

### Database Operations

- Uses UPSERT logic (insert if new, update if exists)
- Matches on `harvest_name` for harvests
- Matches on `label` for packages
- Preserves existing records, only updates changed fields
- All operations are within database transactions (rollback on error)

### Safety Features

- Idempotent (safe to run multiple times)
- Prompts for confirmation before starting
- Transactional (all-or-nothing per entity type)
- Detailed progress logging
- Error handling with stack traces

## When to Use

Run this backfill if:
- ✅ You just fixed the automation and want to fill the gap
- ✅ You need historical data from Feb 3-5 specifically
- ✅ Reports show missing data for those dates

**Do NOT run if:**
- ❌ Automation is still broken (fix it first)
- ❌ You've already manually synced this data
- ❌ The dates have already been backfilled

## Support

If the backfill fails:

1. Check error messages in console
2. Verify Supabase connection: `$env:SUPABASE_PASSWORD` is set
3. Test Metrc API: `python simple_test.py`
4. Check database connectivity: `python -c "from supabase_config import get_connection_string; import psycopg2; psycopg2.connect(get_connection_string())"`

## After Running

Once the backfill completes successfully:

1. ✅ Data from Feb 3-5 is now in Supabase
2. ✅ Daily automation continues normally
3. ✅ No further action needed
4. 🗑️ Optional: Delete these backfill files if you won't need them again:
   - `backfill_feb_3_5.py`
   - `run_backfill_feb_3_5.bat`
   - `BACKFILL_README.md`
