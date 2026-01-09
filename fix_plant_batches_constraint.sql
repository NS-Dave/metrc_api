-- Fix plant_batches unique constraint
-- The current constraint on (license_number, batch_name) is wrong
-- because batch names can be reused. Should be (id, license_number).

-- Drop the incorrect unique constraint
ALTER TABLE metrc_plant_batches 
DROP CONSTRAINT IF EXISTS metrc_plant_batches_license_number_batch_name_key;

-- Add correct unique constraint
ALTER TABLE metrc_plant_batches
ADD CONSTRAINT metrc_plant_batches_id_license_key UNIQUE (id, license_number);
