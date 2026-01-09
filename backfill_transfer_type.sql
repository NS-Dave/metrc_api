-- Backfill transfer_type based on shipper AND destination facility license numbers
-- Company licenses: MC281599, MP281433, MR283288, MR284733, MR281800
-- Only intercompany if BOTH shipper and destination are company licenses

UPDATE metrc_transfers
SET transfer_type = CASE 
    WHEN shipper_facility_license_number IN ('MC281599', 'MP281433', 'MR283288', 'MR284733', 'MR281800')
     AND destination_facility_license_number IN ('MC281599', 'MP281433', 'MR283288', 'MR284733', 'MR281800')
    THEN 'intercompany'
    ELSE '3rd party'
END;

-- Check results
SELECT 
    transfer_type,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE direction = 'incoming') as incoming_count,
    COUNT(*) FILTER (WHERE direction = 'outgoing') as outgoing_count
FROM metrc_transfers
GROUP BY transfer_type
ORDER BY transfer_type;
