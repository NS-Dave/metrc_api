-- Add comprehensive package tracking columns to metrc_packages table
-- Captures transfer, status, location, and other metadata for complete package lifecycle tracking

ALTER TABLE metrc_packages 
-- Transfer/receiving fields
ADD COLUMN IF NOT EXISTS received_datetime timestamp with time zone,
ADD COLUMN IF NOT EXISTS received_from_manifest_number text,
ADD COLUMN IF NOT EXISTS received_from_facility_license_number text,
ADD COLUMN IF NOT EXISTS received_from_facility_name text,
ADD COLUMN IF NOT EXISTS item_from_facility_license_number text,
ADD COLUMN IF NOT EXISTS item_from_facility_name text,

-- Status flags (excluding regulatory investigation/recall fields)
ADD COLUMN IF NOT EXISTS is_donation_persistent boolean,
ADD COLUMN IF NOT EXISTS is_finished boolean,
ADD COLUMN IF NOT EXISTS is_on_hold_combined boolean,
ADD COLUMN IF NOT EXISTS is_on_retailer_delivery boolean,
ADD COLUMN IF NOT EXISTS is_process_validation_testing_sample boolean,
ADD COLUMN IF NOT EXISTS is_trade_sample_persistent boolean,

-- Location details
ADD COLUMN IF NOT EXISTS location_id bigint,
ADD COLUMN IF NOT EXISTS location_type_name text,
ADD COLUMN IF NOT EXISTS sublocation_id bigint,
ADD COLUMN IF NOT EXISTS sublocation_name text,

-- Date fields
ADD COLUMN IF NOT EXISTS decontamination_date timestamp with time zone,
ADD COLUMN IF NOT EXISTS expiration_date timestamp with time zone,
ADD COLUMN IF NOT EXISTS lab_test_result_expiration_datetime timestamp with time zone,
ADD COLUMN IF NOT EXISTS lab_testing_performed_date timestamp with time zone,
ADD COLUMN IF NOT EXISTS lab_testing_recorded_date timestamp with time zone,
ADD COLUMN IF NOT EXISTS labels_last_generated_datetime timestamp with time zone,
ADD COLUMN IF NOT EXISTS remediation_date timestamp with time zone,
ADD COLUMN IF NOT EXISTS sell_by_date timestamp with time zone,
ADD COLUMN IF NOT EXISTS use_by_date timestamp with time zone,

-- Lab/testing fields
ADD COLUMN IF NOT EXISTS lab_test_stage text,
ADD COLUMN IF NOT EXISTS lab_test_stage_id bigint,
ADD COLUMN IF NOT EXISTS product_label text,

-- Source tracking
ADD COLUMN IF NOT EXISTS source_harvest_count integer,
ADD COLUMN IF NOT EXISTS source_package_count integer,
ADD COLUMN IF NOT EXISTS source_package_is_donation boolean,
ADD COLUMN IF NOT EXISTS source_package_is_trade_sample boolean,
ADD COLUMN IF NOT EXISTS source_processing_job_count integer,

-- Other metadata
ADD COLUMN IF NOT EXISTS contains_decontaminated_product boolean,
ADD COLUMN IF NOT EXISTS contains_remediated_product boolean,
ADD COLUMN IF NOT EXISTS external_id text,
ADD COLUMN IF NOT EXISTS original_package_quantity numeric,
ADD COLUMN IF NOT EXISTS package_for_product_destruction boolean,
ADD COLUMN IF NOT EXISTS patient_license_number text,
ADD COLUMN IF NOT EXISTS product_requires_decontamination boolean,
ADD COLUMN IF NOT EXISTS product_requires_remediation boolean,
ADD COLUMN IF NOT EXISTS unit_of_measure_abbreviation text;

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_packages_in_transit 
ON metrc_packages (license_number, finished_date, archived_date, received_datetime)
WHERE finished_date IS NULL AND archived_date IS NULL;

CREATE INDEX IF NOT EXISTS idx_packages_item_from_facility 
ON metrc_packages (item_from_facility_license_number, license_number);

CREATE INDEX IF NOT EXISTS idx_packages_location 
ON metrc_packages (location_id, license_number);

CREATE INDEX IF NOT EXISTS idx_packages_source_counts 
ON metrc_packages (source_harvest_count, source_package_count)
WHERE source_harvest_count > 0 OR source_package_count > 0;

-- Column comments
COMMENT ON COLUMN metrc_packages.received_datetime IS 'When package was received from a transfer (NULL = not yet received or created at this facility)';
COMMENT ON COLUMN metrc_packages.item_from_facility_license_number IS 'License number where package was originally created (different from current license = in-transit or transferred package)';
COMMENT ON COLUMN metrc_packages.is_on_retailer_delivery IS 'Package is currently out for delivery to retailer';
COMMENT ON COLUMN metrc_packages.source_harvest_count IS 'Number of source harvests (1 = simple package, >1 = complex package requiring allocation)';
COMMENT ON COLUMN metrc_packages.is_finished IS 'Package lifecycle is complete (may differ from finished_date for timing)';
