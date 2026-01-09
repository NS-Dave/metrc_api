-- ===========================================================================
-- TRANSFERS SCHEMA - DIRECTION-AWARE (Clean Slate Version)
-- Use this for fresh database or after dropping existing tables
-- ===========================================================================

CREATE TABLE IF NOT EXISTS metrc_transfers (
    id BIGINT NOT NULL,
    manifest_number TEXT NOT NULL,
    license_number TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    
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
    
    -- Composite unique constraint: same transfer can exist as incoming AND outgoing
    CONSTRAINT metrc_transfers_id_license_direction_unique 
    UNIQUE (id, license_number, direction)
);

CREATE INDEX IF NOT EXISTS idx_transfers_license ON metrc_transfers(license_number);
CREATE INDEX IF NOT EXISTS idx_transfers_direction ON metrc_transfers(direction, license_number);
CREATE INDEX IF NOT EXISTS idx_transfers_shipper ON metrc_transfers(shipper_facility_license_number);
CREATE INDEX IF NOT EXISTS idx_transfers_destination ON metrc_transfers(destination_facility_license_number);
CREATE INDEX IF NOT EXISTS idx_transfers_created ON metrc_transfers(created_date DESC);
CREATE INDEX IF NOT EXISTS idx_transfers_manifest ON metrc_transfers(manifest_number);

-- ===========================================================================
-- TRANSFER PACKAGES - DIRECTION-AWARE
-- ===========================================================================

CREATE TABLE IF NOT EXISTS metrc_transfer_packages (
    id BIGSERIAL PRIMARY KEY,
    transfer_id BIGINT NOT NULL,
    delivery_id BIGINT,
    direction TEXT NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    
    package_id BIGINT,
    package_label VARCHAR(255),
    package_type VARCHAR(100),
    
    -- Product/Item Info (from full package fetch)
    product_name TEXT,
    product_category_name VARCHAR(255),
    item_id BIGINT,
    item_name TEXT,
    item_category_name VARCHAR(255),
    item_strain_name VARCHAR(255),
    
    -- Source Traceability
    source_harvest_names TEXT,
    source_package_labels TEXT,
    
    -- Quantities
    quantity_shipped NUMERIC(15, 4),
    quantity_received NUMERIC(15, 4),
    unit_of_measure_name VARCHAR(50),
    unit_of_measure_abbreviation VARCHAR(20),
    
    -- Weight
    gross_weight NUMERIC(15, 4),
    gross_unit_of_weight_name VARCHAR(50),
    gross_unit_of_weight_abbreviation VARCHAR(20),
    
    -- WHOLESALE PRICING
    wholesale_price NUMERIC(15, 2),
    shipper_wholesale_price NUMERIC(15, 2),
    receiver_wholesale_price NUMERIC(15, 2),
    
    -- THC/CBD Content
    item_unit_thc_percent NUMERIC(8, 4),
    item_unit_thc_content NUMERIC(15, 4),
    item_unit_thc_content_uom VARCHAR(50),
    item_unit_cbd_percent NUMERIC(8, 4),
    item_unit_cbd_content NUMERIC(15, 4),
    item_unit_cbd_content_uom VARCHAR(50),
    
    -- Lab Testing
    lab_testing_state VARCHAR(100),
    lab_testing_state_date TIMESTAMPTZ,
    
    -- Package Attributes
    is_testing_sample BOOLEAN,
    is_process_validation_test_sample BOOLEAN,
    is_production_batch BOOLEAN,
    production_batch_number VARCHAR(255),
    is_trade_sample BOOLEAN,
    is_on_hold BOOLEAN,
    
    -- Dates
    packaged_date TIMESTAMP,
    received_date_time TIMESTAMP,
    archived_date TIMESTAMP,
    finished_date TIMESTAMP,
    last_modified TIMESTAMP,
    
    -- Full package enrichment tracking
    full_package_fetched BOOLEAN DEFAULT FALSE,
    full_package_fetch_attempted_at TIMESTAMPTZ,
    full_package_fetch_error TEXT,
    
    -- Metadata
    data JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for transfer packages
CREATE INDEX IF NOT EXISTS idx_transfer_packages_transfer ON metrc_transfer_packages(transfer_id);
CREATE INDEX IF NOT EXISTS idx_transfer_packages_direction ON metrc_transfer_packages(direction);
CREATE INDEX IF NOT EXISTS idx_transfer_packages_package_id ON metrc_transfer_packages(package_id);
CREATE INDEX IF NOT EXISTS idx_transfer_packages_label ON metrc_transfer_packages(package_label);

-- Index for finding packages that need full data fetch
CREATE INDEX IF NOT EXISTS idx_transfer_packages_needs_fetch 
ON metrc_transfer_packages(full_package_fetched, package_id) 
WHERE full_package_fetched = FALSE AND package_id IS NOT NULL;

-- ===========================================================================
-- CONVENIENCE VIEWS
-- ===========================================================================

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
GROUP BY t.id, t.manifest_number, t.license_number, t.direction, t.shipper_facility_name,
         t.shipper_facility_license_number, t.transporter_facility_name, 
         t.transporter_facility_license_number, t.destination_facility_name,
         t.destination_facility_license_number, t.created_date, t.transfer_type,
         t.shipment_type, t.est_departure_datetime, t.est_arrival_datetime,
         t.actual_departure_datetime, t.actual_arrival_datetime, t.package_count,
         t.delivery_count, t.received_delivery_count, t.last_modified, t.data, t.synced_at;

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
GROUP BY t.id, t.manifest_number, t.license_number, t.direction, t.shipper_facility_name,
         t.shipper_facility_license_number, t.transporter_facility_name, 
         t.transporter_facility_license_number, t.destination_facility_name,
         t.destination_facility_license_number, t.created_date, t.transfer_type,
         t.shipment_type, t.est_departure_datetime, t.est_arrival_datetime,
         t.actual_departure_datetime, t.actual_arrival_datetime, t.package_count,
         t.delivery_count, t.received_delivery_count, t.last_modified, t.data, t.synced_at;

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

COMMENT ON TABLE metrc_transfers IS 'Transfer manifests with direction tracking. Same transfer ID can exist as both incoming and outgoing.';
COMMENT ON COLUMN metrc_transfers.direction IS 'incoming = we received it, outgoing = we shipped it';
COMMENT ON COLUMN metrc_transfer_packages.full_package_fetched IS 'TRUE if enriched from /packages/v2/{id} endpoint';
