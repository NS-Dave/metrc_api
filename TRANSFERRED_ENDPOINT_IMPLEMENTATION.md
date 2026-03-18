# Transferred Packages Endpoint Integration

## What Changed

Thanks to finding the `packages/GetTransferred` endpoint in Postman, we can now sync transferred packages directly from Metrc instead of trying to infer them from other data sources.

## Changes Made

### 1. Config Updates ([config.py](config.py))
Added two new endpoint constants:
```python
PACKAGES_INTRANSIT = "packages/v2/intransit"
PACKAGES_TRANSFERRED = "packages/GetTransferred"
```

### 2. Processing Client Updates ([processing.py](processing.py))
Updated `get_packages()` method to support all package statuses:
```python
status: 'active', 'onhold', 'inactive', 'intransit', or 'transferred'
```

### 3. Daily Sync Updates ([metrc_daily_sync.py](metrc_daily_sync.py))
Now syncs from all four package endpoints:
```python
# Sync from 4 endpoints
active_packages = get_packages('active', ...)
inactive_packages = get_packages('inactive', ...)
intransit_packages = get_packages('intransit', ...)
transferred_packages = get_packages('transferred', ...)

# Tag each with appropriate status
upsert_packages(..., status='transferred')
```

### 4. Database Migration ([add_transferred_to_package_status.sql](add_transferred_to_package_status.sql))
Adds 'transferred' to the enum:
```sql
ALTER TYPE package_status_type ADD VALUE IF NOT EXISTS 'transferred';
```

### 5. Updated Views ([package_ui_category_views.sql](package_ui_category_views.sql))
Simplified transferred view to use the package_status column directly:
```sql
CREATE OR REPLACE VIEW metrc_packages_transferred_ui AS
SELECT * FROM metrc_packages
WHERE package_status = 'transferred';
```

## Implementation Steps

### Step 1: Run Database Migration
```bash
# Connect to Supabase
$connString = "postgresql://postgres:YOUR_PASSWORD@..."

# Run migration
psql "$connString" -f add_transferred_to_package_status.sql
```

### Step 2: Test the Transferred Endpoint
```bash
# Set environment variables first
$env:METRC_SOFTWARE_API_KEY = "your_key"
$env:METRC_USER_API_KEY = "your_key"

# Test the endpoint
python test_transferred_endpoint.py
```

### Step 3: Run Daily Sync
```bash
python metrc_daily_sync.py
```

You should see output like:
```
Syncing packages for MC281599 (last 48 hours)...
  Found 3000 active, 50 inactive, 0 intransit, 471 transferred = 3521 total
  ✓ Inserted 10, Updated 3511
```

### Step 4: Verify Data
```bash
python verify_endpoint_source.py
```

Or query directly:
```sql
-- See distribution
SELECT package_status, COUNT(*) 
FROM metrc_packages 
WHERE license_number = 'MC281599'
GROUP BY package_status;

-- Get transferred packages (should match Metrc UI)
SELECT * FROM metrc_packages
WHERE license_number = 'MC281599'
  AND package_status = 'transferred';
```

## Expected Results

Based on your CSV analysis, you should see:

| Status | Expected Count (MC281599) |
|--------|---------------------------|
| active | 2,718 |
| intransit | 239 |
| transferred | 471 |
| inactive | 3 |
| **Total unfinished** | **3,428** |

## Query Examples

### Get Active Packages (Metrc UI "Active" tab)
```sql
SELECT * FROM metrc_packages
WHERE license_number = 'MC281599'
  AND package_status = 'active'
  AND finished_date IS NULL
  AND archived_date IS NULL;
```

### Get In-Transit Packages (Metrc UI "In-Transit" tab)
```sql
SELECT * FROM metrc_packages
WHERE license_number = 'MC281599'
  AND package_status = 'intransit';
```

### Get Transferred Packages (Metrc UI "Transferred" tab)
```sql
SELECT * FROM metrc_packages
WHERE license_number = 'MC281599'
  AND package_status = 'transferred';
```

### Get Summary Dashboard
```sql
SELECT * FROM metrc_packages_summary;
```

## Benefits

1. **Direct endpoint sync** - No more inferring transferred status from other data
2. **Matches Metrc UI exactly** - All four package views now map 1:1 to package_status values
3. **Simpler queries** - Just filter by `package_status = 'transferred'`
4. **Accurate counts** - Should match Metrc UI exactly after sync

## Troubleshooting

### If transferred count is 0 after sync:
1. Check sync logs for errors calling packages/GetTransferred
2. Verify API permissions include access to GetTransferred endpoint
3. Ensure licenses have transferred packages in Metrc UI

### If counts don't match Metrc UI:
1. Run a full sync to ensure all packages are captured
2. Check last_modified dates to ensure recent data
3. Verify that finished/archived filtering matches Metrc logic

## Files Modified

- ✅ [config.py](config.py) - Added PACKAGES_INTRANSIT and PACKAGES_TRANSFERRED endpoints
- ✅ [processing.py](processing.py) - Updated get_packages() to support intransit/transferred
- ✅ [metrc_daily_sync.py](metrc_daily_sync.py) - Added transferred endpoint sync
- ✅ [package_ui_category_views.sql](package_ui_category_views.sql) - Simplified transferred view
- ✅ [verify_endpoint_source.py](verify_endpoint_source.py) - Added transferred to verification

## Files Created

- 📄 [add_transferred_to_package_status.sql](add_transferred_to_package_status.sql) - Migration script
- 📄 [test_transferred_endpoint.py](test_transferred_endpoint.py) - Testing script
- 📄 This file - Implementation guide

## Next Steps

1. Run the migration
2. Test the endpoint
3. Run daily sync
4. Update any existing queries/reports to use `package_status` filter
5. Consider updating documentation/dashboards to show all four categories
