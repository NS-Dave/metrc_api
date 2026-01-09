# Metrc → Supabase Scheduled Tasks Breakdown

## Overview
A single Windows Task Scheduler task runs daily to sync all Metrc data to Supabase.

---

## Task Schedule

### **Task Name:** `metrc_sync`
- **Location:** `\Automation\metrc_sync`
- **Script:** `C:\python\metrc_api\metrc_daily_sync.py`
- **Schedule:** Daily at 6:00 AM
- **Last Run:** January 7, 2026 at 6:00:01 AM
- **Next Run:** January 8, 2026 at 6:00:00 AM
- **Status:** Ready

---

## What Gets Synced

The daily task syncs data from two Metrc licenses:

### **License MC281599 (Cultivation)**
1. **Harvests** (last 48 hours)
   - Active harvests
   - Inactive harvests modified in last 48 hours
   - Stores: harvest name, weight, dates, source plant batches
   
2. **Packages** (last 48 hours)
   - Active packages
   - Inactive packages modified in last 48 hours
   - Stores: product info, quantities, locations, source harvests
   
3. **Transfers** (last 7 days)
   - Incoming transfers
   - Outgoing transfers
   - Stores: manifest details, delivery info, recipient/sender
   - Package-level details with wholesale pricing
   
4. **Plants** (full sync)
   - Vegetative plants
   - Flowering plants
   - On-hold plants
   - Inactive plants
   - Stores: strain, location, growth phase, dates

5. **Plant Batches** (full sync)
   - Active plant batches
   - Inactive plant batches
   - Stores: batch name, count, location, strain

### **License MP281433 (Processing)**
1. **Packages** (last 48 hours)
   - Active packages
   - Inactive packages modified in last 48 hours
   
2. **Transfers** (last 7 days)
   - Incoming transfers
   - Outgoing transfers
   - Package-level details with wholesale pricing
   
3. **Plants** (attempted, skipped)
   - Processing license doesn't have cultivation access
   - Gracefully skipped with no errors

---

## Sync Details by Entity

### Harvests
- **Sync Window:** Last 48 hours
- **Method:** `sync_harvests_incremental(license, hours=48)`
- **Chunking:** 24-hour chunks (Metrc API requirement)
- **Table:** `metrc_harvests`
- **Logging:** Records pulled/inserted/updated in `metrc_sync_log`

### Packages
- **Sync Window:** Last 48 hours
- **Method:** `sync_packages_incremental(license, hours=48)`
- **Chunking:** 24-hour chunks
- **Table:** `metrc_packages`
- **Includes:** Product info, weights, locations, lab tests, harvest sources

### Transfers
- **Sync Window:** Last 7 days
- **Method:** `sync_transfers_incremental(license, days=7)`
- **Chunking:** 24-hour windows
- **Tables:** 
  - `metrc_transfers` - Main transfer/delivery data
  - `metrc_transfer_packages` - Package-level details with pricing
- **Direction Aware:** Stores incoming and outgoing separately
- **Enrichment:** Fetches delivery details and full package data

### Plants
- **Sync Window:** Full (all active and inactive)
- **Method:** `sync_plants(license)`
- **No Time Filtering:** Fetches all plants regardless of modification date
- **Tables:**
  - `metrc_plants` - Individual tracked plants
  - `metrc_plant_batches` - Plant batch groups
- **Phases:** Vegetative, Flowering, On-hold, Inactive

---

## Execution Flow

```
1. Test Metrc API connection
2. Test Supabase connection
3. Sync Cultivation License (MC281599):
   - Harvests (48 hours)
   - Packages (48 hours)
   - Transfers (7 days)
   - Plants (full)
4. Sync Processing License (MP281433):
   - Packages (48 hours)
   - Transfers (7 days)
   - Plants (skip - no cultivation access)
5. Log results to metrc_sync_log
6. Close connections
```

---

## Monitoring

### Check Sync History
```sql
SELECT 
    entity_type,
    license_number,
    sync_start,
    records_pulled,
    records_inserted,
    records_updated,
    status
FROM metrc_sync_log
ORDER BY sync_start DESC
LIMIT 20;
```

### Check for Failures
```sql
SELECT * FROM metrc_sync_log
WHERE status = 'failed'
ORDER BY sync_start DESC;
```

### View Task Status
```powershell
Get-ScheduledTask -TaskName "metrc_sync" | Get-ScheduledTaskInfo
```

---

## Data Freshness

| Entity | Cultivation License | Processing License | Update Frequency |
|--------|--------------------|--------------------|------------------|
| Harvests | Last 48 hours | N/A | Daily at 6 AM |
| Packages | Last 48 hours | Last 48 hours | Daily at 6 AM |
| Transfers | Last 7 days | Last 7 days | Daily at 6 AM |
| Plants | Full snapshot | N/A | Daily at 6 AM |
| Plant Batches | Full snapshot | N/A | Daily at 6 AM |

---

## Performance

- **Typical Duration:** 2-5 minutes per run
- **API Calls:** ~50-100 per sync (depending on data volume)
- **Database Operations:** Insert/update ~200-500 records per sync
- **Error Handling:** Failed syncs logged to `metrc_sync_log`

---

## Manual Execution

Run the sync manually anytime:
```powershell
cd C:\python\metrc_api
python metrc_daily_sync.py
```

---

## Recent Updates (January 7, 2026)

✅ Added plants and plant batches sync
- Now syncs all plant phases (vegetative, flowering, on-hold, inactive)
- Now syncs all plant batches (active and inactive)
- Currently tracking 768 plants (419 flowering, 349 inactive)
- Gracefully handles processing license without cultivation access

✅ Transfer sync uses direction-aware storage
- Incoming and outgoing transfers stored separately
- Full package enrichment with 40+ fields
- Historical backfill completed: 3,803 transfers, 75,411 packages

---

## Files

- **Main Script:** `metrc_daily_sync.py` - Daily sync orchestration
- **Config:** `supabase_config.py` - Database connection
- **Schema:** `supabase_schema.sql` - Database tables
- **Documentation:** `SUPABASE_SYNC_SETUP.md` - Setup guide
