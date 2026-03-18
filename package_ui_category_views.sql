-- Helper views for filtering packages by Metrc UI categories
-- These views match what users see in the Metrc web interface

-- Active packages (matches Metrc UI "Active Packages" tab)
CREATE OR REPLACE VIEW metrc_packages_active_ui AS
SELECT *
FROM metrc_packages
WHERE package_status = 'active'
  AND finished_date IS NULL
  AND archived_date IS NULL;

COMMENT ON VIEW metrc_packages_active_ui IS 
'Packages that appear in Metrc UI "Active Packages" tab. Excludes in-transit and finished packages.';


-- In-transit packages (matches Metrc UI "In-Transit" tab)
CREATE OR REPLACE VIEW metrc_packages_intransit_ui AS
SELECT *
FROM metrc_packages
WHERE package_status = 'intransit';

COMMENT ON VIEW metrc_packages_intransit_ui IS 
'Packages currently in-transit (incoming transfers not yet received). Matches Metrc UI "In-Transit" tab.';


-- Transferred packages (matches Metrc UI "Transferred" tab)
CREATE OR REPLACE VIEW metrc_packages_transferred_ui AS
SELECT *
FROM metrc_packages
WHERE package_status = 'transferred';

COMMENT ON VIEW metrc_packages_transferred_ui IS 
'Packages that appear in Metrc UI "Transferred" tab. Synced from packages/GetTransferred endpoint.';


-- Finished packages (matches Metrc UI "Finished" filter)
CREATE OR REPLACE VIEW metrc_packages_finished_ui AS
SELECT *
FROM metrc_packages
WHERE finished_date IS NOT NULL
   OR archived_date IS NOT NULL;

COMMENT ON VIEW metrc_packages_finished_ui IS 
'Packages marked as finished or archived. Matches Metrc UI when "Show Finished" filter is applied.';


-- Summary by license and category
CREATE OR REPLACE VIEW metrc_packages_summary AS
SELECT 
    license_number,
    COUNT(*) FILTER (WHERE package_status = 'active' AND finished_date IS NULL AND archived_date IS NULL) as active,
    COUNT(*) FILTER (WHERE package_status = 'intransit') as intransit,
    COUNT(*) FILTER (WHERE package_status = 'transferred') as transferred,
    COUNT(*) FILTER (WHERE package_status = 'inactive' AND finished_date IS NULL AND archived_date IS NULL) as inactive,
    COUNT(*) FILTER (WHERE finished_date IS NOT NULL OR archived_date IS NOT NULL) as finished,
    COUNT(*) as total
FROM metrc_packages
GROUP BY license_number;

COMMENT ON VIEW metrc_packages_summary IS 
'Summary counts of packages by category for each license. Useful for dashboard/reporting.';


-- Example usage after creating views:
/*

-- Get active packages for cultivation license (matches Metrc UI)
SELECT * FROM metrc_packages_active_ui 
WHERE license_number = 'MC281599';

-- Get in-transit packages
SELECT * FROM metrc_packages_intransit_ui
WHERE license_number = 'MC281599';

-- Get transferred packages  
SELECT * FROM metrc_packages_transferred_ui
WHERE license_number = 'MC281599';

-- Get summary dashboard
SELECT * FROM metrc_packages_summary;

*/
