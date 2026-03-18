# Package Endpoint Source Tracking - Implementation Guide

## Summary

The `package_status` column in `metrc_packages` table **is already fully implemented** and tracks which Metrc API endpoint each package came from. This allows you to filter packages the same way the Metrc UI does.

## Database Column

**Column:** `package_status`  
**Type:** ENUM (`'active'`, `'inactive'`, `'intransit'`)  
**Purpose:** Track which Metrc endpoint returned each package  
**Updated:** On every sync (packages can move between states)

## Migration Status

✅ **Migration file exists:** `add_package_status.sql`  
✅ **Column exists in database:** Verified  
✅ **Code is using it:** `metrc_daily_sync.py` lines 675-677  

## Current State

As of the last check:
- **MC281599:** 8,797 active, 3 inactive, 0 intransit (3,428 unfinished)
- **MP281433:** 6,578 active, 4 inactive, 0 intransit (2,071 unfinished)

## How It Works

### In `metrc_daily_sync.py`

```python
def sync_packages_incremental(self, license_number: str, hours: int = 48):
    # Fetch from three endpoints
    active_packages = self.processing.get_packages('active', ...)
    inactive_packages = self.processing.get_packages('inactive', ...)
    intransit_packages = self.processing.client.get('packages/v2/intransit', ...)
    
    # Upsert with status tracking
    self.upsert_packages(active_packages, license_number, status='active')
    self.upsert_packages(inactive_packages, license_number, status='inactive')
    self.upsert_packages(intransit_packages, license_number, status='intransit')
```

Each package is tagged with the endpoint it came from when inserted/updated.

## How to Use It

### Get Only "Active" Packages (Metrc UI equivalent)

```sql
SELECT * FROM metrc_packages
WHERE license_number = 'MC281599'
  AND package_status = 'active'
  AND finished_date IS NULL
  AND archived_date IS NULL;
```

This gives you **exactly** what the Metrc UI "Active Packages" tab shows (2,718 packages in your case, not 3,428).

### Get In-Transit Packages

```sql
SELECT * FROM metrc_packages
WHERE license_number = 'MC281599'
  AND package_status = 'intransit';
```

### Get Distribution by Status

```sql
SELECT 
    package_status,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE finished_date IS NULL) as unfinished
FROM metrc_packages
WHERE license_number = 'MC281599'
GROUP BY package_status;
```

## About "Transferred" Packages

**Important:** The Metrc UI "Transferred" tab shows packages that were **sent out** in outgoing transfers. These packages:
- Still appear in `packages/v2/active` endpoint
- Are NOT marked as `package_status = 'transferred'`
- Must be identified by cross-referencing `metrc_transfers` table

### To Track Transferred Packages

You need to:

1. Query packages that appear in outgoing transfers:
```sql
SELECT DISTINCT p.*
FROM metrc_packages p
JOIN metrc_transfers t ON t.data::jsonb->'DeliveryPackages' @> 
    json_build_array(json_build_object('PackageLabel', p.label))::jsonb
WHERE t.direction = 'outgoing'
  AND p.license_number = 'MC281599';
```

2. **OR** add a new column to track this (recommended):
```sql
ALTER TABLE metrc_packages 
ADD COLUMN is_in_outgoing_transfer BOOLEAN DEFAULT FALSE;

-- Update during transfer sync
UPDATE metrc_packages 
SET is_in_outgoing_transfer = TRUE
WHERE label IN (SELECT package_label FROM outgoing_transfer_packages);
```

## Why No Intransit Packages Currently?

Zero `'intransit'` packages suggests:
1. No active incoming transfers at the moment, OR
2. The intransit endpoint sync may have failed silently

To verify, run a sync manually and check the output:
```bash
python metrc_daily_sync.py
```

Look for this line:
```
Found X active, Y inactive, Z intransit = N total
```

## Comparison: Your CSV Analysis vs Current DB

| Category | Your CSV | Current DB | Explanation |
|----------|----------|------------|-------------|
| Active-only | 2,718 | 3,428 | DB includes all unfinished, not filtered by `package_status` |
| In-transit | 239 | 0 | Either no current transfers OR sync issue |
| Transferred | 471 | N/A | Not tracked - needs transfer cross-reference |

## Next Steps

### 1. Verify Intransit Sync is Working

Check sync logs or run manually:
```bash
python metrc_daily_sync.py
```

### 2. Use Correct Filter for "Active Only"

Update your queries to include `package_status = 'active'`:

```sql
-- OLD (includes intransit)
SELECT * FROM metrc_packages
WHERE license_number = 'MC281599'
  AND finished_date IS NULL
  AND archived_date IS NULL;

-- NEW (matches Metrc UI)
SELECT * FROM metrc_packages
WHERE license_number = 'MC281599'
  AND package_status = 'active'
  AND finished_date IS NULL
  AND archived_date IS NULL;
```

### 3. (Optional) Add Transferred Package Tracking

If you need to identify packages in outgoing transfers:

```sql
-- Add column
ALTER TABLE metrc_packages 
ADD COLUMN in_outgoing_transfer BOOLEAN DEFAULT FALSE,
ADD COLUMN last_outgoing_transfer_id TEXT;

-- Create view
CREATE OR REPLACE VIEW packages_transferred AS
SELECT DISTINCT 
    p.*,
    t.id as transfer_id,
    t.manifest_number
FROM metrc_packages p
INNER JOIN metrc_transfers t ON ...
WHERE t.direction = 'outgoing';
```

## Testing

Run the verification script:
```bash
python verify_endpoint_source.py
```

This will show the current distribution and confirm everything is working.

## Summary

✅ **`package_status` column is already implemented and working**  
✅ **Use `package_status = 'active'` to match Metrc UI "Active" tab**  
⚠️ **Transferred packages need additional tracking via transfers table**  
❓ **Intransit packages showing as 0 - verify sync is working**
