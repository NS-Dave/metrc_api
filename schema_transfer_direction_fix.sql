-- ===========================================================================
-- REVISED TRANSFER SCHEMA - DIRECTION-AWARE DESIGN
-- Addresses deduplication and direction tracking issues
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- OPTION 1: Add direction column with composite unique constraint
-- (Recommended - keeps single table but properly tracks direction)
-- ---------------------------------------------------------------------------

-- Drop existing unique constraint if it exists
ALTER TABLE metrc_transfers DROP CONSTRAINT IF EXISTS metrc_transfers_manifest_number_key;

-- Add direction column
ALTER TABLE metrc_transfers 
ADD COLUMN IF NOT EXISTS direction TEXT CHECK (direction IN ('incoming', 'outgoing'));

-- Create composite unique constraint
-- Same transfer ID can exist twice: once incoming, once outgoing
ALTER TABLE metrc_transfers 
ADD CONSTRAINT metrc_transfers_id_license_direction_unique 
UNIQUE (id, license_number, direction);

-- Index for efficient direction filtering
CREATE INDEX IF NOT EXISTS idx_transfers_direction ON metrc_transfers(direction, license_number);

-- ---------------------------------------------------------------------------
-- Update metrc_transfer_packages to include direction context
-- ---------------------------------------------------------------------------

ALTER TABLE metrc_transfer_packages
ADD COLUMN IF NOT EXISTS direction TEXT CHECK (direction IN ('incoming', 'outgoing'));

-- Update foreign key relationship to include direction
ALTER TABLE metrc_transfer_packages DROP CONSTRAINT IF EXISTS fk_transfer_packages_transfer;
ALTER TABLE metrc_transfer_packages 
ADD CONSTRAINT fk_transfer_packages_transfer 
FOREIGN KEY (transfer_id, direction) 
REFERENCES metrc_transfers(id, direction);

-- ---------------------------------------------------------------------------
-- Add full package reference columns
-- To link transfer packages to main packages table for enrichment
-- ---------------------------------------------------------------------------

ALTER TABLE metrc_transfer_packages
ADD COLUMN IF NOT EXISTS full_package_fetched BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS full_package_fetch_attempted_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS full_package_fetch_error TEXT;

-- Index for finding packages that need full data fetch
CREATE INDEX IF NOT EXISTS idx_transfer_packages_needs_fetch 
ON metrc_transfer_packages(full_package_fetched, package_id) 
WHERE full_package_fetched = FALSE AND package_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- MIGRATION NOTES
-- ---------------------------------------------------------------------------

/*
TO MIGRATE EXISTING DATA:

1. Add direction column (done above)

2. Populate direction for existing records:
   
   UPDATE metrc_transfers SET direction = 
     CASE 
       WHEN shipper_facility_license_number = license_number THEN 'outgoing'
       WHEN destination_facility_license_number = license_number THEN 'incoming'
       ELSE 'outgoing'  -- default assumption
     END
   WHERE direction IS NULL;

3. Handle duplicates that violate new constraint:
   
   -- Find actual duplicates (same ID + license + direction)
   SELECT id, license_number, direction, COUNT(*) 
   FROM metrc_transfers 
   GROUP BY id, license_number, direction 
   HAVING COUNT(*) > 1;
   
   -- Keep most recent sync, delete older duplicates
   DELETE FROM metrc_transfers t1
   WHERE EXISTS (
     SELECT 1 FROM metrc_transfers t2
     WHERE t2.id = t1.id 
     AND t2.license_number = t1.license_number
     AND t2.direction = t1.direction
     AND t2.synced_at > t1.synced_at
   );

4. Update transfer_packages direction:
   
   UPDATE metrc_transfer_packages tp
   SET direction = t.direction
   FROM metrc_transfers t
   WHERE tp.transfer_id = t.id;

5. Apply the unique constraint (after cleaning duplicates):
   
   ALTER TABLE metrc_transfers 
   ADD CONSTRAINT metrc_transfers_id_license_direction_unique 
   UNIQUE (id, license_number, direction);

*/

-- ---------------------------------------------------------------------------
-- ALTERNATIVE OPTION 2: Separate tables (if preferred)
-- ---------------------------------------------------------------------------

/*
CREATE TABLE metrc_transfers_incoming AS 
SELECT * FROM metrc_transfers 
WHERE destination_facility_license_number IN ('MP281433', 'MC281599');

CREATE TABLE metrc_transfers_outgoing AS 
SELECT * FROM metrc_transfers 
WHERE shipper_facility_license_number IN ('MP281433', 'MC281599');

-- Then drop original table and use view for backwards compatibility
CREATE VIEW metrc_transfers AS
  SELECT *, 'incoming' as direction FROM metrc_transfers_incoming
  UNION ALL
  SELECT *, 'outgoing' as direction FROM metrc_transfers_outgoing;
*/

-- ---------------------------------------------------------------------------
-- Views for convenience
-- ---------------------------------------------------------------------------

-- Incoming transfers with package details
CREATE OR REPLACE VIEW transfers_incoming_with_packages AS
SELECT 
    t.*,
    COUNT(tp.id) as package_count_detailed,
    SUM(tp.wholesale_price) as total_wholesale_value,
    SUM(tp.quantity_received) as total_quantity_received
FROM metrc_transfers t
LEFT JOIN metrc_transfer_packages tp ON tp.transfer_id = t.id AND tp.direction = 'incoming'
WHERE t.direction = 'incoming'
GROUP BY t.id;

-- Outgoing transfers with package details
CREATE OR REPLACE VIEW transfers_outgoing_with_packages AS
SELECT 
    t.*,
    COUNT(tp.id) as package_count_detailed,
    SUM(tp.wholesale_price) as total_wholesale_value,
    SUM(tp.quantity_shipped) as total_quantity_shipped
FROM metrc_transfers t
LEFT JOIN metrc_transfer_packages tp ON tp.transfer_id = t.id AND tp.direction = 'outgoing'
WHERE t.direction = 'outgoing'
GROUP BY t.id;

-- Packages needing full data enrichment
CREATE OR REPLACE VIEW transfer_packages_needing_enrichment AS
SELECT 
    tp.*,
    t.manifest_number,
    t.shipper_facility_license_number,
    t.destination_facility_license_number
FROM metrc_transfer_packages tp
JOIN metrc_transfers t ON t.id = tp.transfer_id AND t.direction = tp.direction
WHERE tp.package_id IS NOT NULL
  AND (tp.full_package_fetched = FALSE OR tp.full_package_fetched IS NULL)
  AND (tp.full_package_fetch_attempted_at IS NULL 
       OR tp.full_package_fetch_attempted_at < NOW() - INTERVAL '7 days');
