-- ============================================================================
-- HARVEST RECONCILIATION SQL VIEWS
-- 
-- Purpose: SQL-based harvest reconciliation for export to spreadsheets
-- Philosophy: Calculate everything in SQL, export to Excel for review
-- ============================================================================

-- Drop existing views in reverse dependency order
DROP VIEW IF EXISTS v_complex_packages_detail CASCADE;
DROP VIEW IF EXISTS v_harvests_needing_review CASCADE;
DROP VIEW IF EXISTS v_harvest_reconciliation CASCADE;
DROP VIEW IF EXISTS v_package_detail CASCADE;
DROP VIEW IF EXISTS v_transfer_classification CASCADE;
DROP VIEW IF EXISTS v_package_categorization CASCADE;

-- 1. Package Categorization View
-- Categorizes each package by complexity and status
CREATE OR REPLACE VIEW v_package_categorization AS
SELECT 
    p.id,
    p.label,
    p.license_number,
    p.product_name,
    p.quantity,
    p.unit_of_measure,
    p.source_harvest_names,
    p.packaged_date,
    p.finished_date,
    p.archived_date,
    
    -- Parse source harvests
    string_to_array(p.source_harvest_names, ',') as source_harvest_array,
    array_length(string_to_array(p.source_harvest_names, ','), 1) as source_harvest_count,
    
    -- Package status
    CASE 
        WHEN p.finished_date IS NULL AND p.archived_date IS NULL THEN 'active'
        ELSE 'finished_or_archived'
    END as package_status,
    
    -- Package complexity
    CASE 
        WHEN array_length(string_to_array(p.source_harvest_names, ','), 1) = 1 THEN 'simple'
        WHEN array_length(string_to_array(p.source_harvest_names, ','), 1) > 1 THEN 'complex'
        ELSE 'unknown'
    END as package_complexity,
    
    p.last_modified
FROM metrc_packages p
WHERE p.source_harvest_names IS NOT NULL;

COMMENT ON VIEW v_package_categorization IS 
'Categorizes packages as simple (single harvest) or complex (multiple harvests), and active vs finished';


-- 2. Transfer Classification View
-- Identifies sale vs internal transfers
CREATE OR REPLACE VIEW v_transfer_classification AS
SELECT 
    tp.id,
    tp.package_label,
    tp.quantity_shipped,
    tp.unit_of_measure_name,
    t.id as transfer_id,
    t.manifest_number,
    t.shipment_type,
    t.destination_facility_name,
    t.shipper_facility_name,
    t.actual_departure_datetime as shipped_date,
    t.license_number,
    
    -- Transfer classification
    CASE 
        WHEN t.shipment_type IN ('Unaffiliated Transfer', 'Affiliated Transfer')
             AND t.destination_facility_name != '140 Industrial Road, LLC'
        THEN 'sale'
        WHEN t.destination_facility_name = '140 Industrial Road, LLC'
        THEN 'internal'
        ELSE 'other'
    END as transfer_type
    
FROM metrc_transfer_packages tp
JOIN metrc_transfers t ON tp.transfer_id = t.id;

COMMENT ON VIEW v_transfer_classification IS 
'Classifies transfers as sale (external) or internal (140 Industrial Road)';


-- 3. Package Detail View
-- Combines package info with transfer classification
CREATE OR REPLACE VIEW v_package_detail AS
SELECT 
    pc.*,
    tc.transfer_id,
    tc.manifest_number,
    tc.shipment_type,
    tc.destination_facility_name,
    tc.shipped_date,
    tc.transfer_type,
    tc.quantity_shipped
FROM v_package_categorization pc
LEFT JOIN v_transfer_classification tc 
    ON pc.label = tc.package_label
    AND pc.license_number = tc.license_number;

COMMENT ON VIEW v_package_detail IS 
'Complete package details with transfer classification';


-- 4. Harvest Reconciliation Summary
-- Main reconciliation view - one row per harvest
-- Filters: Only active harvests OR finished since 2025-01-01
CREATE OR REPLACE VIEW v_harvest_reconciliation AS
WITH harvest_packages AS (
    -- Get all packages for each harvest
    SELECT 
        h.id as harvest_id,
        h.harvest_name,
        h.license_number,
        h.harvest_type,
        h.source_strain_names as harvest_strain,
        h.total_packaged_weight as harvest_weight,
        h.unit_of_weight as harvest_unit,
        h.harvest_start_date as harvest_packaged_date,
        h.finished_date,
        h.is_finished as harvest_is_finished,
        
        -- Harvest status
        CASE 
            WHEN h.finished_date IS NULL THEN 'active'
            WHEN h.finished_date IS NOT NULL AND h.total_packaged_weight > 0 THEN 'finished'
            ELSE 'other'
        END as harvest_status,
        
        -- Count simple packages
        COUNT(*) FILTER (
            WHERE pc.package_complexity = 'simple'
        ) as simple_package_count,
        
        -- Simple active inventory
        COUNT(*) FILTER (
            WHERE pc.package_complexity = 'simple' 
            AND pc.package_status = 'active'
        ) as simple_active_count,
        
        SUM(pc.quantity) FILTER (
            WHERE pc.package_complexity = 'simple' 
            AND pc.package_status = 'active'
        ) as simple_active_weight,
        
        -- Simple finished/archived
        COUNT(*) FILTER (
            WHERE pc.package_complexity = 'simple' 
            AND pc.package_status = 'finished_or_archived'
        ) as simple_finished_count,
        
        SUM(pc.quantity) FILTER (
            WHERE pc.package_complexity = 'simple' 
            AND pc.package_status = 'finished_or_archived'
        ) as simple_finished_weight,
        
        -- Sales (external transfers)
        COUNT(DISTINCT pd.label) FILTER (
            WHERE pc.package_complexity = 'simple'
            AND pd.transfer_type = 'sale'
        ) as simple_sale_count,
        
        SUM(pd.quantity_shipped) FILTER (
            WHERE pc.package_complexity = 'simple'
            AND pd.transfer_type = 'sale'
        ) as simple_sale_weight,
        
        -- Internal transfers
        COUNT(DISTINCT pd.label) FILTER (
            WHERE pc.package_complexity = 'simple'
            AND pd.transfer_type = 'internal'
        ) as simple_internal_count,
        
        SUM(pd.quantity_shipped) FILTER (
            WHERE pc.package_complexity = 'simple'
            AND pd.transfer_type = 'internal'
        ) as simple_internal_weight,
        
        -- Complex packages
        COUNT(*) FILTER (
            WHERE pc.package_complexity = 'complex'
        ) as complex_package_count,
        
        SUM(pc.quantity) FILTER (
            WHERE pc.package_complexity = 'complex'
        ) as complex_total_weight
        
    FROM metrc_harvests h
    LEFT JOIN v_package_categorization pc 
        ON h.harvest_name = ANY(pc.source_harvest_array)
        AND h.license_number = pc.license_number
    LEFT JOIN v_package_detail pd
        ON pc.label = pd.label
        AND pc.license_number = pd.license_number
    WHERE 
        -- Only active harvests OR finished since 2025-01-01
        h.finished_date IS NULL 
        OR (h.finished_date >= '2025-01-01' AND h.total_packaged_weight > 0)
    GROUP BY 
        h.id, h.harvest_name, h.license_number, h.harvest_type, 
        h.source_strain_names, h.total_packaged_weight, h.unit_of_weight,
        h.harvest_start_date, h.finished_date, h.is_finished
)
SELECT 
    harvest_id,
    harvest_name,
    license_number,
    harvest_type,
    harvest_strain,
    harvest_weight,
    harvest_unit,
    harvest_packaged_date,
    finished_date,
    harvest_is_finished,
    harvest_status,
    
    -- Simple package totals
    simple_package_count,
    COALESCE(simple_active_weight, 0) + COALESCE(simple_finished_weight, 0) as simple_total_weight,
    simple_active_count,
    simple_active_weight,
    simple_finished_count,
    simple_finished_weight,
    simple_sale_count,
    simple_sale_weight,
    simple_internal_count,
    simple_internal_weight,
    
    -- Complex packages
    COALESCE(complex_package_count, 0) as complex_package_count,
    COALESCE(complex_total_weight, 0) as complex_total_weight,
    
    -- Reconciliation
    harvest_weight - COALESCE(simple_active_weight, 0) - COALESCE(simple_finished_weight, 0) as simple_discrepancy,
    
    CASE 
        WHEN harvest_weight > 0 THEN
            ROUND(((harvest_weight - COALESCE(simple_active_weight, 0) - COALESCE(simple_finished_weight, 0)) / harvest_weight * 100)::numeric, 2)
        ELSE 0
    END as simple_discrepancy_pct,
    
    -- Status flags
    CASE 
        WHEN ABS(harvest_weight - COALESCE(simple_active_weight, 0) - COALESCE(simple_finished_weight, 0)) < 1.0 
            THEN 'OK'
        ELSE 'REVIEW_NEEDED'
    END as reconciliation_status,
    
    CASE 
        WHEN COALESCE(complex_package_count, 0) > 0 THEN TRUE
        ELSE FALSE
    END as has_complex_packages
    
FROM harvest_packages
ORDER BY harvest_status ASC, harvest_packaged_date DESC NULLS LAST;

COMMENT ON VIEW v_harvest_reconciliation IS 
'Master harvest reconciliation view - one row per harvest with all reconciliation metrics. Includes only active harvests OR those finished since 2025-01-01 with non-zero packaged weight.';


-- 5. Problem Harvests View
-- Quick view of harvests needing review
CREATE OR REPLACE VIEW v_harvests_needing_review AS
SELECT 
    harvest_name,
    harvest_strain,
    harvest_status,
    harvest_packaged_date,
    finished_date,
    harvest_weight,
    simple_total_weight,
    simple_discrepancy,
    simple_discrepancy_pct,
    complex_package_count,
    complex_total_weight,
    reconciliation_status
FROM v_harvest_reconciliation
WHERE reconciliation_status = 'REVIEW_NEEDED'
   OR has_complex_packages = TRUE
ORDER BY harvest_status ASC, ABS(simple_discrepancy) DESC;

COMMENT ON VIEW v_harvests_needing_review IS 
'Harvests with discrepancies > 1g or complex packages requiring manual allocation';


-- 6. Complex Package Details
-- Export-ready view of all complex packages for manual allocation
CREATE OR REPLACE VIEW v_complex_packages_detail AS
SELECT 
    pc.label,
    pc.product_name,
    pc.quantity,
    pc.unit_of_measure,
    pc.source_harvest_names,
    pc.source_harvest_count,
    pc.package_status,
    pc.packaged_date,
    pc.finished_date,
    pc.archived_date,
    pd.transfer_type,
    pd.destination_facility_name,
    pd.shipped_date,
    pd.manifest_number
FROM v_package_categorization pc
LEFT JOIN v_package_detail pd
    ON pc.label = pd.label
    AND pc.license_number = pd.license_number
WHERE pc.package_complexity = 'complex'
ORDER BY pc.packaged_date DESC;

COMMENT ON VIEW v_complex_packages_detail IS 
'All packages with multiple source harvests requiring manual weight allocation';


-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index for source_harvest_names searches
CREATE INDEX IF NOT EXISTS idx_packages_source_harvests_gin 
ON metrc_packages USING gin(string_to_array(source_harvest_names, ','));

-- Index for active packages
CREATE INDEX IF NOT EXISTS idx_packages_active 
ON metrc_packages(license_number) 
WHERE finished_date IS NULL AND archived_date IS NULL;

-- Index for transfer classification
CREATE INDEX IF NOT EXISTS idx_transfers_classification 
ON metrc_transfers(shipment_type, destination_facility_name);
