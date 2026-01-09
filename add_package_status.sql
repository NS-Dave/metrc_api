-- Add package_status column to track which Metrc endpoint returned the package
-- This is more reliable than inferring status from fields

-- Add status enum type
DO $$ BEGIN
    CREATE TYPE package_status_type AS ENUM ('active', 'inactive', 'intransit');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add column with default 'active' for existing records
ALTER TABLE metrc_packages 
ADD COLUMN IF NOT EXISTS package_status package_status_type DEFAULT 'active';

-- Add index for common queries
CREATE INDEX IF NOT EXISTS idx_packages_status 
ON metrc_packages(license_number, package_status, finished_date, archived_date);

-- Add comment
COMMENT ON COLUMN metrc_packages.package_status IS 
'Source endpoint: active (v2/active), inactive (v2/inactive), or intransit (v2/intransit). Updated on each sync.';
