-- Packages that appear in both metrc_packages and metrc_transfer_packages
-- Only OUTGOING transfers, excluding intercompany affiliated transfers and lab transfers

SELECT 
    -- Package details from metrc_packages
    p.label,
    p.item_name,
    p.product_name,
    p.product_category_name,
    p.item_id,
    p.quantity,
    p.unit_of_measure,
    p.packaged_date,
    
    -- Transfer details from metrc_transfers (via metrc_transfer_packages)
    t.destination_facility_name,
    t.shipment_type,
    t.actual_arrival_datetime,
    t.manifest_number,
    t.transfer_type
    
FROM metrc_packages p
INNER JOIN metrc_transfer_packages tp 
    ON p.label = tp.package_label
INNER JOIN metrc_transfers t 
    ON tp.transfer_id = t.id 
    AND tp.direction = t.direction
    
WHERE 
    -- Only outgoing transfers
    tp.direction = 'outgoing'
    
    -- Exclude intercompany affiliated transfers
    AND NOT (t.transfer_type = 'intercompany' AND t.shipment_type = 'Affiliated Transfer')
    
    -- Exclude lab transfers
    AND t.shipment_type != 'Lab Transfer'
    
ORDER BY t.actual_arrival_datetime DESC, p.label;
