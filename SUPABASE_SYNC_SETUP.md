# Metrc → Supabase Data Warehouse

This setup syncs Metrc cultivation and processing data to Supabase for fast querying without API rate limits.

## Why Supabase?

**Problem**: Metrc API has strict rate limits (24-hour window max for inactive records), making queries slow and complex.

**Solution**: Daily incremental sync to Supabase enables:
- ⚡ Instant harvest reconciliation queries
- 📊 Historical analysis without API calls
- 🔍 Complex joins and aggregations
- 📈 Dashboards and reporting

## Setup

### 1. Create Supabase Schema

Run `supabase_schema.sql` in Supabase SQL Editor to create all tables:
- `metrc_harvests` - Harvest tracking
- `metrc_packages` - Package inventory
- `metrc_plant_batches` - Plant batches
- `metrc_plants` - Individual plants
- `metrc_transfers` - Transfer manifests
- `metrc_sync_log` - Sync history
- `harvest_reconciliation` view - Quick discrepancy analysis

### 2. Set Supabase Password

```powershell
# Set environment variable
$env:SUPABASE_PASSWORD = "your_supabase_password"

# Or set permanently
[System.Environment]::SetEnvironmentVariable('SUPABASE_PASSWORD', 'your_password', 'User')
```

### 3. Test Connection

```python
from supabase_config import get_connection_string
import psycopg2

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM metrc_harvests")
print(cursor.fetchone())
conn.close()
```

### 4. Run Initial Sync

```bash
# First time - syncs last 48 hours
python metrc_daily_sync.py
```

Expected output:
```
======================================================================
METRC DAILY INCREMENTAL SYNC
Timestamp: 2025-12-29T12:00:00
======================================================================

Testing Metrc API connection...
✓ Metrc API connected

Testing Supabase connection...
✓ Supabase connected

CULTIVATION LICENSE: MC281599
----------------------------------------------------------------------
Syncing harvests for MC281599 (last 48 hours)...
  Found 4 active, 8 inactive = 12 total
  ✓ Inserted 10, Updated 2

Syncing packages for MC281599 (last 48 hours)...
  Found 156 active, 23 inactive = 179 total
  ✓ Inserted 150, Updated 29

PROCESSING LICENSE: MP281433
----------------------------------------------------------------------
Syncing packages for MP281433 (last 48 hours)...
  Found 89 active, 12 inactive = 101 total
  ✓ Inserted 85, Updated 16

======================================================================
✓ DAILY SYNC COMPLETED SUCCESSFULLY
======================================================================
```

## Schedule Daily Sync

### Windows Task Scheduler

```powershell
# Create scheduled task to run daily at 6 AM
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\python\metrc_api\metrc_daily_sync.py" -WorkingDirectory "C:\python\metrc_api"
$trigger = New-ScheduledTaskTrigger -Daily -At 6am
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "Metrc Daily Sync" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

### Linux/Mac Cron

```bash
# Add to crontab (run daily at 6 AM)
0 6 * * * cd /path/to/metrc_api && python metrc_daily_sync.py >> sync.log 2>&1
```

## Querying Supabase

### Harvest Reconciliation (Fast!)

Instead of hitting Metrc API repeatedly, query Supabase:

```sql
-- All harvest discrepancies > 10g
SELECT 
    harvest_name,
    harvest_packaged_weight,
    total_package_weight_grams,
    weight_discrepancy_grams,
    package_count
FROM harvest_reconciliation
WHERE weight_discrepancy_grams > 10
ORDER BY weight_discrepancy_grams DESC;
```

### Recent Package Movements

```sql
-- Packages finished in last 7 days
SELECT 
    label,
    product_name,
    quantity,
    unit_of_measure,
    finished_date,
    source_harvest_names
FROM metrc_packages
WHERE finished_date > NOW() - INTERVAL '7 days'
    AND license_number = 'MC281599'
ORDER BY finished_date DESC;
```

### Active Inventory by Room

```sql
-- Current inventory by location
SELECT 
    location_name,
    COUNT(*) as package_count,
    SUM(quantity) as total_quantity,
    unit_of_measure
FROM metrc_packages
WHERE archived_date IS NULL 
    AND finished_date IS NULL
    AND license_number = 'MC281599'
GROUP BY location_name, unit_of_measure
ORDER BY location_name;
```

## Sync Monitoring

```sql
-- Check recent syncs
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

-- Failed syncs
SELECT * FROM metrc_sync_log
WHERE status = 'failed'
ORDER BY sync_start DESC;
```

## Data Tiers

### Tier 1: Weekly Refresh (Reference Data)
- Facilities
- Strains
- Locations
- Items

### Tier 2: Daily Incremental (48 hours)
- Harvests (active + last 48hr inactive)
- Packages (active + last 48hr inactive)
- Plant Batches (active + last 48hr)
- Plants (vegetative, flowering, on-hold)

### Tier 3: Weekly Deep Pull
- Transfers (last 7 days)
- Lab Tests (last 7 days)

### Tier 4: Monthly Backfill
- Historical inactive records for compliance

## Harvest Reconciliation Workflow

```python
# Query Supabase instead of Metrc API
import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# Find all discrepancies > 5g
cursor.execute("""
    SELECT * FROM harvest_reconciliation
    WHERE weight_discrepancy_grams > 5
    ORDER BY weight_discrepancy_grams DESC
""")

for row in cursor.fetchall():
    print(f"{row[1]}: {row[8]:.2f}g discrepancy")
```

## Troubleshooting

### Connection Errors

```bash
# Test environment variable
python -c "import os; print(os.getenv('SUPABASE_PASSWORD'))"

# Test connection
python -c "from supabase_config import get_connection_string; print('OK')"
```

### Sync Failures

Check `metrc_sync_log` table for error messages:

```sql
SELECT error_message 
FROM metrc_sync_log 
WHERE status = 'failed' 
ORDER BY sync_start DESC 
LIMIT 1;
```

### Missing Data

Run a backfill for specific date range:

```python
# Modify metrc_daily_sync.py to use custom date range
syncer.sync_harvests_incremental(CULTIVATION_LICENSE, hours=168)  # 7 days
```

## Performance

- **Metrc API Query**: 2-5 minutes for 317 harvests (365+ API calls)
- **Supabase Query**: < 1 second for same data
- **Daily Sync**: ~2-3 minutes for 48-hour window
- **Storage**: ~50MB per month of data

## Next Steps

1. ✅ Created schema and sync script
2. ⏭️ Run initial sync to populate data
3. ⏭️ Schedule daily sync
4. ⏭️ Build harvest reconciliation dashboard
5. ⏭️ Add weekly reference data refresh
6. ⏭️ Implement monthly backfill for historical compliance

## Files

- `supabase_schema.sql` - Database schema (run once in Supabase)
- `supabase_config.py` - Connection configuration
- `metrc_daily_sync.py` - Daily incremental sync script
- `metrc_sync_setup.md` - This file
