# Package History Tracking - Implementation Guide

## Overview

Track every change to package state over time using a history table. This solves the "white whale" problem of tracking package journeys through their production lifecycle.

## Architecture

```
metrc_packages (current state)  ←  Fast queries for "what is it now?"
        ↓
metrc_packages_history          ←  Complete timeline for "what was it then?"
```

### Design Pattern: Slowly Changing Dimension Type 2 (SCD2)

- **Current state**: `metrc_packages` table (one row per package)
- **History**: `metrc_packages_history` table (many rows per package, one per change)
- **Temporal tracking**: `valid_from` and `valid_to` timestamps

## Data Volume

✅ **Highly Feasible**:
- Current: ~15,421 packages
- Daily changes: ~810 packages/day
- Annual growth: ~296K history rows/year
- Storage: < 1 GB/year

## Installation

### Step 1: Create History Table

```bash
# Run the migration SQL
psql -h <host> -U <user> -d <database> -f schema_package_history.sql
```

Or in Python:
```python
python run_history_migration.py
```

This creates:
- `metrc_packages_history` table
- Helper views and functions
- Initial snapshot of current state

### Step 2: Enable History Capture (Optional)

To automatically capture changes on every sync, integrate `package_history.py` into `metrc_daily_sync.py`:

```python
from package_history import capture_history_before_update, create_initial_history_entry

# In upsert_packages(), before updating:
if exists:
    capture_history_before_update(cursor, package_label, new_data, datetime.now())
    # ... then do UPDATE
else:
    # ... do INSERT
    create_initial_history_entry(cursor, data, datetime.now())
```

## Query Examples

### 1. Get Package Timeline

```sql
-- See all changes to a specific package
SELECT * FROM get_package_timeline('1A40A030000C289000029893');

-- Result:
-- change_time              | change_type      | quantity | is_finished
-- 2025-01-01 10:00:00     | created          | 350.0    | false
-- 2025-01-05 14:30:00     | quantity_change  | 250.0    | false
-- 2025-01-10 16:00:00     | quantity_change  | 100.0    | false
-- 2025-01-15 12:00:00     | state_change     | 100.0    | true
```

### 2. Get Package State at Specific Time

```sql
-- What was this package like on December 1st?
SELECT * FROM get_package_at_time(
    '1A40A030000C289000029893', 
    '2025-12-01'::timestamptz
);
```

### 3. Track Quantity Changes

```sql
-- See how quantity changed over time
SELECT 
    valid_from as change_time,
    quantity,
    quantity - LAG(quantity) OVER (ORDER BY valid_from) as quantity_delta,
    location_name
FROM metrc_packages_history
WHERE label = '1A40A030000C289000029893'
ORDER BY valid_from;
```

### 4. Find When Package Was Finished

```sql
-- When did this package transition to finished?
SELECT 
    label,
    valid_from as finished_time,
    quantity as final_quantity,
    location_name
FROM metrc_packages_history
WHERE label = '1A40A030000C289000029893'
  AND is_finished = true
ORDER BY valid_from
LIMIT 1;
```

### 5. Packages That Changed Today

```sql
-- What packages changed state today?
SELECT DISTINCT
    label,
    change_type,
    changed_fields,
    valid_from
FROM metrc_packages_history
WHERE DATE(valid_from) = CURRENT_DATE
  AND change_type IN ('state_change', 'quantity_change')
ORDER BY valid_from DESC;
```

### 6. Package Journey Visualization

```sql
-- Complete journey of a package from creation to finish
SELECT 
    valid_from::date as date,
    CASE 
        WHEN is_finished THEN 'Finished'
        WHEN is_archived THEN 'Archived'
        WHEN is_on_hold THEN 'On Hold'
        WHEN endpoint_source = 'intransit' THEN 'In Transit'
        WHEN endpoint_source = 'transferred' THEN 'Transferred'
        ELSE 'Active'
    END as status,
    quantity,
    location_name,
    changed_fields
FROM metrc_packages_history
WHERE label = '1A40A030000C289000029893'
ORDER BY valid_from;
```

### 7. Harvest Weight Reconciliation Over Time

```sql
-- Track where harvest weight went over time
WITH harvest_packages AS (
    SELECT 
        h.valid_from,
        h.label,
        h.quantity,
        h.source_harvest_names,
        h.is_finished
    FROM metrc_packages_history h
    WHERE h.source_harvest_names LIKE '%ILLI #8 R4C60 8/15/25%'
)
SELECT 
    DATE(valid_from) as date,
    COUNT(*) as package_count,
    SUM(quantity) FILTER (WHERE NOT is_finished) as active_quantity,
    SUM(quantity) FILTER (WHERE is_finished) as finished_quantity,
    SUM(quantity) as total_quantity
FROM harvest_packages
GROUP BY DATE(valid_from)
ORDER BY date;
```

### 8. Packages That Disappeared (Quantity → 0)

```sql
-- Find packages that had quantity go to zero
SELECT 
    h1.label,
    h1.valid_from as when_depleted,
    h2.quantity as previous_quantity,
    h1.location_name
FROM metrc_packages_history h1
JOIN metrc_packages_history h2 
    ON h1.label = h2.label 
    AND h2.valid_from = (
        SELECT MAX(valid_from) 
        FROM metrc_packages_history 
        WHERE label = h1.label 
        AND valid_from < h1.valid_from
    )
WHERE h1.quantity = 0
  AND h2.quantity > 0
  AND h1.valid_from >= NOW() - INTERVAL '30 days'
ORDER BY h1.valid_from DESC;
```

### 9. State Transition Report

```sql
-- How many packages transitioned to finished today?
SELECT 
    COUNT(*) as packages_finished_today
FROM metrc_packages_history
WHERE change_type = 'state_change'
  AND is_finished = true
  AND DATE(valid_from) = CURRENT_DATE;
```

### 10. Audit Trail for Compliance

```sql
-- Complete audit trail for a package
SELECT 
    history_id,
    valid_from as timestamp,
    change_type,
    changed_fields,
    quantity,
    is_finished,
    is_archived,
    location_name,
    endpoint_source,
    data->>'LastModified' as api_last_modified
FROM metrc_packages_history
WHERE label = '1A40A030000C289000029893'
ORDER BY valid_from;
```

## Python Usage

```python
import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# Get package timeline
cursor.execute("""
    SELECT * FROM get_package_timeline(%s)
""", ('1A40A030000C289000029893',))

for row in cursor.fetchall():
    change_time, change_type, changed_fields, quantity, is_finished, is_archived, endpoint = row
    print(f"{change_time}: {change_type} - Qty: {quantity}, Finished: {is_finished}")

# Get state at specific time
cursor.execute("""
    SELECT * FROM get_package_at_time(%s, %s)
""", ('1A40A030000C289000029893', '2025-12-01'))

package_state = cursor.fetchone()
print(f"On 2025-12-01, package had quantity: {package_state[2]}")
```

## Performance Considerations

### Indexes Created

All necessary indexes are automatically created:
- `idx_packages_history_label` - Fast lookup by label
- `idx_packages_history_valid_range` - Temporal queries
- `idx_packages_history_state_changes` - State transition queries

### Query Performance

- Current state: Query `metrc_packages` (fastest)
- Package timeline: `get_package_timeline()` function (fast, uses indexes)
- Historical point-in-time: `get_package_at_time()` function (fast, uses indexes)
- Large scans: Use date filters to limit range

### Storage Management

Archive old history after compliance period:

```sql
-- Archive history older than 7 years (MA cannabis compliance requirement)
DELETE FROM metrc_packages_history
WHERE valid_from < NOW() - INTERVAL '7 years'
  AND is_current = false;
```

## Benefits

### 1. **Compliance & Audit**
- Complete audit trail for regulators
- Prove package state at any point in time
- Track chain of custody

### 2. **Harvest Reconciliation**
- See how package quantities changed over time
- Track consumption/transfers dynamically
- Identify weight discrepancies when they occurred

### 3. **Business Intelligence**
- Package lifecycle analytics
- Average time to finish
- Quantity consumption patterns
- Location movement tracking

### 4. **Debugging**
- "What changed and when?"
- Identify sync issues
- Compare API responses over time

## Limitations & Considerations

### 1. **Granularity**
- History captured at sync time (daily or 48-hour increments)
- Can't track changes between syncs
- For real-time tracking, increase sync frequency

### 2. **Data Volume**
- Current approach: ~296K rows/year
- If you want EVERY sync (even no-change): ~5.8M rows/year
- Trade-off: storage vs. granularity

### 3. **Initial State**
- First run captures current state as "initial_snapshot"
- Historical data before first run is lost
- Consider backfilling if needed

## Next Steps

1. **Run migration**: Create history table
2. **Test queries**: Try the examples above
3. **Integrate into sync** (optional): Auto-capture on updates
4. **Build dashboards**: Visualize package journeys
5. **Harvest reconciliation**: Use timeline data for weight tracking

This gives you the **complete package journey tracking** you've been looking for! 🎯
