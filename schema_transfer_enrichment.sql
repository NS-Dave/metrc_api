-- ===========================================================================
-- TRANSFER ENRICHMENT SCHEMA
-- Comprehensive package-level tracking for completed transfers
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. UPDATE metrc_transfers table - add received/pricing columns
-- ---------------------------------------------------------------------------
ALTER TABLE metrc_transfers
ADD COLUMN IF NOT EXISTS received_date_time TIMESTAMP,
ADD COLUMN IF NOT EXISTS received_package_count INTEGER,
ADD COLUMN IF NOT EXISTS delivery_received_package_count INTEGER,
ADD COLUMN IF NOT EXISTS shipment_license_type VARCHAR(100);

COMMENT ON COLUMN metrc_transfers.received_date_time IS 'Actual time transfer was received';
COMMENT ON COLUMN metrc_transfers.received_package_count IS 'Number of packages actually received';
COMMENT ON COLUMN metrc_transfers.delivery_received_package_count IS 'Delivery-level received count';
COMMENT ON COLUMN metrc_transfers.shipment_license_type IS 'Type of shipment license';

-- ---------------------------------------------------------------------------
-- 2. NEW TABLE: metrc_transfer_packages
-- Package-level detail for each transfer with wholesale pricing
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metrc_transfer_packages (
    id BIGSERIAL PRIMARY KEY,
    transfer_id BIGINT NOT NULL,
    delivery_id BIGINT,
    package_id BIGINT,
    package_label VARCHAR(255),
    package_type VARCHAR(100),
    
    -- Product/Item Info
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
    
    -- WHOLESALE PRICING (KEY BUSINESS VALUE)
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
    
    -- Full JSON from API
    data JSONB,
    synced_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_transfer FOREIGN KEY (transfer_id) REFERENCES metrc_transfers(id) ON DELETE CASCADE,
    CONSTRAINT unique_transfer_package UNIQUE (transfer_id, package_label)
);

CREATE INDEX IF NOT EXISTS idx_transfer_packages_transfer_id ON metrc_transfer_packages(transfer_id);
CREATE INDEX IF NOT EXISTS idx_transfer_packages_package_id ON metrc_transfer_packages(package_id);
CREATE INDEX IF NOT EXISTS idx_transfer_packages_package_label ON metrc_transfer_packages(package_label);
CREATE INDEX IF NOT EXISTS idx_transfer_packages_product_name ON metrc_transfer_packages(product_name);
CREATE INDEX IF NOT EXISTS idx_transfer_packages_source_harvests ON metrc_transfer_packages USING GIN (source_harvest_names gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_transfer_packages_wholesale_price ON metrc_transfer_packages(wholesale_price) WHERE wholesale_price IS NOT NULL;

COMMENT ON TABLE metrc_transfer_packages IS 'Package-level detail for each transfer with wholesale pricing and full traceability';
COMMENT ON COLUMN metrc_transfer_packages.wholesale_price IS 'Wholesale price for the package';
COMMENT ON COLUMN metrc_transfer_packages.shipper_wholesale_price IS 'Price set by shipper';
COMMENT ON COLUMN metrc_transfer_packages.receiver_wholesale_price IS 'Price recorded by receiver';
COMMENT ON COLUMN metrc_transfer_packages.source_harvest_names IS 'Comma-separated harvest names for traceability';

-- ---------------------------------------------------------------------------
-- 3. NEW TABLE: metrc_transfer_transporters
-- Driver and vehicle details for each transfer delivery
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metrc_transfer_transporters (
    id BIGSERIAL PRIMARY KEY,
    transfer_id BIGINT NOT NULL,
    delivery_id BIGINT,
    
    -- Transporter/Driver Info
    transporter_facility_license_number VARCHAR(100),
    driver_occupational_license_number VARCHAR(100),
    driver_name VARCHAR(255),
    driver_license_number VARCHAR(100),
    phone_number_for_questions VARCHAR(50),
    
    -- Vehicle Info
    vehicle_make VARCHAR(100),
    vehicle_model VARCHAR(100),
    vehicle_license_plate_number VARCHAR(50),
    
    -- Route Info
    is_layover BOOLEAN,
    estimated_departure_date_time TIMESTAMP,
    estimated_arrival_date_time TIMESTAMP,
    actual_departure_date_time TIMESTAMP,
    actual_arrival_date_time TIMESTAMP,
    
    -- Full JSON from API
    data JSONB,
    synced_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_transporter_transfer FOREIGN KEY (transfer_id) REFERENCES metrc_transfers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transfer_transporters_transfer_id ON metrc_transfer_transporters(transfer_id);
CREATE INDEX IF NOT EXISTS idx_transfer_transporters_driver_name ON metrc_transfer_transporters(driver_name);
CREATE INDEX IF NOT EXISTS idx_transfer_transporters_vehicle_plate ON metrc_transfer_transporters(vehicle_license_plate_number);
CREATE INDEX IF NOT EXISTS idx_transfer_transporters_departure ON metrc_transfer_transporters(actual_departure_date_time);

COMMENT ON TABLE metrc_transfer_transporters IS 'Driver and vehicle tracking for transfer deliveries';
COMMENT ON COLUMN metrc_transfer_transporters.driver_name IS 'Name of driver executing the transfer';
COMMENT ON COLUMN metrc_transfer_transporters.vehicle_license_plate_number IS 'License plate for tracking and compliance';

-- ---------------------------------------------------------------------------
-- 4. VIEWS: Aggregated transfer analytics
-- ---------------------------------------------------------------------------

-- View: Transfer package summary with pricing
CREATE OR REPLACE VIEW transfer_package_summary AS
SELECT 
    t.id AS transfer_id,
    t.manifest_number,
    t.shipper_facility_name,
    t.destination_facility_name,
    t.created_date,
    t.received_date_time,
    COUNT(tp.id) AS total_packages,
    SUM(tp.quantity_shipped) AS total_quantity_shipped,
    SUM(tp.quantity_received) AS total_quantity_received,
    SUM(tp.wholesale_price) AS total_wholesale_value,
    SUM(CASE WHEN tp.quantity_received IS NULL OR tp.quantity_received < tp.quantity_shipped 
        THEN tp.quantity_shipped - COALESCE(tp.quantity_received, 0) 
        ELSE 0 END) AS total_shrinkage_qty,
    SUM(CASE WHEN tp.wholesale_price IS NOT NULL 
        THEN tp.wholesale_price * (tp.quantity_shipped - COALESCE(tp.quantity_received, 0)) / NULLIF(tp.quantity_shipped, 0)
        ELSE 0 END) AS total_shrinkage_value
FROM metrc_transfers t
LEFT JOIN metrc_transfer_packages tp ON t.id = tp.transfer_id
GROUP BY t.id, t.manifest_number, t.shipper_facility_name, 
         t.destination_facility_name, t.created_date, t.received_date_time;

COMMENT ON VIEW transfer_package_summary IS 'Aggregated transfer metrics including pricing and shrinkage';

-- View: Transporter performance
CREATE OR REPLACE VIEW transporter_performance AS
SELECT 
    tt.driver_name,
    tt.vehicle_license_plate_number,
    COUNT(DISTINCT tt.transfer_id) AS total_transfers,
    AVG(EXTRACT(EPOCH FROM (tt.actual_arrival_date_time - tt.actual_departure_date_time)) / 3600) AS avg_transit_hours,
    SUM(CASE WHEN tt.actual_arrival_date_time > tt.estimated_arrival_date_time THEN 1 ELSE 0 END) AS late_arrivals,
    COUNT(*) FILTER (WHERE tt.actual_arrival_date_time IS NOT NULL) AS completed_deliveries
FROM metrc_transfer_transporters tt
WHERE tt.actual_departure_date_time IS NOT NULL
GROUP BY tt.driver_name, tt.vehicle_license_plate_number
ORDER BY total_transfers DESC;

COMMENT ON VIEW transporter_performance IS 'Driver/vehicle performance metrics';

-- View: Product transfer flow (harvest to destination)
CREATE OR REPLACE VIEW harvest_transfer_flow AS
SELECT 
    tp.source_harvest_names,
    h.harvest_name,
    h.harvest_start_date,
    tp.product_name,
    t.shipper_facility_name,
    t.destination_facility_name,
    tp.quantity_shipped,
    tp.wholesale_price,
    tp.packaged_date,
    t.created_date AS transfer_date,
    t.received_date_time
FROM metrc_transfer_packages tp
JOIN metrc_transfers t ON tp.transfer_id = t.id
LEFT JOIN metrc_harvests h ON tp.source_harvest_names LIKE '%' || h.harvest_name || '%'
WHERE tp.source_harvest_names IS NOT NULL
ORDER BY h.harvest_start_date DESC, t.created_date DESC;

COMMENT ON VIEW harvest_transfer_flow IS 'Track products from harvest through transfers';
