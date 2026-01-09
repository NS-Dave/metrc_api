#!/usr/bin/env python3
"""Analyze what package fields we're storing vs ignoring."""

import json

# Sample JSON from user
sample_json = """{"Id":15600577,"Item":{"Id":3964110,"Name":"M00003964110: Florida Man | 1g Pre-Roll","IsUsed":true,"StrainId":null,"Allergens":null,"StrainName":null,"UnitVolume":null,"UnitWeight":null,"Description":"","ItemBrandId":0,"LabelImages":[],"ServingSize":"","HasUseByDate":false,"QuantityType":"WeightBased","UnitQuantity":null,"HasSellByDate":false,"ItemBrandName":null,"NumberOfDoses":null,"ProductImages":[],"ApprovalStatus":"Approved","UnitCbdContent":null,"UnitCbdPercent":null,"UnitThcContent":null,"UnitThcPercent":null,"PackagingImages":[],"UnitCbdAContent":null,"UnitCbdAPercent":null,"UnitThcAContent":null,"UnitThcAPercent":null,"ProductBrandName":null,"GlobalProductName":null,"HasExpirationDate":false,"LabTestBatchNames":[],"PublicIngredients":"","UnitOfMeasureName":"Grams","UnitCbdContentDose":null,"UnitThcContentDose":null,"GlobalProductNumber":null,"IsUseByDateRequired":false,"ProductCategoryName":"Raw Pre-Rolls","ProductCategoryType":"ShakeTrim","ProductPDFDocuments":[],"UnitCbdAContentDose":null,"UnitThcAContentDose":null,"AdministrationMethod":"","IsSellByDateRequired":false,"LabelPhotoDescription":null,"ProcessingJobTypeName":null,"ApprovalStatusDateTime":"2025-04-03T16:46:57+00:00","DefaultLabTestingState":"NotSubmitted","ProductPhotoDescription":null,"IsExpirationDateRequired":false,"PackagingPhotoDescription":null,"ProcessingJobCategoryName":null,"UnitVolumeUnitOfMeasureName":null,"UnitWeightUnitOfMeasureName":null,"UnitQuantityUnitOfMeasureName":null,"UnitCbdContentUnitOfMeasureName":null,"UnitThcContentUnitOfMeasureName":null,"UnitCbdAContentUnitOfMeasureName":null,"UnitThcAContentUnitOfMeasureName":null,"UnitThcContentDoseUnitOfMeasureId":null,"UnitThcAContentDoseUnitOfMeasureId":null,"UnitCbdContentDoseUnitOfMeasureName":null,"UnitThcContentDoseUnitOfMeasureName":null,"UnitCbdAContentDoseUnitOfMeasureName":null,"UnitThcAContentDoseUnitOfMeasureName":null},"Note":"","Label":"1A40A030000C289000031566","IsOnHold":false,"Quantity":100,"UseByDate":null,"ExternalId":null,"IsDonation":false,"IsFinished":false,"IsOnRecall":false,"LocationId":793103,"SellByDate":null,"PackageType":"Product","ArchivedDate":null,"FinishedDate":null,"LabTestStage":null,"LastModified":"2025-12-31T14:43:43+00:00","LocationName":"Packaged Goods Vault - Finished Goods - Wholesale","PackagedDate":"2025-12-30","ProductLabel":null,"IsTradeSample":false,"SublocationId":null,"ExpirationDate":null,"LabTestStageId":null,"IsTestingSample":false,"LabTestingState":"TestPassed","RemediationDate":null,"SublocationName":null,"IsOnHoldCombined":false,"LocationTypeName":"Default Location Type","ReceivedDateTime":null,"IsOnInvestigation":false,"IsProductionBatch":false,"UnitOfMeasureName":"Grams","IsOnRecallCombined":false,"SourceHarvestCount":1,"SourceHarvestNames":"FMAN #8 R6C64 9/26/25","SourcePackageCount":1,"DecontaminationDate":null,"LabTestingStateDate":"2025-11-03","SourcePackageLabels":"1A40A030000C28A000015488","IsDonationPersistent":false,"IsOnRetailerDelivery":false,"ItemFromFacilityName":"140 Industrial Road, LLC","PatientLicenseNumber":"","IsOnInvestigationHold":false,"ProductionBatchNumber":"","InitialLabTestingState":"TestPassed","LabTestingRecordedDate":"2025-11-03T20:35:03+00:00","IsOnInvestigationRecall":false,"IsTradeSamplePersistent":false,"LabTestingPerformedDate":null,"OriginalPackageQuantity":100,"SourcePackageIsDonation":false,"ReceivedFromFacilityName":null,"SourceProcessingJobCount":0,"ContainsRemediatedProduct":false,"UnitOfMeasureAbbreviation":"g","ProductRequiresRemediation":false,"ReceivedFromManifestNumber":null,"SourcePackageIsTradeSample":false,"LabelsLastGeneratedDateTime":null,"PackageForProductDestruction":null,"SourceProductionBatchNumbers":"FMAN #8 R6C64 9/26/25 - 2","ContainsDecontaminatedProduct":false,"ItemFromFacilityLicenseNumber":"MP281433","ProductRequiresDecontamination":false,"LabTestResultExpirationDateTime":"2026-11-03","IsProcessValidationTestingSample":false,"ReceivedFromFacilityLicenseNumber":null}"""

package = json.loads(sample_json)

# Fields currently stored (from metrc_daily_sync.py)
stored_fields = {
    'id': 'Id',
    'label': 'Label',
    'package_type': 'PackageType',
    'product_name': 'Item.Name',
    'product_category_name': 'Item.ProductCategoryName',
    'item_name': 'Item.Name',
    'item_id': 'Item.Id',
    'quantity': 'Quantity',
    'unit_of_measure': 'UnitOfMeasureName',
    'packaged_date': 'PackagedDate',
    'initial_lab_testing_state': 'InitialLabTestingState',
    'lab_testing_state': 'LabTestingState',
    'lab_testing_state_date': 'LabTestingStateDate',
    'is_production_batch': 'IsProductionBatch',
    'production_batch_number': 'ProductionBatchNumber',
    'source_production_batch_numbers': 'SourceProductionBatchNumbers',
    'source_package_labels': 'SourcePackageLabels',
    'source_harvest_names': 'SourceHarvestNames',
    'is_trade_sample': 'IsTradeSample',
    'is_testing_sample': 'IsTestingSample',
    'is_process_validation_test_sample': 'IsProcessValidationTestSample',
    'is_donation': 'IsDonation',
    'is_on_hold': 'IsOnHold',
    'archived_date': 'ArchivedDate',
    'finished_date': 'FinishedDate',
    'location_name': 'LocationName',
    'note': 'Note',
    'last_modified': 'LastModified',
}

# All top-level fields in the JSON
all_fields = set(package.keys())

# Fields we're storing (top-level only, excluding Item nested fields)
storing_top_level = set([v for v in stored_fields.values() if '.' not in v])

# Fields we're ignoring
ignored = all_fields - storing_top_level

print("FIELDS WE ARE CURRENTLY STORING:")
print("=" * 80)
for db_col, json_field in sorted(stored_fields.items()):
    value = package.get(json_field.split('.')[0]) if '.' not in json_field else 'nested'
    if '.' in json_field and package.get('Item'):
        value = package['Item'].get(json_field.split('.')[1])
    print(f"  {db_col:40} <- {json_field:40} = {str(value)[:50]}")

print("\n\nFIELDS WE ARE IGNORING:")
print("=" * 80)
for field in sorted(ignored):
    value = package.get(field)
    print(f"  {field:50} = {str(value)[:80]}")

# Group by category
print("\n\nIGNORED FIELDS BY CATEGORY:")
print("=" * 80)

transfer_fields = [f for f in ignored if 'Received' in f or 'ItemFrom' in f or 'Manifest' in f]
status_flags = [f for f in ignored if f.startswith('Is') and f not in storing_top_level]
location_fields = [f for f in ignored if 'Location' in f or 'Sublocation' in f]
date_fields = [f for f in ignored if 'Date' in f and f not in storing_top_level]
lab_fields = [f for f in ignored if 'Lab' in f or 'Test' in f]
source_fields = [f for f in ignored if 'Source' in f]
other_fields = [f for f in ignored if f not in transfer_fields + status_flags + location_fields + date_fields + lab_fields + source_fields]

print("\nTRANSFER/RECEIVING FIELDS:")
for f in sorted(transfer_fields):
    print(f"  {f:50} = {package.get(f)}")

print("\nSTATUS FLAGS:")
for f in sorted(status_flags):
    print(f"  {f:50} = {package.get(f)}")

print("\nLOCATION FIELDS:")
for f in sorted(location_fields):
    print(f"  {f:50} = {package.get(f)}")

print("\nDATE FIELDS:")
for f in sorted(date_fields):
    print(f"  {f:50} = {package.get(f)}")

print("\nLAB/TESTING FIELDS:")
for f in sorted(lab_fields):
    print(f"  {f:50} = {package.get(f)}")

print("\nSOURCE TRACKING FIELDS:")
for f in sorted(source_fields):
    print(f"  {f:50} = {package.get(f)}")

print("\nOTHER FIELDS:")
for f in sorted(other_fields):
    print(f"  {f:50} = {package.get(f)}")
