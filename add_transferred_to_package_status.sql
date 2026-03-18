-- Add 'transferred' value to package_status_type enum
-- This allows tracking packages from the packages/GetTransferred endpoint

-- Add the new enum value
ALTER TYPE package_status_type ADD VALUE IF NOT EXISTS 'transferred';

-- Add comment
COMMENT ON TYPE package_status_type IS 
'Source endpoint: active (v2/active), inactive (v2/inactive), intransit (v2/intransit), or transferred (GetTransferred). Updated on each sync.';

-- Update the comment on the column as well
COMMENT ON COLUMN metrc_packages.package_status IS 
'Source endpoint: active (v2/active), inactive (v2/inactive), intransit (v2/intransit), or transferred (GetTransferred). Updated on each sync.';
