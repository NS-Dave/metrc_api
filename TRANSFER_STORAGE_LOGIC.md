# Transfer Storage Logic - Detailed Analysis

## Overview
Both **incoming** and **outgoing** transfers ARE stored in the same `metrc_transfers` table. The table uses a **single primary key** (`id`) which is Metrc's transfer ID, so duplicates are automatically handled.

---

## Data Flow Architecture

### 1. **API Fetching** (Daily Sync & Historical Backfill)

**Endpoints Called:**
```python
# Daily sync (last 7 days, in 24-hour chunks):
/transfers/v2/incoming?lastModifiedStart={date}&lastModifiedEnd={date}
/transfers/v2/outgoing?lastModifiedStart={date}&lastModifiedEnd={date}

# Historical backfill (30-day windows):
/transfers/v2/incoming?lastModifiedStart={date}&lastModifiedEnd={date}  
/transfers/v2/outgoing?lastModifiedStart={date}&lastModifiedEnd={date}
```

**Code Location:** `metrc_daily_sync.py` lines 527-562
```python
# Get incoming transfers
incoming_response = self.processing.get_incoming_transfers(
    license_number=license_number,
    last_modified_start=start_str,
    last_modified_end=end_str
)
incoming = incoming_response['Data'] if isinstance(incoming_response, dict) else []

# Get outgoing transfers
outgoing_response = self.processing.get_outgoing_transfers(
    license_number=license_number,
    last_modified_start=start_str,
    last_modified_end=end_str
)
outgoing = outgoing_response['Data'] if isinstance(outgoing_response, dict) else []

# COMBINE both into single list
all_transfers.extend(incoming + outgoing)
```

---

### 2. **Deduplication Logic**

**Why Needed:** 
A transfer can appear in BOTH incoming and outgoing results if:
- License A ships to License B
- You have access to both licenses
- Transfer appears in "outgoing" for License A AND "incoming" for License B

**Code Location:** `metrc_daily_sync.py` lines 565-571
```python
# Remove duplicates based on Id
seen_ids = set()
unique_transfers = []
for transfer in all_transfers:
    if transfer['Id'] not in seen_ids:
        seen_ids.add(transfer['Id'])
        unique_transfers.append(transfer)
```

**Result:** Each unique transfer (by Metrc ID) appears only once in the list going to database.

---

### 3. **Database Storage (Upsert Logic)**

**Primary Key:** `id` (Metrc's transfer ID)
**Unique Constraint:** `manifest_number` (transfer manifest)

**Code Location:** `metrc_historical_backfill.py` lines 312-427
```python
def upsert_transfers(self, transfers: List[Dict], license_number: str):
    for transfer in transfers:
        # Check if exists by ID
        cursor.execute("SELECT data FROM metrc_transfers WHERE id = %s", (transfer['Id'],))
        exists = cursor.fetchone() is not None
        
        if exists:
            UPDATE metrc_transfers WHERE id = %(id)s
        else:
            INSERT INTO metrc_transfers VALUES (...)
```

**Key Behavior:**
- **INSERT:** If transfer ID doesn't exist → new record
- **UPDATE:** If transfer ID exists → update all fields
- **Preservation:** If updating and old record has Deliveries but new doesn't → preserve old Deliveries

---

## What Distinguishes Incoming vs Outgoing?

### The table does NOT have an explicit "direction" column!

**Direction is determined by querying these fields:**

| Scenario | Shipper License | Destination License | Direction Interpretation |
|----------|----------------|---------------------|-------------------------|
| **Outgoing** | = Your License | ≠ Your License | You shipped it out |
| **Incoming** | ≠ Your License | = Your License | You received it |
| **Internal** | = Your License | = Your License | Transfer between your facilities |

**Query Examples:**

```sql
-- Outgoing transfers (we shipped)
SELECT * FROM metrc_transfers 
WHERE shipper_facility_license_number = 'MP281433';

-- Incoming transfers (we received)
SELECT * FROM metrc_transfers 
WHERE destination_facility_license_number = 'MP281433';

-- All transfers touching our license
SELECT * FROM metrc_transfers 
WHERE shipper_facility_license_number = 'MP281433' 
   OR destination_facility_license_number = 'MP281433';
```

---

## Schema Fields That Identify Direction

```sql
CREATE TABLE metrc_transfers (
    id BIGINT PRIMARY KEY,
    manifest_number TEXT NOT NULL,
    license_number TEXT NOT NULL,  -- License used to fetch this transfer
    
    -- SENDER INFO
    shipper_facility_name TEXT,
    shipper_facility_license_number TEXT,  -- ← Key: who sent it
    
    -- TRANSPORT INFO
    transporter_facility_name TEXT,
    transporter_facility_license_number TEXT,
    
    -- RECIPIENT INFO  
    destination_facility_name TEXT,
    destination_facility_license_number TEXT,  -- ← Key: who received it
    
    -- ... other fields
)
```

---

## Storage Architecture Summary

### ✅ **What IS Filtered:**
1. **Duplicates:** Same transfer appearing in both incoming/outgoing API responses
2. **Time windows:** Only transfers modified within the sync date range
3. **License scope:** Only transfers involving the specified license number

### ✅ **What IS Combined:**
1. **Incoming + Outgoing:** Merged into single list before dedup
2. **Multiple licenses:** If syncing both MP281433 and MC281599, transfers from both go into same table
3. **Deliveries preservation:** When updating, existing delivery data is preserved if new data lacks it

### ❌ **What is NOT Stored Separately:**
1. ~~No separate tables for incoming vs outgoing~~
2. ~~No direction flag column~~
3. ~~No filtering by transfer type during storage~~

---

## Child Tables (Package Details)

### `metrc_transfer_packages`
- **Parent Key:** `transfer_id` (references `metrc_transfers.id`)
- **Purpose:** Package-level details with wholesale pricing
- **Populated by:** 
  - Daily sync: `/transfers/v2/deliveries/{id}/packages/wholesale`
  - Enrichment scripts for historical data

### `metrc_transfer_transporters` (future)
- **Parent Key:** `transfer_id` (references `metrc_transfers.id`)
- **Purpose:** Driver, vehicle, route details
- **Populated by:** `/transfers/v2/deliveries/{id}/transporters`

---

## Practical Implications

### **Analytics Queries Need Direction Logic**

```sql
-- Wholesale sales (outgoing transfers)
SELECT 
    COUNT(*) as transfer_count,
    SUM(package_count) as total_packages
FROM metrc_transfers
WHERE shipper_facility_license_number = 'MP281433'
AND transfer_type = 'Wholesale';

-- Purchases (incoming transfers)  
SELECT 
    COUNT(*) as transfer_count,
    SUM(package_count) as total_packages
FROM metrc_transfers
WHERE destination_facility_license_number = 'MP281433'
AND transfer_type = 'Wholesale';

-- Revenue from outgoing wholesale transfers
SELECT 
    t.manifest_number,
    t.destination_facility_name,
    SUM(tp.wholesale_price) as total_wholesale_value
FROM metrc_transfers t
JOIN metrc_transfer_packages tp ON tp.transfer_id = t.id
WHERE t.shipper_facility_license_number = 'MP281433'
GROUP BY t.id, t.manifest_number, t.destination_facility_name;
```

### **Deduplication Happens At:**
1. **API level:** Combine incoming + outgoing arrays
2. **In-memory:** Deduplicate by transfer ID before database insert
3. **Database level:** Primary key constraint prevents duplicate IDs

### **License_number Field Purpose:**
- Tracks which license was used to fetch this transfer from API
- Does NOT indicate direction
- Useful for sync tracking and troubleshooting

---

## Edge Cases Handled

1. **Transfer appears in both incoming/outgoing:** 
   - ✅ Deduplicated by ID, stored once
   
2. **Same transfer synced multiple times:**
   - ✅ UPDATE existing record (preserves Deliveries if present)
   
3. **Transfer has no Deliveries in API response:**
   - ✅ Preserved from previous sync if available
   - ✅ Can be enriched later via `/deliveries/{id}/packages/wholesale`
   
4. **Multi-license environment:**
   - ✅ All transfers go to same table
   - ✅ Direction determined by shipper_license vs destination_license comparison

---

## Recommendation: Add Direction Column?

**Current state:** Direction is implicit (requires JOIN logic in queries)

**Option to improve:** Add computed column for clarity
```sql
ALTER TABLE metrc_transfers 
ADD COLUMN direction TEXT GENERATED ALWAYS AS (
    CASE 
        WHEN shipper_facility_license_number IN ('MP281433', 'MC281599') 
             AND destination_facility_license_number NOT IN ('MP281433', 'MC281599')
        THEN 'outgoing'
        WHEN destination_facility_license_number IN ('MP281433', 'MC281599')
             AND shipper_facility_license_number NOT IN ('MP281433', 'MC281599')  
        THEN 'incoming'
        ELSE 'internal'
    END
) STORED;
```

**Benefit:** Simpler queries, faster filtering
**Downside:** Hardcoded license numbers (less flexible)
