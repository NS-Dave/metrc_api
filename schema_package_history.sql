-- Package History Tracking System
-- 
-- Purpose: Track changes to packages over time to answer questions like:
--   - When did this package finish?
--   - How did quantity change over time?
--   - What was the package state on a specific date?
--   - Track package journey: created → processed → transferred → finished
--
-- Pattern: Slowly Changing Dimension Type 2 (SCD2)
--   - metrc_packages: Current state (fast queries)
--   - metrc_packages_history: All historical snapshots

-- ==============================================================================
-- HISTORY TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS metrc_packages_history (
    history_id BIGSERIAL PRIMARY KEY,
    
    -- Package identification
    id BIGINT NOT NULL,
    label TEXT NOT NULL,
    license_number TEXT NOT NULL,
    
    -- State tracking
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    is_current BOOLEAN DEFAULT FALSE,
    
    -- What changed
    change_type TEXT,  -- 'created', 'updated', 'state_change', 'quantity_change'
    changed_fields JSONB,  -- Array of field names that changed
    
    -- Snapshot of all package data at this point in time
    package_type TEXT,
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
    source_harvest_names TEXT,
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
    
    -- Status flags
    is_finished BOOLEAN,
    is_archived BOOLEAN,
    endpoint_source TEXT,
    
    -- Full API response at this point in time
    data JSONB NOT NULL,
    
    -- Metadata
    synced_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_packages_history_label 
ON metrc_packages_history(label, valid_from DESC);

CREATE INDEX IF NOT EXISTS idx_packages_history_id 
ON metrc_packages_history(id, valid_from DESC);

CREATE INDEX IF NOT EXISTS idx_packages_history_current 
ON metrc_packages_history(label) WHERE is_current = true;

CREATE INDEX IF NOT EXISTS idx_packages_history_license 
ON metrc_packages_history(license_number, valid_from DESC);

CREATE INDEX IF NOT EXISTS idx_packages_history_valid_range 
ON metrc_packages_history(label, valid_from, valid_to);

CREATE INDEX IF NOT EXISTS idx_packages_history_change_type 
ON metrc_packages_history(change_type);

CREATE INDEX IF NOT EXISTS idx_packages_history_state_changes
ON metrc_packages_history(label, is_finished, is_archived, valid_from DESC);

COMMENT ON TABLE metrc_packages_history IS 
'Historical snapshots of package states. Tracks all changes to packages over time.
Use this to see what a package looked like at any point in time.';

COMMENT ON COLUMN metrc_packages_history.valid_from IS 
'When this state became valid (when the sync occurred that captured this state)';

COMMENT ON COLUMN metrc_packages_history.valid_to IS 
'When this state ceased being valid (NULL if current state)';

COMMENT ON COLUMN metrc_packages_history.is_current IS 
'True if this is the current state of the package';

COMMENT ON COLUMN metrc_packages_history.changed_fields IS 
'JSON array of field names that changed from previous version';

-- ==============================================================================
-- HELPER VIEWS
-- ==============================================================================

-- View: Get current state of all packages from history
CREATE OR REPLACE VIEW packages_current_from_history AS
SELECT *
FROM metrc_packages_history
WHERE is_current = true;

COMMENT ON VIEW packages_current_from_history IS 
'Current state of all packages as stored in history table';

-- View: Package state changes (transitions)
CREATE OR REPLACE VIEW package_state_transitions AS
SELECT 
    label,
    license_number,
    valid_from as transition_time,
    COALESCE(
        CASE WHEN is_finished THEN 'finished' END,
        CASE WHEN is_archived THEN 'archived' END,
        CASE WHEN is_on_hold THEN 'on_hold' END,
        'active'
    ) as state,
    quantity,
    endpoint_source,
    LAG(is_finished) OVER (PARTITION BY label ORDER BY valid_from) as prev_finished,
    LAG(is_archived) OVER (PARTITION BY label ORDER BY valid_from) as prev_archived,
    LAG(quantity) OVER (PARTITION BY label ORDER BY valid_from) as prev_quantity
FROM metrc_packages_history
ORDER BY label, valid_from;

COMMENT ON VIEW package_state_transitions IS 
'Shows all state transitions for packages with previous state for comparison';

-- View: Packages that changed state (not just synced)
CREATE OR REPLACE VIEW package_significant_changes AS
SELECT *
FROM metrc_packages_history
WHERE change_type IN ('state_change', 'quantity_change', 'created')
ORDER BY valid_from DESC;

COMMENT ON VIEW package_significant_changes IS 
'Only shows history entries where meaningful changes occurred (filters out routine syncs)';

-- ==============================================================================
-- FUNCTIONS
-- ==============================================================================

-- Function: Get package state at a specific point in time
CREATE OR REPLACE FUNCTION get_package_at_time(
    p_label TEXT,
    p_timestamp TIMESTAMPTZ
) RETURNS TABLE (
    history_id BIGINT,
    label TEXT,
    quantity DECIMAL,
    is_finished BOOLEAN,
    is_archived BOOLEAN,
    location_name TEXT,
    data JSONB,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        h.history_id,
        h.label,
        h.quantity,
        h.is_finished,
        h.is_archived,
        h.location_name,
        h.data,
        h.valid_from,
        h.valid_to
    FROM metrc_packages_history h
    WHERE h.label = p_label
      AND h.valid_from <= p_timestamp
      AND (h.valid_to IS NULL OR h.valid_to > p_timestamp)
    ORDER BY h.valid_from DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_package_at_time IS 
'Get the state of a package at a specific point in time.
Usage: SELECT * FROM get_package_at_time(''1A40A030000C289000029893'', ''2025-12-01'');';

-- Function: Get package change timeline
CREATE OR REPLACE FUNCTION get_package_timeline(p_label TEXT)
RETURNS TABLE (
    change_time TIMESTAMPTZ,
    change_type TEXT,
    changed_fields JSONB,
    quantity DECIMAL,
    is_finished BOOLEAN,
    is_archived BOOLEAN,
    endpoint_source TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        h.valid_from as change_time,
        h.change_type,
        h.changed_fields,
        h.quantity,
        h.is_finished,
        h.is_archived,
        h.endpoint_source
    FROM metrc_packages_history h
    WHERE h.label = p_label
    ORDER BY h.valid_from;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_package_timeline IS 
'Get complete timeline of changes for a specific package.
Usage: SELECT * FROM get_package_timeline(''1A40A030000C289000029893'');';

-- ==============================================================================
-- INITIALIZATION
-- ==============================================================================

-- Populate history with current state as initial snapshot
DO $$
DECLARE
    inserted_count INT;
BEGIN
    INSERT INTO metrc_packages_history (
        id, label, license_number,
        valid_from, valid_to, is_current,
        change_type,
        package_type, product_name, product_category_name,
        item_name, item_id, quantity, unit_of_measure,
        packaged_date, initial_lab_testing_state, lab_testing_state,
        lab_testing_state_date, is_production_batch, production_batch_number,
        source_production_batch_numbers, source_package_labels, source_harvest_names,
        is_trade_sample, is_testing_sample, is_process_validation_test_sample,
        is_donation, is_on_hold, archived_date, finished_date,
        location_name, note, last_modified,
        is_finished, is_archived, endpoint_source,
        data, synced_at
    )
    SELECT 
        id, label, license_number,
        synced_at as valid_from,
        NULL as valid_to,
        true as is_current,
        'initial_snapshot' as change_type,
        package_type, product_name, product_category_name,
        item_name, item_id, quantity, unit_of_measure,
        packaged_date, initial_lab_testing_state, lab_testing_state,
        lab_testing_state_date, is_production_batch, production_batch_number,
        source_production_batch_numbers, source_package_labels, source_harvest_names,
        is_trade_sample, is_testing_sample, is_process_validation_test_sample,
        is_donation, is_on_hold, archived_date, finished_date,
        location_name, note, last_modified,
        is_finished, is_archived, endpoint_source,
        data, synced_at
    FROM metrc_packages
    WHERE NOT EXISTS (
        SELECT 1 FROM metrc_packages_history WHERE is_current = true
    );
    
    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    
    RAISE NOTICE 'Initialized history table with % current package states', inserted_count;
END $$;
