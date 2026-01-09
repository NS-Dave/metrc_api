# Transfer Schema Migration Plan

## Problem Summary

**Current Issues:**
1. ❌ Incoming and outgoing transfers stored together without direction tracking
2. ❌ Deduplication by transfer ID only (should be ID + direction)
3. ❌ Same transfer ID can't exist as both incoming and outgoing
4. ❌ Transfer packages only have minimal data from `/deliveries/{id}/packages/wholesale`
5. ❌ Missing full package details available from `/packages/v2/{id}`

**Impact:**
- Data conflicts when same transfer appears as incoming AND outgoing
- Incomplete package information for outgoing shipments
- Cannot properly distinguish sales vs purchases
- Missing product details, THC/CBD, quantities, harvest traceability

---

## Solution Design

### Schema Changes

**Add direction column:**
```sql
ALTER TABLE metrc_transfers 
ADD COLUMN direction TEXT CHECK (direction IN ('incoming', 'outgoing'));

ALTER TABLE metrc_transfer_packages
ADD COLUMN direction TEXT CHECK (direction IN ('incoming', 'outgoing'));
```

**Change unique constraint:**
```sql
-- OLD: UNIQUE(manifest_number) or PRIMARY KEY(id)
-- NEW: UNIQUE(id, license_number, direction)

-- This allows:
-- - Transfer 123 as incoming for MP281433
-- - Transfer 123 as outgoing for MC281599 (if we have both licenses involved)
```

**Add package enrichment tracking:**
```sql
ALTER TABLE metrc_transfer_packages
ADD COLUMN full_package_fetched BOOLEAN DEFAULT FALSE,
ADD COLUMN full_package_fetch_attempted_at TIMESTAMPTZ,
ADD COLUMN full_package_fetch_error TEXT;
```

### Logic Changes

**1. Fetching:**
```python
# OLD: Combine incoming + outgoing, dedupe by ID
all_transfers = incoming + outgoing
unique = deduplicate_by_id(all_transfers)

# NEW: Keep separate, store with direction tag
store_with_direction(incoming, 'incoming')
store_with_direction(outgoing, 'outgoing')
```

**2. Deduplication:**
```python
# OLD: Unique by transfer_id only
seen_ids = {transfer['Id'] for transfer in transfers}

# NEW: Unique by (transfer_id, license, direction)
# Dedupe within each direction, but same ID can exist in both
```

**3. Package Enrichment:**
```python
# OLD: Only /transfers/v2/deliveries/{id}/packages/wholesale
#      Returns: PackageId, PackageLabel, WholesalePrice only

# NEW: Fetch from /packages/v2/{package_id}  
#      Returns: Full package object with all fields
```

---

## Migration Steps

### Option A: Clean Slate (Recommended if data is not production-critical)

```sql
-- 1. Backup existing data
CREATE TABLE metrc_transfers_backup AS SELECT * FROM metrc_transfers;
CREATE TABLE metrc_transfer_packages_backup AS SELECT * FROM metrc_transfer_packages;

-- 2. Drop existing tables
DROP TABLE metrc_transfer_packages CASCADE;
DROP TABLE metrc_transfers CASCADE;

-- 3. Run new schema: schema_transfers_clean_slate.sql
-- (Copy contents of schema_transfers_clean_slate.sql and run in Supabase SQL Editor)

-- 4. Re-sync all data with new direction-aware logic
-- Run: python transfer_sync_direction_aware.py
```

**Pros:**
- Clean implementation
- No data conflicts
- Faster than migration

**Cons:**
- Loses historical sync data (can be re-pulled from API)

---

### Option B: In-Place Migration (If preserving data is critical)

```sql
-- STEP 1: Add direction column
ALTER TABLE metrc_transfers 
ADD COLUMN direction TEXT;

ALTER TABLE metrc_transfer_packages
ADD COLUMN direction TEXT;

-- STEP 2: Populate direction for existing records
-- This is best-effort based on shipper vs destination matching your licenses
UPDATE metrc_transfers SET direction = 
  CASE 
    WHEN shipper_facility_license_number IN ('MP281433', 'MC281599') 
         AND destination_facility_license_number NOT IN ('MP281433', 'MC281599')
    THEN 'outgoing'
    WHEN destination_facility_license_number IN ('MP281433', 'MC281599')
         AND shipper_facility_license_number NOT IN ('MP281433', 'MC281599')  
    THEN 'incoming'
    ELSE 'outgoing'  -- default assumption for unclear cases
  END
WHERE direction IS NULL;

-- STEP 3: Update transfer_packages direction from parent transfer
UPDATE metrc_transfer_packages tp
SET direction = t.direction
FROM metrc_transfers t
WHERE tp.transfer_id = t.id;

-- STEP 4: Find and resolve duplicates
-- Identify duplicates that will violate new constraint
WITH duplicates AS (
  SELECT id, license_number, direction, COUNT(*) as cnt
  FROM metrc_transfers 
  GROUP BY id, license_number, direction 
  HAVING COUNT(*) > 1
)
SELECT * FROM duplicates;

-- Keep most recent, delete older
DELETE FROM metrc_transfers t1
WHERE EXISTS (
  SELECT 1 FROM metrc_transfers t2
  WHERE t2.id = t1.id 
  AND t2.license_number = t1.license_number
  AND t2.direction = t1.direction
  AND t2.synced_at > t1.synced_at
);

-- STEP 5: Drop old constraints
ALTER TABLE metrc_transfers DROP CONSTRAINT IF EXISTS metrc_transfers_pkey;
ALTER TABLE metrc_transfers DROP CONSTRAINT IF EXISTS metrc_transfers_manifest_number_key;

-- STEP 6: Add new composite unique constraint
ALTER TABLE metrc_transfers 
ADD CONSTRAINT metrc_transfers_id_license_direction_unique 
UNIQUE (id, license_number, direction);

-- STEP 7: Add NOT NULL constraint after data is populated
ALTER TABLE metrc_transfers 
ALTER COLUMN direction SET NOT NULL;

ALTER TABLE metrc_transfer_packages
ALTER COLUMN direction SET NOT NULL;

-- STEP 8: Add package enrichment columns
ALTER TABLE metrc_transfer_packages
ADD COLUMN full_package_fetched BOOLEAN DEFAULT FALSE,
ADD COLUMN full_package_fetch_attempted_at TIMESTAMPTZ,
ADD COLUMN full_package_fetch_error TEXT;

-- STEP 9: Create indexes
CREATE INDEX idx_transfers_direction ON metrc_transfers(direction, license_number);
CREATE INDEX idx_transfer_packages_needs_fetch 
ON metrc_transfer_packages(full_package_fetched, package_id) 
WHERE full_package_fetched = FALSE AND package_id IS NOT NULL;
```

**Pros:**
- Preserves existing data
- Gradual migration

**Cons:**
- More complex
- Risk of data conflicts
- Direction assignment may be incorrect for edge cases

---

## Post-Migration Tasks

### 1. Update sync scripts
Replace `metrc_daily_sync.py` transfer sync logic with `transfer_sync_direction_aware.py`

### 2. Enrich historical outgoing packages
```python
# Run enrichment for existing outgoing transfers
syncer = DirectionAwareTransferSync()
syncer.enrich_outgoing_transfer_packages(PROCESSING_LICENSE, limit=1000)
syncer.enrich_outgoing_transfer_packages(CULTIVATION_LICENSE, limit=1000)
```

### 3. Update queries
```sql
-- OLD: Filter by license only
SELECT * FROM metrc_transfers WHERE license_number = 'MP281433';

-- NEW: Filter by direction too
SELECT * FROM metrc_transfers 
WHERE license_number = 'MP281433' AND direction = 'outgoing';
```

### 4. Verify data integrity
```sql
-- Check all transfers have direction
SELECT COUNT(*) FROM metrc_transfers WHERE direction IS NULL;

-- Check for unexpected duplicates
SELECT id, license_number, direction, COUNT(*) 
FROM metrc_transfers 
GROUP BY id, license_number, direction 
HAVING COUNT(*) > 1;

-- Check package enrichment status
SELECT 
  direction,
  COUNT(*) as total_packages,
  SUM(CASE WHEN full_package_fetched THEN 1 ELSE 0 END) as enriched,
  SUM(CASE WHEN full_package_fetched THEN 0 ELSE 1 END) as needs_enrichment
FROM metrc_transfer_packages
GROUP BY direction;
```

---

## Recommendation

**For development/testing:** Use **Option A (Clean Slate)**
- Fastest implementation
- Cleanest data
- Can re-sync from API

**For production:** Use **Option B (In-Place Migration)**
- Preserves historical data
- More careful transition
- Better audit trail

---

## Timeline Estimate

**Option A:** 
- Schema changes: 5 minutes
- Re-sync data: 2-4 hours (depending on date range)
- Total: ~4 hours

**Option B:**
- Migration script execution: 30 minutes
- Data validation: 1 hour
- Incremental enrichment: Ongoing background task
- Total: 1.5 hours initial + ongoing enrichment

---

## Testing Plan

1. ✅ Run migration on test database first
2. ✅ Verify direction assignment is correct
3. ✅ Test sync with new logic
4. ✅ Verify no duplicate key violations
5. ✅ Test package enrichment from /packages/v2/{id}
6. ✅ Validate query results for incoming vs outgoing
7. ✅ Compare record counts before/after

---

## Rollback Plan

If migration fails:

```sql
-- Restore from backup
DROP TABLE metrc_transfers;
DROP TABLE metrc_transfer_packages;

CREATE TABLE metrc_transfers AS SELECT * FROM metrc_transfers_backup;
CREATE TABLE metrc_transfer_packages AS SELECT * FROM metrc_transfer_packages_backup;

-- Recreate indexes and constraints
-- (Run original schema file)
```
