-- Backfill NULL package columns from JSONB data column
-- Run this in Supabase SQL Editor to populate missing structured columns
-- This includes BOTH basic fields and the 45 new fields added

UPDATE metrc_packages
SET
    -- BASIC PACKAGE FIELDS
    label = CASE 
        WHEN label IS NULL THEN data->>'Label' 
        ELSE label 
    END,
    package_type = CASE 
        WHEN package_type IS NULL THEN data->>'PackageType' 
        ELSE package_type 
    END,
    product_name = CASE 
        WHEN product_name IS NULL THEN 
            COALESCE(
                (data->'Item'->>'Name'),
                data->>'ProductName'
            )
        ELSE product_name 
    END,
    product_category_name = CASE 
        WHEN product_category_name IS NULL THEN 
            COALESCE(
                (data->'Item'->>'ProductCategoryName'),
                data->>'ProductCategoryName'
            )
        ELSE product_category_name 
    END,
    item_name = CASE 
        WHEN item_name IS NULL THEN 
            COALESCE(
                (data->'Item'->>'Name'),
                data->>'ItemName'
            )
        ELSE item_name 
    END,
    item_id = CASE 
        WHEN item_id IS NULL THEN 
            COALESCE(
                ((data->'Item'->>'Id')::bigint),
                ((data->>'ItemId')::bigint)
            )
        ELSE item_id 
    END,
    quantity = CASE 
        WHEN quantity IS NULL THEN (data->>'Quantity')::numeric 
        ELSE quantity 
    END,
    unit_of_measure = CASE 
        WHEN unit_of_measure IS NULL THEN data->>'UnitOfMeasureName' 
        ELSE unit_of_measure 
    END,
    packaged_date = CASE 
        WHEN packaged_date IS NULL THEN (data->>'PackagedDate')::timestamptz 
        ELSE packaged_date 
    END,
    initial_lab_testing_state = CASE 
        WHEN initial_lab_testing_state IS NULL THEN data->>'InitialLabTestingState' 
        ELSE initial_lab_testing_state 
    END,
    lab_testing_state = CASE 
        WHEN lab_testing_state IS NULL THEN data->>'LabTestingState' 
        ELSE lab_testing_state 
    END,
    lab_testing_state_date = CASE 
        WHEN lab_testing_state_date IS NULL THEN (data->>'LabTestingStateDate')::timestamptz 
        ELSE lab_testing_state_date 
    END,
    is_production_batch = CASE 
        WHEN is_production_batch IS NULL THEN COALESCE((data->>'IsProductionBatch')::boolean, false)
        ELSE is_production_batch 
    END,
    production_batch_number = CASE 
        WHEN production_batch_number IS NULL THEN data->>'ProductionBatchNumber' 
        ELSE production_batch_number 
    END,
    source_production_batch_numbers = CASE 
        WHEN source_production_batch_numbers IS NULL THEN data->>'SourceProductionBatchNumbers' 
        ELSE source_production_batch_numbers 
    END,
    source_package_labels = CASE 
        WHEN source_package_labels IS NULL THEN data->>'SourcePackageLabels' 
        ELSE source_package_labels 
    END,
    source_harvest_names = CASE 
        WHEN source_harvest_names IS NULL THEN data->>'SourceHarvestNames' 
        ELSE source_harvest_names 
    END,
    is_trade_sample = CASE 
        WHEN is_trade_sample IS NULL THEN COALESCE((data->>'IsTradeSample')::boolean, false)
        ELSE is_trade_sample 
    END,
    is_testing_sample = CASE 
        WHEN is_testing_sample IS NULL THEN COALESCE((data->>'IsTestingSample')::boolean, false)
        ELSE is_testing_sample 
    END,
    is_process_validation_test_sample = CASE 
        WHEN is_process_validation_test_sample IS NULL THEN COALESCE((data->>'IsProcessValidationTestSample')::boolean, false)
        ELSE is_process_validation_test_sample 
    END,
    is_donation = CASE 
        WHEN is_donation IS NULL THEN COALESCE((data->>'IsDonation')::boolean, false)
        ELSE is_donation 
    END,
    is_on_hold = CASE 
        WHEN is_on_hold IS NULL THEN COALESCE((data->>'IsOnHold')::boolean, false)
        ELSE is_on_hold 
    END,
    archived_date = CASE 
        WHEN archived_date IS NULL THEN (data->>'ArchivedDate')::timestamptz 
        ELSE archived_date 
    END,
    finished_date = CASE 
        WHEN finished_date IS NULL THEN (data->>'FinishedDate')::timestamptz 
        ELSE finished_date 
    END,
    location_name = CASE 
        WHEN location_name IS NULL THEN data->>'LocationName' 
        ELSE location_name 
    END,
    note = CASE 
        WHEN note IS NULL THEN data->>'Note' 
        ELSE note 
    END,
    last_modified = CASE 
        WHEN last_modified IS NULL THEN (data->>'LastModified')::timestamptz 
        ELSE last_modified 
    END,
    
    -- Transfer/receiving fields
    received_datetime = CASE 
        WHEN received_datetime IS NULL THEN (data->>'ReceivedDateTime')::timestamptz 
        ELSE received_datetime 
    END,
    received_from_manifest_number = CASE 
        WHEN received_from_manifest_number IS NULL THEN data->>'ReceivedFromManifestNumber' 
        ELSE received_from_manifest_number 
    END,
    received_from_facility_license_number = CASE 
        WHEN received_from_facility_license_number IS NULL THEN data->>'ReceivedFromFacilityLicenseNumber' 
        ELSE received_from_facility_license_number 
    END,
    received_from_facility_name = CASE 
        WHEN received_from_facility_name IS NULL THEN data->>'ReceivedFromFacilityName' 
        ELSE received_from_facility_name 
    END,
    item_from_facility_license_number = CASE 
        WHEN item_from_facility_license_number IS NULL THEN data->>'ItemFromFacilityLicenseNumber' 
        ELSE item_from_facility_license_number 
    END,
    item_from_facility_name = CASE 
        WHEN item_from_facility_name IS NULL THEN data->>'ItemFromFacilityName' 
        ELSE item_from_facility_name 
    END,
    
    -- Status flags
    is_donation_persistent = CASE 
        WHEN is_donation_persistent IS NULL THEN COALESCE((data->>'IsDonationPersistent')::boolean, false)
        ELSE is_donation_persistent 
    END,
    is_finished = CASE 
        WHEN is_finished IS NULL THEN COALESCE((data->>'IsFinished')::boolean, false)
        ELSE is_finished 
    END,
    is_on_hold_combined = CASE 
        WHEN is_on_hold_combined IS NULL THEN COALESCE((data->>'IsOnHoldCombined')::boolean, false)
        ELSE is_on_hold_combined 
    END,
    is_on_retailer_delivery = CASE 
        WHEN is_on_retailer_delivery IS NULL THEN COALESCE((data->>'IsOnRetailerDelivery')::boolean, false)
        ELSE is_on_retailer_delivery 
    END,
    is_process_validation_testing_sample = CASE 
        WHEN is_process_validation_testing_sample IS NULL THEN COALESCE((data->>'IsProcessValidationTestingSample')::boolean, false)
        ELSE is_process_validation_testing_sample 
    END,
    is_trade_sample_persistent = CASE 
        WHEN is_trade_sample_persistent IS NULL THEN COALESCE((data->>'IsTradeSamplePersistent')::boolean, false)
        ELSE is_trade_sample_persistent 
    END,
    
    -- Location details
    location_id = CASE 
        WHEN location_id IS NULL THEN (data->>'LocationId')::bigint 
        ELSE location_id 
    END,
    location_type_name = CASE 
        WHEN location_type_name IS NULL THEN data->>'LocationTypeName' 
        ELSE location_type_name 
    END,
    sublocation_id = CASE 
        WHEN sublocation_id IS NULL THEN (data->>'SublocationId')::bigint 
        ELSE sublocation_id 
    END,
    sublocation_name = CASE 
        WHEN sublocation_name IS NULL THEN data->>'SublocationName' 
        ELSE sublocation_name 
    END,
    
    -- Date fields
    decontamination_date = CASE 
        WHEN decontamination_date IS NULL THEN (data->>'DecontaminationDate')::timestamptz 
        ELSE decontamination_date 
    END,
    expiration_date = CASE 
        WHEN expiration_date IS NULL THEN (data->>'ExpirationDate')::timestamptz 
        ELSE expiration_date 
    END,
    lab_test_result_expiration_datetime = CASE 
        WHEN lab_test_result_expiration_datetime IS NULL THEN (data->>'LabTestResultExpirationDateTime')::timestamptz 
        ELSE lab_test_result_expiration_datetime 
    END,
    lab_testing_performed_date = CASE 
        WHEN lab_testing_performed_date IS NULL THEN (data->>'LabTestingPerformedDate')::timestamptz 
        ELSE lab_testing_performed_date 
    END,
    lab_testing_recorded_date = CASE 
        WHEN lab_testing_recorded_date IS NULL THEN (data->>'LabTestingRecordedDate')::timestamptz 
        ELSE lab_testing_recorded_date 
    END,
    labels_last_generated_datetime = CASE 
        WHEN labels_last_generated_datetime IS NULL THEN (data->>'LabelsLastGeneratedDateTime')::timestamptz 
        ELSE labels_last_generated_datetime 
    END,
    remediation_date = CASE 
        WHEN remediation_date IS NULL THEN (data->>'RemediationDate')::timestamptz 
        ELSE remediation_date 
    END,
    sell_by_date = CASE 
        WHEN sell_by_date IS NULL THEN (data->>'SellByDate')::timestamptz 
        ELSE sell_by_date 
    END,
    use_by_date = CASE 
        WHEN use_by_date IS NULL THEN (data->>'UseByDate')::timestamptz 
        ELSE use_by_date 
    END,
    
    -- Lab/testing fields
    lab_test_stage = CASE 
        WHEN lab_test_stage IS NULL THEN data->>'LabTestStage' 
        ELSE lab_test_stage 
    END,
    lab_test_stage_id = CASE 
        WHEN lab_test_stage_id IS NULL THEN (data->>'LabTestStageId')::bigint 
        ELSE lab_test_stage_id 
    END,
    product_label = CASE 
        WHEN product_label IS NULL THEN data->>'ProductLabel' 
        ELSE product_label 
    END,
    
    -- Source tracking
    source_harvest_count = CASE 
        WHEN source_harvest_count IS NULL THEN (data->>'SourceHarvestCount')::integer 
        ELSE source_harvest_count 
    END,
    source_package_count = CASE 
        WHEN source_package_count IS NULL THEN (data->>'SourcePackageCount')::integer 
        ELSE source_package_count 
    END,
    source_package_is_donation = CASE 
        WHEN source_package_is_donation IS NULL THEN COALESCE((data->>'SourcePackageIsDonation')::boolean, false)
        ELSE source_package_is_donation 
    END,
    source_package_is_trade_sample = CASE 
        WHEN source_package_is_trade_sample IS NULL THEN COALESCE((data->>'SourcePackageIsTradeSample')::boolean, false)
        ELSE source_package_is_trade_sample 
    END,
    source_processing_job_count = CASE 
        WHEN source_processing_job_count IS NULL THEN (data->>'SourceProcessingJobCount')::integer 
        ELSE source_processing_job_count 
    END,
    
    -- Other metadata
    contains_decontaminated_product = CASE 
        WHEN contains_decontaminated_product IS NULL THEN COALESCE((data->>'ContainsDecontaminatedProduct')::boolean, false)
        ELSE contains_decontaminated_product 
    END,
    contains_remediated_product = CASE 
        WHEN contains_remediated_product IS NULL THEN COALESCE((data->>'ContainsRemediatedProduct')::boolean, false)
        ELSE contains_remediated_product 
    END,
    external_id = CASE 
        WHEN external_id IS NULL THEN data->>'ExternalId' 
        ELSE external_id 
    END,
    original_package_quantity = CASE 
        WHEN original_package_quantity IS NULL THEN (data->>'OriginalPackageQuantity')::numeric 
        ELSE original_package_quantity 
    END,
    package_for_product_destruction = CASE 
        WHEN package_for_product_destruction IS NULL THEN COALESCE((data->>'PackageForProductDestruction')::boolean, false)
        ELSE package_for_product_destruction 
    END,
    patient_license_number = CASE 
        WHEN patient_license_number IS NULL THEN data->>'PatientLicenseNumber' 
        ELSE patient_license_number 
    END,
    product_requires_decontamination = CASE 
        WHEN product_requires_decontamination IS NULL THEN COALESCE((data->>'ProductRequiresDecontamination')::boolean, false)
        ELSE product_requires_decontamination 
    END,
    product_requires_remediation = CASE 
        WHEN product_requires_remediation IS NULL THEN COALESCE((data->>'ProductRequiresRemediation')::boolean, false)
        ELSE product_requires_remediation 
    END,
    unit_of_measure_abbreviation = CASE 
        WHEN unit_of_measure_abbreviation IS NULL THEN data->>'UnitOfMeasureAbbreviation' 
        ELSE unit_of_measure_abbreviation 
    END
WHERE 
    data IS NOT NULL
    AND (
        -- Basic fields
        label IS NULL OR
        package_type IS NULL OR
        product_name IS NULL OR
        product_category_name IS NULL OR
        item_name IS NULL OR
        item_id IS NULL OR
        quantity IS NULL OR
        unit_of_measure IS NULL OR
        packaged_date IS NULL OR
        initial_lab_testing_state IS NULL OR
        lab_testing_state IS NULL OR
        lab_testing_state_date IS NULL OR
        is_production_batch IS NULL OR
        production_batch_number IS NULL OR
        source_production_batch_numbers IS NULL OR
        source_package_labels IS NULL OR
        source_harvest_names IS NULL OR
        is_trade_sample IS NULL OR
        is_testing_sample IS NULL OR
        is_process_validation_test_sample IS NULL OR
        is_donation IS NULL OR
        is_on_hold IS NULL OR
        archived_date IS NULL OR
        finished_date IS NULL OR
        location_name IS NULL OR
        note IS NULL OR
        last_modified IS NULL OR
        -- New fields (45 additional fields)
        received_datetime IS NULL OR
        item_from_facility_license_number IS NULL OR
        source_harvest_count IS NULL OR
        location_id IS NULL OR
        is_donation_persistent IS NULL OR
        is_finished IS NULL OR
        is_on_hold_combined IS NULL OR
        is_on_retailer_delivery IS NULL OR
        is_process_validation_testing_sample IS NULL OR
        is_trade_sample_persistent IS NULL OR
        location_type_name IS NULL OR
        sublocation_id IS NULL OR
        sublocation_name IS NULL OR
        decontamination_date IS NULL OR
        expiration_date IS NULL OR
        lab_test_result_expiration_datetime IS NULL OR
        lab_testing_performed_date IS NULL OR
        lab_testing_recorded_date IS NULL OR
        labels_last_generated_datetime IS NULL OR
        remediation_date IS NULL OR
        sell_by_date IS NULL OR
        use_by_date IS NULL OR
        lab_test_stage IS NULL OR
        lab_test_stage_id IS NULL OR
        product_label IS NULL OR
        source_package_count IS NULL OR
        source_package_is_donation IS NULL OR
        source_package_is_trade_sample IS NULL OR
        source_processing_job_count IS NULL OR
        contains_decontaminated_product IS NULL OR
        contains_remediated_product IS NULL OR
        external_id IS NULL OR
        original_package_quantity IS NULL OR
        package_for_product_destruction IS NULL OR
        patient_license_number IS NULL OR
        product_requires_decontamination IS NULL OR
        product_requires_remediation IS NULL OR
        unit_of_measure_abbreviation IS NULL
    );

-- Show summary of what was updated
SELECT 
    'Backfill Complete!' as status,
    COUNT(*) as total_packages_in_db,
    COUNT(*) FILTER (WHERE product_name IS NOT NULL) as have_product_name,
    COUNT(*) FILTER (WHERE product_category_name IS NOT NULL) as have_product_category,
    COUNT(*) FILTER (WHERE item_name IS NOT NULL) as have_item_name,
    COUNT(*) FILTER (WHERE item_from_facility_license_number IS NOT NULL) as have_item_from_facility,
    COUNT(*) FILTER (WHERE source_harvest_count IS NOT NULL) as have_source_harvest_count,
    COUNT(*) FILTER (WHERE location_id IS NOT NULL) as have_location_id
FROM metrc_packages;
