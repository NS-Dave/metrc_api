-- Metrc Data Warehouse Schema for Supabase
-- 
-- This schema stores Metrc cultivation and processing data for:
-- - Fast queries without API rate limits
-- - Historical tracking and compliance
-- - Harvest weight reconciliation
--
-- Run this in Supabase SQL Editor to create all tables

-- ==============================================================================
-- EXTENSIONS
-- ==============================================================================

-- Enable trigram extension for fuzzy text matching on harvest names
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ==============================================================================
-- REFERENCE DATA (Tier 1 - Refresh Weekly)
-- ==============================================================================

-- Facilities
CREATE TABLE IF NOT EXISTS metrc_facilities (
    id BIGINT PRIMARY KEY,
    license_number TEXT NOT NULL,
    license_type TEXT,
    display_name TEXT,
    facility_name TEXT,
    alias TEXT,
    credentialing_authority TEXT,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(license_number)
);

CREATE INDEX IF NOT EXISTS idx_facilities_license ON metrc_facilities(license_number);
CREATE INDEX IF NOT EXISTS idx_facilities_synced ON metrc_facilities(synced_at DESC);

-- Strains
CREATE TABLE IF NOT EXISTS metrc_strains (
    id BIGINT PRIMARY KEY,
    strain_name TEXT NOT NULL,
    license_number TEXT NOT NULL,
    testing_status TEXT,
    thc_level DECIMAL,
    cbd_level DECIMAL,
    indica_percentage DECIMAL,
    sativa_percentage DECIMAL,
    is_used BOOLEAN,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(license_number, strain_name)
);

CREATE INDEX IF NOT EXISTS idx_strains_license ON metrc_strains(license_number);
CREATE INDEX IF NOT EXISTS idx_strains_name ON metrc_strains(strain_name);

-- Locations (Rooms)
CREATE TABLE IF NOT EXISTS metrc_locations (
    id BIGINT PRIMARY KEY,
    location_name TEXT NOT NULL,
    license_number TEXT NOT NULL,
    location_type_name TEXT,
    for_plant_batches BOOLEAN,
    for_plants BOOLEAN,
    for_harvests BOOLEAN,
    for_packages BOOLEAN,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(license_number, location_name)
);

CREATE INDEX IF NOT EXISTS idx_locations_license ON metrc_locations(license_number);

-- Items (Product Catalog)
CREATE TABLE IF NOT EXISTS metrc_items (
    id BIGINT PRIMARY KEY,
    item_name TEXT NOT NULL,
    license_number TEXT NOT NULL,
    product_category_name TEXT,
    product_category_type TEXT,
    quantity_type TEXT,
    default_lab_testing_state TEXT,
    unit_of_measure TEXT,
    approval_status TEXT,
    strain_id BIGINT,
    strain_name TEXT,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(license_number, item_name)
);

CREATE INDEX IF NOT EXISTS idx_items_license ON metrc_items(license_number);
CREATE INDEX IF NOT EXISTS idx_items_category ON metrc_items(product_category_name);

-- ==============================================================================
-- OPERATIONAL DATA (Tier 2 - Daily Incremental)
-- ==============================================================================

-- Harvests
CREATE TABLE IF NOT EXISTS metrc_harvests (
    id BIGINT PRIMARY KEY,
    harvest_name TEXT NOT NULL,
    license_number TEXT NOT NULL,
    harvest_type TEXT,
    source_strain_count INT,
    source_strain_names TEXT,
    drying_location_name TEXT,
    harvest_start_date TIMESTAMPTZ,
    harvest_date TIMESTAMPTZ,
    finished_date TIMESTAMPTZ,
    is_finished BOOLEAN,
    current_weight DECIMAL,
    total_waste_weight DECIMAL,
    total_packaged_weight DECIMAL,
    total_restorative_waste_weight DECIMAL,
    packaged_date TIMESTAMPTZ,
    unit_of_weight TEXT,
    lab_testing_state TEXT,
    lab_testing_state_date TIMESTAMPTZ,
    is_on_hold BOOLEAN,
    last_modified TIMESTAMPTZ,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(license_number, harvest_name)
);

CREATE INDEX IF NOT EXISTS idx_harvests_license ON metrc_harvests(license_number);
CREATE INDEX IF NOT EXISTS idx_harvests_name ON metrc_harvests(harvest_name);
CREATE INDEX IF NOT EXISTS idx_harvests_finished ON metrc_harvests(is_finished, license_number);
CREATE INDEX IF NOT EXISTS idx_harvests_packaged_weight ON metrc_harvests(total_packaged_weight) WHERE total_packaged_weight > 0;
CREATE INDEX IF NOT EXISTS idx_harvests_last_modified ON metrc_harvests(last_modified DESC);
CREATE INDEX IF NOT EXISTS idx_harvests_synced ON metrc_harvests(synced_at DESC);

-- Packages
CREATE TABLE IF NOT EXISTS metrc_packages (
    id BIGINT PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    package_type TEXT,
    license_number TEXT NOT NULL,
    product_name TEXT,
    product_category_name TEXT,
    item_name TEXT,
    item_id BIGINT,
    quantity DECIMAL,
    unit_of_measure TEXT,
    packaged_date TIMESTAMPTZ,
    initial_lab_testing_state TEXT,
    lab_testing_state TEXT,
    lab_testing_state_date TIMESTAMPTZ,
    is_production_batch BOOLEAN,
    production_batch_number TEXT,
    source_production_batch_numbers TEXT,
    source_package_labels TEXT,
    source_harvest_names TEXT,  -- KEY for harvest reconciliation
    is_trade_sample BOOLEAN,
    is_testing_sample BOOLEAN,
    is_process_validation_test_sample BOOLEAN,
    is_donation BOOLEAN,
    is_on_hold BOOLEAN,
    archived_date TIMESTAMPTZ,
    finished_date TIMESTAMPTZ,
    location_name TEXT,
    note TEXT,
    last_modified TIMESTAMPTZ,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_packages_license ON metrc_packages(license_number);
CREATE INDEX IF NOT EXISTS idx_packages_label ON metrc_packages(label);
CREATE INDEX IF NOT EXISTS idx_packages_item ON metrc_packages(item_name);
CREATE INDEX IF NOT EXISTS idx_packages_harvest ON metrc_packages USING gin(source_harvest_names gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_packages_active ON metrc_packages(license_number) WHERE archived_date IS NULL AND finished_date IS NULL;
CREATE INDEX IF NOT EXISTS idx_packages_last_modified ON metrc_packages(last_modified DESC);
CREATE INDEX IF NOT EXISTS idx_packages_synced ON metrc_packages(synced_at DESC);

-- Plant Batches
CREATE TABLE IF NOT EXISTS metrc_plant_batches (
    id BIGINT PRIMARY KEY,
    batch_name TEXT NOT NULL,
    license_number TEXT NOT NULL,
    batch_type TEXT,
    location_name TEXT,
    strain_name TEXT,
    plant_count INT,
    packaged_date TIMESTAMPTZ,
    planted_date TIMESTAMPTZ,
    destroyed_date TIMESTAMPTZ,
    is_destroyed BOOLEAN,
    destroyed_count INT,
    last_modified TIMESTAMPTZ,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(license_number, batch_name)
);

CREATE INDEX IF NOT EXISTS idx_plant_batches_license ON metrc_plant_batches(license_number);
CREATE INDEX IF NOT EXISTS idx_plant_batches_active ON metrc_plant_batches(license_number) WHERE destroyed_date IS NULL;
CREATE INDEX IF NOT EXISTS idx_plant_batches_last_modified ON metrc_plant_batches(last_modified DESC);

-- Plants
CREATE TABLE IF NOT EXISTS metrc_plants (
    id BIGINT PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    license_number TEXT NOT NULL,
    plant_state TEXT,
    growth_phase TEXT,
    plant_batch_name TEXT,
    plant_batch_id BIGINT,
    strain_name TEXT,
    location_name TEXT,
    planted_date TIMESTAMPTZ,
    vegetative_date TIMESTAMPTZ,
    flowering_date TIMESTAMPTZ,
    harvested_date TIMESTAMPTZ,
    destroyed_date TIMESTAMPTZ,
    is_on_hold BOOLEAN,
    last_modified TIMESTAMPTZ,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plants_license ON metrc_plants(license_number);
CREATE INDEX IF NOT EXISTS idx_plants_state ON metrc_plants(plant_state, license_number);
CREATE INDEX IF NOT EXISTS idx_plants_phase ON metrc_plants(growth_phase, license_number);
CREATE INDEX IF NOT EXISTS idx_plants_last_modified ON metrc_plants(last_modified DESC);

-- ==============================================================================
-- TRANSFERS (Tier 3 - Weekly)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS metrc_transfers (
    id BIGINT PRIMARY KEY,
    manifest_number TEXT NOT NULL,
    license_number TEXT NOT NULL,
    shipper_facility_name TEXT,
    shipper_facility_license_number TEXT,
    transporter_facility_name TEXT,
    transporter_facility_license_number TEXT,
    destination_facility_name TEXT,
    destination_facility_license_number TEXT,
    created_date TIMESTAMPTZ,
    transfer_type TEXT,
    shipment_type TEXT,
    est_departure_datetime TIMESTAMPTZ,
    est_arrival_datetime TIMESTAMPTZ,
    actual_departure_datetime TIMESTAMPTZ,
    actual_arrival_datetime TIMESTAMPTZ,
    package_count INT,
    delivery_count INT,
    received_delivery_count INT,
    last_modified TIMESTAMPTZ,
    data JSONB NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(manifest_number)
);

CREATE INDEX IF NOT EXISTS idx_transfers_license ON metrc_transfers(license_number);
CREATE INDEX IF NOT EXISTS idx_transfers_shipper ON metrc_transfers(shipper_facility_license_number);
CREATE INDEX IF NOT EXISTS idx_transfers_destination ON metrc_transfers(destination_facility_license_number);
CREATE INDEX IF NOT EXISTS idx_transfers_created ON metrc_transfers(created_date DESC);

-- ==============================================================================
-- SYNC TRACKING
-- ==============================================================================

CREATE TABLE IF NOT EXISTS metrc_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,  -- 'harvests', 'packages', 'plants', etc.
    license_number TEXT,
    sync_type TEXT NOT NULL,  -- 'full', 'incremental', 'backfill'
    sync_start TIMESTAMPTZ NOT NULL,
    sync_end TIMESTAMPTZ,
    records_pulled INT DEFAULT 0,
    records_inserted INT DEFAULT 0,
    records_updated INT DEFAULT 0,
    date_range_start TIMESTAMPTZ,
    date_range_end TIMESTAMPTZ,
    status TEXT DEFAULT 'running',  -- 'running', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_log_entity ON metrc_sync_log(entity_type, sync_start DESC);
CREATE INDEX IF NOT EXISTS idx_sync_log_status ON metrc_sync_log(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_log_license ON metrc_sync_log(license_number, entity_type);

-- ==============================================================================
-- HARVEST RECONCILIATION VIEW
-- ==============================================================================

-- View to quickly find harvest-package discrepancies
CREATE OR REPLACE VIEW harvest_reconciliation AS
SELECT 
    h.id as harvest_id,
    h.harvest_name,
    h.license_number,
    h.harvest_date,
    h.total_packaged_weight as harvest_packaged_weight,
    h.unit_of_weight,
    h.is_finished,
    COUNT(p.id) as package_count,
    COALESCE(SUM(
        CASE 
            WHEN p.unit_of_measure = 'Grams' THEN p.quantity
            WHEN p.unit_of_measure = 'Ounces' THEN p.quantity * 28.3495
            WHEN p.unit_of_measure = 'Pounds' THEN p.quantity * 453.592
            WHEN p.unit_of_measure = 'Kilograms' THEN p.quantity * 1000
            ELSE p.quantity
        END
    ), 0) as total_package_weight_grams,
    COALESCE(SUM(
        CASE 
            WHEN p.archived_date IS NULL AND p.finished_date IS NULL THEN
                CASE 
                    WHEN p.unit_of_measure = 'Grams' THEN p.quantity
                    WHEN p.unit_of_measure = 'Ounces' THEN p.quantity * 28.3495
                    WHEN p.unit_of_measure = 'Pounds' THEN p.quantity * 453.592
                    WHEN p.unit_of_measure = 'Kilograms' THEN p.quantity * 1000
                    ELSE p.quantity
                END
            ELSE 0
        END
    ), 0) as active_package_weight_grams,
    ABS(h.total_packaged_weight - COALESCE(SUM(
        CASE 
            WHEN p.unit_of_measure = 'Grams' THEN p.quantity
            WHEN p.unit_of_measure = 'Ounces' THEN p.quantity * 28.3495
            WHEN p.unit_of_measure = 'Pounds' THEN p.quantity * 453.592
            WHEN p.unit_of_measure = 'Kilograms' THEN p.quantity * 1000
            ELSE p.quantity
        END
    ), 0)) as weight_discrepancy_grams,
    h.synced_at as harvest_synced_at,
    MAX(p.synced_at) as packages_synced_at
FROM metrc_harvests h
LEFT JOIN metrc_packages p ON p.source_harvest_names LIKE '%' || h.harvest_name || '%' 
    AND p.license_number = h.license_number
WHERE h.total_packaged_weight > 0
GROUP BY h.id, h.harvest_name, h.license_number, h.harvest_date, 
         h.total_packaged_weight, h.unit_of_weight, h.is_finished, h.synced_at
ORDER BY h.harvest_date DESC;

-- ==============================================================================
-- COMMENTS
-- ==============================================================================

COMMENT ON TABLE metrc_harvests IS 'Harvest data from Metrc - tracks plant harvesting and drying';
COMMENT ON TABLE metrc_packages IS 'Package inventory from Metrc - finished products ready for transfer/sale';
COMMENT ON TABLE metrc_plant_batches IS 'Plant batches (clones/seeds) from Metrc';
COMMENT ON TABLE metrc_plants IS 'Individual plants from Metrc';
COMMENT ON TABLE metrc_transfers IS 'Transfer manifests between facilities';
COMMENT ON TABLE metrc_sync_log IS 'Tracks all sync operations from Metrc API';

COMMENT ON VIEW harvest_reconciliation IS 'Shows harvest weight vs actual package weight with discrepancies';
