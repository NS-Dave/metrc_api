-- Migration: Rename package_status to endpoint_source and add is_archived flag
-- This clarifies that the column tracks which API endpoint returned the data,
-- not the actual status of the package.
--
-- To determine actual package status, use:
--   - is_finished (boolean flag from API)
--   - finished_date (date field)
--   - archived_date (date field)
--   - is_on_hold (boolean flag from API)

-- Step 1: Add is_archived column to track archived status flag
ALTER TABLE metrc_packages 
ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN metrc_packages.is_archived IS 
'Boolean flag from Metrc API indicating if package is archived. Use this instead of endpoint_source for filtering.';

-- Step 2: Rename package_status to endpoint_source
-- Check if old column exists before renaming
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'metrc_packages' 
        AND column_name = 'package_status'
    ) THEN
        ALTER TABLE metrc_packages 
        RENAME COLUMN package_status TO endpoint_source;
    END IF;
END $$;

COMMENT ON COLUMN metrc_packages.endpoint_source IS 
'Tracks which API endpoint returned this package data (active/inactive/intransit/transferred). 
WARNING: Do NOT use for filtering active packages - use is_finished, finished_date, archived_date instead.';

-- Step 3: Update the enum type name to reflect new purpose
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'package_status_type') THEN
        ALTER TYPE package_status_type RENAME TO endpoint_source_type;
    END IF;
EXCEPTION
    WHEN undefined_object THEN
        -- Type doesn't exist, create it
        CREATE TYPE endpoint_source_type AS ENUM ('active', 'inactive', 'intransit', 'transferred');
END $$;

-- Step 4: Create index on new is_archived column
CREATE INDEX IF NOT EXISTS idx_packages_archived 
ON metrc_packages(is_archived) 
WHERE is_archived = false;

-- Step 5: Create a view for truly active packages (matching Metrc UI)
CREATE OR REPLACE VIEW active_packages AS
SELECT *
FROM metrc_packages
WHERE is_finished = false
  AND archived_date IS NULL
  AND (is_archived = false OR is_archived IS NULL);

COMMENT ON VIEW active_packages IS 
'Packages that are truly active (not finished, not archived).
This matches the Metrc UI "Active Packages" view.
Use this instead of filtering by endpoint_source = ''active''.';

-- Step 6: Create a view for available inventory (active packages with quantity)
CREATE OR REPLACE VIEW available_inventory AS
SELECT *
FROM metrc_packages
WHERE is_finished = false
  AND archived_date IS NULL
  AND (is_archived = false OR is_archived IS NULL)
  AND quantity > 0;

COMMENT ON VIEW available_inventory IS 
'Active packages with remaining quantity (available inventory).';

-- Step 7: Create a view for in-transit packages (based on actual state, not endpoint)
CREATE OR REPLACE VIEW intransit_packages AS
SELECT *
FROM metrc_packages
WHERE endpoint_source = 'intransit'
  OR (received_from_manifest_number IS NOT NULL AND received_datetime IS NULL);

COMMENT ON VIEW intransit_packages IS 
'Packages currently in transit (on manifests but not yet received).';

-- Step 8: Update is_archived for existing records from the JSON data
UPDATE metrc_packages
SET is_archived = COALESCE((data->>'IsArchived')::boolean, false)
WHERE is_archived IS NULL OR is_archived = false;

-- Verify migration
DO $$
DECLARE
    active_count INT;
    finished_count INT;
    archived_count INT;
BEGIN
    SELECT COUNT(*) INTO active_count
    FROM active_packages;
    
    SELECT COUNT(*) INTO finished_count
    FROM metrc_packages WHERE is_finished = true;
    
    SELECT COUNT(*) INTO archived_count
    FROM metrc_packages WHERE is_archived = true;
    
    RAISE NOTICE 'Migration complete!';
    RAISE NOTICE '  Active packages (view): %', active_count;
    RAISE NOTICE '  Finished packages: %', finished_count;
    RAISE NOTICE '  Archived packages: %', archived_count;
END $$;
