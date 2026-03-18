# Package Status Filtering - Critical Documentation

## ⚠️ CRITICAL: Metrc API Limitation

The Metrc API has a fundamental limitation: **endpoints filter by `lastModified`, not by current state**.

### The Problem

When you call `/packages/v2/active`:
- **What you expect**: Currently active packages
- **What you get**: Packages that were recently modified (even if now finished/archived)

### Real Data Evidence

```
Packages from /packages/v2/active endpoint:  14,956
Actually finished/archived:                   9,235 (61.7%!)
```

**Over 60% of packages from the "active" endpoint are actually finished!**

## ✅ Correct Solution

### Database Schema

```sql
-- Tracks which API endpoint returned the data (debugging only)
endpoint_source TEXT  -- 'active', 'inactive', 'intransit', 'transferred'

-- Actual package status (USE THESE for filtering!)
is_finished BOOLEAN       -- Package is finished (from API IsFinished flag)
is_archived BOOLEAN       -- Package is archived (from API IsArchived flag)
finished_date TIMESTAMPTZ -- When package was finished
archived_date TIMESTAMPTZ -- When package was archived
is_on_hold BOOLEAN        -- Package is on hold
```

### Views for Common Queries

#### 1. Active Packages (Matching Metrc UI)
```sql
SELECT * FROM active_packages 
WHERE license_number = 'MC281599';

-- Equivalent manual query:
SELECT * FROM metrc_packages
WHERE is_finished = false
  AND archived_date IS NULL
  AND (is_archived = false OR is_archived IS NULL);
```

Result: **3,465 packages** (vs 8,559 from endpoint_source='active')

#### 2. Available Inventory
```sql
SELECT * FROM available_inventory 
WHERE license_number = 'MC281599'
ORDER BY quantity DESC;

-- Active packages with remaining quantity
```

Result: **3,204 packages** with quantity > 0

#### 3. In-Transit Packages
```sql
SELECT * FROM intransit_packages 
WHERE license_number = 'MC281599';

-- Packages on manifests but not yet received
```

### Python Example

```python
import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# ✅ CORRECT: Use the view
cursor.execute("""
    SELECT * FROM active_packages 
    WHERE license_number = %s
""", ('MC281599',))

# ✅ CORRECT: Use status flags
cursor.execute("""
    SELECT * FROM metrc_packages
    WHERE license_number = %s
      AND is_finished = false
      AND archived_date IS NULL
""", ('MC281599',))

# ❌ WRONG: Don't filter by endpoint_source
cursor.execute("""
    SELECT * FROM metrc_packages
    WHERE endpoint_source = 'active'  -- WILL INCLUDE FINISHED PACKAGES!
""")
```

## Understanding endpoint_source

The `endpoint_source` column is **only useful for debugging**:
- Tells you which API endpoint most recently returned the package
- Indicates recency of data, not current state
- Should NEVER be used for business logic

### Why It Exists

When a package is finished, it gets a `lastModified` timestamp update. The next incremental sync (48-hour window) will pull it from `/packages/v2/active` because it was recently modified, even though it's now finished.

### Example Timeline

```
Day 1:  Package created → active endpoint returns it → endpoint_source='active', is_finished=false
Day 30: Package finished → lastModified updated
Day 30: Next sync runs → active endpoint STILL returns it (recently modified!)
                      → endpoint_source='active', is_finished=TRUE ⚠️
```

## Query Patterns

### Get truly active packages
```sql
SELECT * FROM active_packages WHERE license_number = 'MC281599';
```

### Get finished packages from last 30 days
```sql
SELECT * FROM metrc_packages 
WHERE license_number = 'MC281599'
  AND is_finished = true
  AND finished_date >= NOW() - INTERVAL '30 days'
ORDER BY finished_date DESC;
```

### Find packages in limbo (modified recently but finished)
```sql
SELECT label, endpoint_source, is_finished, finished_date, last_modified
FROM metrc_packages
WHERE endpoint_source = 'active' 
  AND is_finished = true
ORDER BY last_modified DESC
LIMIT 100;
```

### Check data freshness
```sql
SELECT 
    endpoint_source,
    COUNT(*) as count,
    MAX(synced_at) as last_sync
FROM metrc_packages
WHERE license_number = 'MC281599'
GROUP BY endpoint_source;
```

## Harvest Reconciliation Impact

**This limitation affects harvest weight reconciliation!**

When tracking where harvest weight went:
- Don't assume `endpoint_source='active'` means package still exists
- Check `is_finished` and `finished_date` to see if weight was consumed
- Consider packages finished AFTER harvest but BEFORE sync window

## Mitigation Strategies

1. **Use the views** - They implement correct filtering logic
2. **Periodic full syncs** - Without `lastModified` filter (expensive: ~1000s of API calls)
3. **Trust the flags** - `is_finished`, `is_archived` from API response
4. **Don't rely on endpoint names** - They indicate recency, not state

## Summary

| Column | Purpose | Use For |
|--------|---------|---------|
| `endpoint_source` | Debugging/tracking | Which API endpoint returned data |
| `is_finished` | ✅ Business Logic | Is package actually finished? |
| `is_archived` | ✅ Business Logic | Is package actually archived? |
| `finished_date` | ✅ Business Logic | When was it finished? |
| `archived_date` | ✅ Business Logic | When was it archived? |

**Remember**: The Metrc API is optimized for incremental syncs (efficiency), not accurate state filtering (accuracy). Always use status flags, never endpoint names.
