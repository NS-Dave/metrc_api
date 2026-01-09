"""
Metrc Daily Incremental Sync to Supabase

Pulls last 48 hours of data from Metrc API and upserts to Supabase.
This avoids rate limits by querying Supabase for analysis instead of hitting API repeatedly.

Run this daily (via Task Scheduler or cron) to keep data warehouse fresh.
"""

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import json
import os
from typing import List, Dict, Optional
import uuid

from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from processing import ProcessingClient
from supabase_config import get_connection_string

# License configuration
CULTIVATION_LICENSE = os.getenv('METRC_LICENSE_CULTIVATION', 'MC281599')
PROCESSING_LICENSE = os.getenv('METRC_LICENSE_PROCESSING', 'MP281433')


class MetrcSupabaseSync:
    """Handles syncing Metrc data to Supabase."""
    
    def __init__(self, password: Optional[str] = None):
        """Initialize sync with Metrc and Supabase connections."""
        # Metrc API clients
        config = MetrcConfig.from_env()
        self.metrc_client = MetrcClient(config)
        self.cultivation = CultivationClient(self.metrc_client)
        self.processing = ProcessingClient(self.metrc_client)
        
        # Supabase connection
        self.conn_string = get_connection_string(password)
        self.conn = None
        
    def connect_supabase(self):
        """Connect to Supabase database."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(self.conn_string)
            self.conn.autocommit = False
        
    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()
    
    def log_sync_start(self, entity_type: str, license_number: str, sync_type: str, 
                       date_range_start: Optional[datetime] = None,
                       date_range_end: Optional[datetime] = None) -> str:
        """Log sync start and return sync ID."""
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        sync_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO metrc_sync_log 
            (id, entity_type, license_number, sync_type, sync_start, 
             date_range_start, date_range_end, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'running')
        """, (sync_id, entity_type, license_number, sync_type, datetime.now(),
              date_range_start, date_range_end))
        
        self.conn.commit()
        return sync_id
    
    def log_sync_end(self, sync_id: str, records_pulled: int, 
                     records_inserted: int, records_updated: int,
                     status: str = 'completed', error_message: Optional[str] = None):
        """Log sync completion."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE metrc_sync_log
            SET sync_end = %s,
                records_pulled = %s,
                records_inserted = %s,
                records_updated = %s,
                status = %s,
                error_message = %s
            WHERE id = %s
        """, (datetime.now(), records_pulled, records_inserted, records_updated,
              status, error_message, sync_id))
        
        self.conn.commit()
    
    def upsert_harvests(self, harvests: List[Dict], license_number: str) -> tuple:
        """
        Upsert harvests to Supabase.
        
        Returns:
            (inserted_count, updated_count)
        """
        if not harvests:
            return (0, 0)
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for harvest in harvests:
            # Check if exists
            cursor.execute("SELECT id FROM metrc_harvests WHERE id = %s", (harvest['Id'],))
            exists = cursor.fetchone() is not None
            
            # Prepare data
            data = {
                'id': harvest['Id'],
                'harvest_name': harvest['Name'],
                'license_number': license_number,
                'harvest_type': harvest.get('HarvestType'),
                'source_strain_count': harvest.get('SourceStrainCount'),
                'source_strain_names': harvest.get('SourceStrainNames'),
                'drying_location_name': harvest.get('DryingLocationName'),
                'harvest_start_date': harvest.get('HarvestStartDate'),
                'finished_date': harvest.get('FinishedDate'),
                'is_finished': harvest.get('IsFinished', False),
                'current_weight': harvest.get('CurrentWeight'),
                'total_waste_weight': harvest.get('TotalWasteWeight'),
                'total_packaged_weight': harvest.get('TotalPackagedWeight'),
                'total_restorative_waste_weight': harvest.get('TotalRestorativeWasteWeight'),
                'unit_of_weight': harvest.get('UnitOfWeightName'),
                'lab_testing_state': harvest.get('LabTestingState'),
                'lab_testing_state_date': harvest.get('LabTestingStateDate'),
                'is_on_hold': harvest.get('IsOnHold', False),
                'last_modified': harvest.get('LastModified'),
                'data': json.dumps(harvest),
                'synced_at': datetime.now()
            }
            
            if exists:
                # Update existing
                cursor.execute("""
                    UPDATE metrc_harvests SET
                        harvest_name = %(harvest_name)s,
                        license_number = %(license_number)s,
                        harvest_type = %(harvest_type)s,
                        source_strain_count = %(source_strain_count)s,
                        source_strain_names = %(source_strain_names)s,
                        drying_location_name = %(drying_location_name)s,
                        harvest_start_date = %(harvest_start_date)s,
                        harvest_date = %(harvest_date)s,
                        finished_date = %(finished_date)s,
                        is_finished = %(is_finished)s,
                        current_weight = %(current_weight)s,
                        total_waste_weight = %(total_waste_weight)s,
                        total_packaged_weight = %(total_packaged_weight)s,
                        total_restorative_waste_weight = %(total_restorative_waste_weight)s,
                        packaged_date = %(packaged_date)s,
                        unit_of_weight = %(unit_of_weight)s,
                        lab_testing_state = %(lab_testing_state)s,
                        lab_testing_state_date = %(lab_testing_state_date)s,
                        is_on_hold = %(is_on_hold)s,
                        last_modified = %(last_modified)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s
                """, data)
                updated += 1
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO metrc_harvests (
                        id, harvest_name, license_number, harvest_type,
                        source_strain_count, source_strain_names, drying_location_name,
                        harvest_start_date, harvest_date, finished_date, is_finished,
                        current_weight, total_waste_weight, total_packaged_weight,
                        total_restorative_waste_weight, packaged_date, unit_of_weight,
                        lab_testing_state, lab_testing_state_date, is_on_hold,
                        last_modified, data, synced_at
                    ) VALUES (
                        %(id)s, %(harvest_name)s, %(license_number)s, %(harvest_type)s,
                        %(source_strain_count)s, %(source_strain_names)s, %(drying_location_name)s,
                        %(harvest_start_date)s, %(harvest_date)s, %(finished_date)s, %(is_finished)s,
                        %(current_weight)s, %(total_waste_weight)s, %(total_packaged_weight)s,
                        %(total_restorative_waste_weight)s, %(packaged_date)s, %(unit_of_weight)s,
                        %(lab_testing_state)s, %(lab_testing_state_date)s, %(is_on_hold)s,
                        %(last_modified)s, %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        return (inserted, updated)
    
    def upsert_packages(self, packages: List[Dict], license_number: str, status: str = 'active') -> tuple:
        """
        Upsert packages to Supabase.
        
        Args:
            packages: List of package dicts from Metrc API
            license_number: License number for the packages
            status: Package status ('active', 'inactive', or 'intransit')
        
        Returns:
            (inserted_count, updated_count)
        """
        if not packages:
            return (0, 0)
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for package in packages:
            # Check if exists
            cursor.execute("SELECT id FROM metrc_packages WHERE id = %s", (package['Id'],))
            exists = cursor.fetchone() is not None
            
            # Prepare data
            data = {
                'id': package['Id'],
                'label': package['Label'],
                'package_type': package.get('PackageType'),
                'license_number': license_number,
                'product_name': package.get('Item', {}).get('Name') if isinstance(package.get('Item'), dict) else package.get('ProductName'),
                'product_category_name': package.get('Item', {}).get('ProductCategoryName') if isinstance(package.get('Item'), dict) else package.get('ProductCategoryName'),
                'item_name': package.get('Item', {}).get('Name') if isinstance(package.get('Item'), dict) else package.get('ItemName'),
                'item_id': package.get('Item', {}).get('Id') if isinstance(package.get('Item'), dict) else package.get('ItemId'),
                'quantity': package.get('Quantity'),
                'unit_of_measure': package.get('UnitOfMeasureName'),
                'packaged_date': package.get('PackagedDate'),
                'initial_lab_testing_state': package.get('InitialLabTestingState'),
                'lab_testing_state': package.get('LabTestingState'),
                'lab_testing_state_date': package.get('LabTestingStateDate'),
                'is_production_batch': package.get('IsProductionBatch', False),
                'production_batch_number': package.get('ProductionBatchNumber'),
                'source_production_batch_numbers': package.get('SourceProductionBatchNumbers'),
                'source_package_labels': package.get('SourcePackageLabels'),
                'source_harvest_names': package.get('SourceHarvestNames'),
                'is_trade_sample': package.get('IsTradeSample', False),
                'is_testing_sample': package.get('IsTestingSample', False),
                'is_process_validation_test_sample': package.get('IsProcessValidationTestSample', False),
                'is_donation': package.get('IsDonation', False),
                'is_on_hold': package.get('IsOnHold', False),
                'archived_date': package.get('ArchivedDate'),
                'finished_date': package.get('FinishedDate'),
                'location_name': package.get('LocationName'),
                'note': package.get('Note'),
                'last_modified': package.get('LastModified'),
                # Transfer/receiving fields
                'received_datetime': package.get('ReceivedDateTime'),
                'received_from_manifest_number': package.get('ReceivedFromManifestNumber'),
                'received_from_facility_license_number': package.get('ReceivedFromFacilityLicenseNumber'),
                'received_from_facility_name': package.get('ReceivedFromFacilityName'),
                'item_from_facility_license_number': package.get('ItemFromFacilityLicenseNumber'),
                'item_from_facility_name': package.get('ItemFromFacilityName'),
                # Status flags
                'is_donation_persistent': package.get('IsDonationPersistent', False),
                'is_finished': package.get('IsFinished', False),
                'is_on_hold_combined': package.get('IsOnHoldCombined', False),
                'is_on_retailer_delivery': package.get('IsOnRetailerDelivery', False),
                'is_process_validation_testing_sample': package.get('IsProcessValidationTestingSample', False),
                'is_trade_sample_persistent': package.get('IsTradeSamplePersistent', False),
                # Location details
                'location_id': package.get('LocationId'),
                'location_type_name': package.get('LocationTypeName'),
                'sublocation_id': package.get('SublocationId'),
                'sublocation_name': package.get('SublocationName'),
                # Date fields
                'decontamination_date': package.get('DecontaminationDate'),
                'expiration_date': package.get('ExpirationDate'),
                'lab_test_result_expiration_datetime': package.get('LabTestResultExpirationDateTime'),
                'lab_testing_performed_date': package.get('LabTestingPerformedDate'),
                'lab_testing_recorded_date': package.get('LabTestingRecordedDate'),
                'labels_last_generated_datetime': package.get('LabelsLastGeneratedDateTime'),
                'remediation_date': package.get('RemediationDate'),
                'sell_by_date': package.get('SellByDate'),
                'use_by_date': package.get('UseByDate'),
                # Lab/testing fields
                'lab_test_stage': package.get('LabTestStage'),
                'lab_test_stage_id': package.get('LabTestStageId'),
                'product_label': package.get('ProductLabel'),
                # Source tracking
                'source_harvest_count': package.get('SourceHarvestCount'),
                'source_package_count': package.get('SourcePackageCount'),
                'source_package_is_donation': package.get('SourcePackageIsDonation', False),
                'source_package_is_trade_sample': package.get('SourcePackageIsTradeSample', False),
                'source_processing_job_count': package.get('SourceProcessingJobCount'),
                # Other metadata
                'contains_decontaminated_product': package.get('ContainsDecontaminatedProduct', False),
                'contains_remediated_product': package.get('ContainsRemediatedProduct', False),
                'external_id': package.get('ExternalId'),
                'original_package_quantity': package.get('OriginalPackageQuantity'),
                'package_for_product_destruction': package.get('PackageForProductDestruction'),
                'patient_license_number': package.get('PatientLicenseNumber'),
                'product_requires_decontamination': package.get('ProductRequiresDecontamination', False),
                'product_requires_remediation': package.get('ProductRequiresRemediation', False),
                'unit_of_measure_abbreviation': package.get('UnitOfMeasureAbbreviation'),
                'data': json.dumps(package),
                'synced_at': datetime.now(),
                'package_status': status  # Track which endpoint returned this package
            }
            
            if exists:
                # Update existing
                cursor.execute("""
                    UPDATE metrc_packages SET
                        label = %(label)s,
                        package_type = %(package_type)s,
                        license_number = %(license_number)s,
                        product_name = %(product_name)s,
                        product_category_name = %(product_category_name)s,
                        item_name = %(item_name)s,
                        item_id = %(item_id)s,
                        quantity = %(quantity)s,
                        unit_of_measure = %(unit_of_measure)s,
                        packaged_date = %(packaged_date)s,
                        initial_lab_testing_state = %(initial_lab_testing_state)s,
                        lab_testing_state = %(lab_testing_state)s,
                        lab_testing_state_date = %(lab_testing_state_date)s,
                        is_production_batch = %(is_production_batch)s,
                        production_batch_number = %(production_batch_number)s,
                        source_production_batch_numbers = %(source_production_batch_numbers)s,
                        source_package_labels = %(source_package_labels)s,
                        source_harvest_names = %(source_harvest_names)s,
                        is_trade_sample = %(is_trade_sample)s,
                        is_testing_sample = %(is_testing_sample)s,
                        is_process_validation_test_sample = %(is_process_validation_test_sample)s,
                        is_donation = %(is_donation)s,
                        is_on_hold = %(is_on_hold)s,
                        archived_date = %(archived_date)s,
                        finished_date = %(finished_date)s,
                        location_name = %(location_name)s,
                        note = %(note)s,
                        last_modified = %(last_modified)s,
                        received_datetime = %(received_datetime)s,
                        received_from_manifest_number = %(received_from_manifest_number)s,
                        received_from_facility_license_number = %(received_from_facility_license_number)s,
                        received_from_facility_name = %(received_from_facility_name)s,
                        item_from_facility_license_number = %(item_from_facility_license_number)s,
                        item_from_facility_name = %(item_from_facility_name)s,
                        is_donation_persistent = %(is_donation_persistent)s,
                        is_finished = %(is_finished)s,
                        is_on_hold_combined = %(is_on_hold_combined)s,
                        is_on_retailer_delivery = %(is_on_retailer_delivery)s,
                        is_process_validation_testing_sample = %(is_process_validation_testing_sample)s,
                        is_trade_sample_persistent = %(is_trade_sample_persistent)s,
                        location_id = %(location_id)s,
                        location_type_name = %(location_type_name)s,
                        sublocation_id = %(sublocation_id)s,
                        sublocation_name = %(sublocation_name)s,
                        decontamination_date = %(decontamination_date)s,
                        expiration_date = %(expiration_date)s,
                        lab_test_result_expiration_datetime = %(lab_test_result_expiration_datetime)s,
                        lab_testing_performed_date = %(lab_testing_performed_date)s,
                        lab_testing_recorded_date = %(lab_testing_recorded_date)s,
                        labels_last_generated_datetime = %(labels_last_generated_datetime)s,
                        remediation_date = %(remediation_date)s,
                        sell_by_date = %(sell_by_date)s,
                        use_by_date = %(use_by_date)s,
                        lab_test_stage = %(lab_test_stage)s,
                        lab_test_stage_id = %(lab_test_stage_id)s,
                        product_label = %(product_label)s,
                        source_harvest_count = %(source_harvest_count)s,
                        source_package_count = %(source_package_count)s,
                        source_package_is_donation = %(source_package_is_donation)s,
                        source_package_is_trade_sample = %(source_package_is_trade_sample)s,
                        source_processing_job_count = %(source_processing_job_count)s,
                        contains_decontaminated_product = %(contains_decontaminated_product)s,
                        contains_remediated_product = %(contains_remediated_product)s,
                        external_id = %(external_id)s,
                        original_package_quantity = %(original_package_quantity)s,
                        package_for_product_destruction = %(package_for_product_destruction)s,
                        patient_license_number = %(patient_license_number)s,
                        product_requires_decontamination = %(product_requires_decontamination)s,
                        product_requires_remediation = %(product_requires_remediation)s,
                        unit_of_measure_abbreviation = %(unit_of_measure_abbreviation)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s,
                        package_status = %(package_status)s
                    WHERE id = %(id)s
                """, data)
                updated += 1
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO metrc_packages (
                        id, label, package_type, license_number,
                        product_name, product_category_name, item_name, item_id,
                        quantity, unit_of_measure, packaged_date,
                        initial_lab_testing_state, lab_testing_state, lab_testing_state_date,
                        is_production_batch, production_batch_number,
                        source_production_batch_numbers, source_package_labels, source_harvest_names,
                        is_trade_sample, is_testing_sample, is_process_validation_test_sample,
                        is_donation, is_on_hold, archived_date, finished_date,
                        location_name, note, last_modified,
                        received_datetime, received_from_manifest_number,
                        received_from_facility_license_number, received_from_facility_name,
                        item_from_facility_license_number, item_from_facility_name,
                        is_donation_persistent, is_finished, is_on_hold_combined, is_on_retailer_delivery,
                        is_process_validation_testing_sample, is_trade_sample_persistent,
                        location_id, location_type_name, sublocation_id, sublocation_name,
                        decontamination_date, expiration_date, lab_test_result_expiration_datetime,
                        lab_testing_performed_date, lab_testing_recorded_date, labels_last_generated_datetime,
                        remediation_date, sell_by_date, use_by_date,
                        lab_test_stage, lab_test_stage_id, product_label,
                        source_harvest_count, source_package_count, source_package_is_donation,
                        source_package_is_trade_sample, source_processing_job_count,
                        contains_decontaminated_product, contains_remediated_product,
                        external_id, original_package_quantity, package_for_product_destruction,
                        patient_license_number, product_requires_decontamination, product_requires_remediation,
                        unit_of_measure_abbreviation,
                        data, synced_at, package_status
                    ) VALUES (
                        %(id)s, %(label)s, %(package_type)s, %(license_number)s,
                        %(product_name)s, %(product_category_name)s, %(item_name)s, %(item_id)s,
                        %(quantity)s, %(unit_of_measure)s, %(packaged_date)s,
                        %(initial_lab_testing_state)s, %(lab_testing_state)s, %(lab_testing_state_date)s,
                        %(is_production_batch)s, %(production_batch_number)s,
                        %(source_production_batch_numbers)s, %(source_package_labels)s, %(source_harvest_names)s,
                        %(is_trade_sample)s, %(is_testing_sample)s, %(is_process_validation_test_sample)s,
                        %(is_donation)s, %(is_on_hold)s, %(archived_date)s, %(finished_date)s,
                        %(location_name)s, %(note)s, %(last_modified)s,
                        %(received_datetime)s, %(received_from_manifest_number)s,
                        %(received_from_facility_license_number)s, %(received_from_facility_name)s,
                        %(item_from_facility_license_number)s, %(item_from_facility_name)s,
                        %(is_donation_persistent)s, %(is_finished)s, %(is_on_hold_combined)s, %(is_on_retailer_delivery)s,
                        %(is_process_validation_testing_sample)s, %(is_trade_sample_persistent)s,
                        %(location_id)s, %(location_type_name)s, %(sublocation_id)s, %(sublocation_name)s,
                        %(decontamination_date)s, %(expiration_date)s, %(lab_test_result_expiration_datetime)s,
                        %(lab_testing_performed_date)s, %(lab_testing_recorded_date)s, %(labels_last_generated_datetime)s,
                        %(remediation_date)s, %(sell_by_date)s, %(use_by_date)s,
                        %(lab_test_stage)s, %(lab_test_stage_id)s, %(product_label)s,
                        %(source_harvest_count)s, %(source_package_count)s, %(source_package_is_donation)s,
                        %(source_package_is_trade_sample)s, %(source_processing_job_count)s,
                        %(contains_decontaminated_product)s, %(contains_remediated_product)s,
                        %(external_id)s, %(original_package_quantity)s, %(package_for_product_destruction)s,
                        %(patient_license_number)s, %(product_requires_decontamination)s, %(product_requires_remediation)s,
                        %(unit_of_measure_abbreviation)s,
                        %(data)s, %(synced_at)s, %(package_status)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        return (inserted, updated)

    # --------------------------- transfer enrichment ---------------------------
    def enrich_transfers_with_deliveries(self, transfers: List[Dict], license_number: str) -> List[Dict]:
        """
        Comprehensive transfer enrichment with packages and transporter details.
        
        For each transfer, fetches:
        1. Delivery packages (with wholesale pricing)
        2. Transporter/driver/vehicle details
        
        Stores enriched data in transfer_packages and transfer_transporters tables.
        """
        if not transfers:
            return transfers

        enriched: List[Dict] = []
        packages_enriched = 0
        transporters_enriched = 0
        
        for transfer in transfers:
            transfer_id = transfer.get('Id')
            manifest = transfer.get('ManifestNumber', 'Unknown')
            direction = transfer.get('_direction', 'incoming')  # Get direction tag, default to incoming
            
            # Check if transfer already has Deliveries embedded
            if transfer.get('Deliveries'):
                enriched.append(transfer)
                # Still try to get transporter details even if Deliveries exist
                try:
                    self._fetch_and_store_transporter_details(transfer_id, transfer.get('DeliveryId'), license_number)
                except:
                    pass
                continue

            # Use DeliveryId if available
            delivery_id = transfer.get('DeliveryId')
            if not delivery_id:
                enriched.append(transfer)
                continue

            try:
                # Fetch delivery packages with wholesale pricing
                detail = self.processing.get_transfer_delivery(delivery_id, license_number=license_number)
                packages = None
                if isinstance(detail, dict):
                    packages = detail.get('Data', [])
                elif isinstance(detail, list):
                    packages = detail

                if packages:
                    # Store packages in database with direction
                    stored_count = self.upsert_transfer_packages(transfer_id, delivery_id, packages, direction)
                    # upsert_transfer_packages commits at end, so transaction is clean
                    
                    # Add to transfer object for JSON storage
                    transfer['Deliveries'] = [{'Packages': packages, 'Id': delivery_id}]
                    packages_enriched += 1
                    print(f"        ✓ Stored {stored_count} packages for transfer {manifest}")
                
                # Fetch and store transporter details (separate try/catch to not fail entire enrichment)
                try:
                    transporter_stored = self._fetch_and_store_transporter_details(
                        transfer_id, delivery_id, license_number
                    )
                    if transporter_stored:
                        transporters_enriched += 1
                except Exception as e:
                    # Transporter fetch can fail - they're optional metadata
                    # _fetch_and_store_transporter_details handles its own transaction
                    pass
                    
            except Exception as e:
                print(f"      ✗ Transfer enrichment failed for {manifest}: {e}")
                # Rollback any failed transaction so subsequent transfers can continue
                try:
                    if self.conn:
                        self.conn.rollback()
                except:
                    pass

            enriched.append(transfer)
        
        if packages_enriched > 0:
            print(f"      ✓ Enriched {packages_enriched} transfers with package data")
        if transporters_enriched > 0:
            print(f"      ✓ Enriched {transporters_enriched} transfers with transporter data")

        return enriched
    
    def _fetch_and_store_transporter_details(
        self, 
        transfer_id: int, 
        delivery_id: Optional[int], 
        license_number: str
    ) -> bool:
        """Fetch and store transporter details for a delivery."""
        if not delivery_id:
            return False
        
        try:
            # Fetch transporter data
            endpoint = f"transfers/v2/deliveries/{delivery_id}/transporters"
            transporter_data = self.processing.client.get(endpoint, license_number=license_number)
            
            transporters = None
            if isinstance(transporter_data, dict):
                transporters = transporter_data.get('Data', [])
            elif isinstance(transporter_data, list):
                transporters = transporter_data
            
            if transporters:
                self.upsert_transfer_transporters(transfer_id, delivery_id, transporters)
                return True
                
        except Exception as e:
            # Transporter endpoint may not be available for all deliveries
            # Don't treat this as a critical error
            pass
        
        return False
    
    def sync_harvests_incremental(self, license_number: str, hours: int = 48):
        """Sync harvests modified in last N hours."""
        print(f"Syncing harvests for {license_number} (last {hours} hours)...")
        
        end = datetime.now()
        start = end - timedelta(hours=hours)
        
        sync_id = self.log_sync_start('harvests', license_number, 'incremental', start, end)
        
        try:
            # Get active harvests
            active_response = self.cultivation.get_harvests('active', license_number=license_number)
            active_harvests = active_response['Data'] if isinstance(active_response, dict) and 'Data' in active_response else []
            
            # Get inactive harvests in last 48 hours (in 24-hour chunks to avoid API limit)
            inactive_harvests = []
            current_start = start
            
            while current_start < end:
                current_end = min(current_start + timedelta(hours=24), end)
                
                start_str = current_start.strftime('%Y-%m-%dT%H:%M:%S')
                end_str = current_end.strftime('%Y-%m-%dT%H:%M:%S')
                
                chunk_response = self.cultivation.get_harvests(
                    'inactive',
                    license_number=license_number,
                    last_modified_start=start_str,
                    last_modified_end=end_str
                )
                chunk = chunk_response['Data'] if isinstance(chunk_response, dict) and 'Data' in chunk_response else []
                inactive_harvests.extend(chunk)
                
                current_start = current_end
            
            all_harvests = active_harvests + inactive_harvests
            
            print(f"  Found {len(active_harvests)} active, {len(inactive_harvests)} inactive = {len(all_harvests)} total")
            
            # Upsert to Supabase
            inserted, updated = self.upsert_harvests(all_harvests, license_number)
            
            print(f"  ✓ Inserted {inserted}, Updated {updated}")
            
            self.log_sync_end(sync_id, len(all_harvests), inserted, updated)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            self.log_sync_end(sync_id, 0, 0, 0, 'failed', str(e))
            raise
    
    def sync_packages_incremental(self, license_number: str, hours: int = 48):
        """Sync packages modified in last N hours from active, inactive, and intransit endpoints."""
        print(f"Syncing packages for {license_number} (last {hours} hours)...")
        
        end = datetime.now()
        start = end - timedelta(hours=hours)
        
        sync_id = self.log_sync_start('packages', license_number, 'incremental', start, end)
        
        try:
            # Get active packages
            active_response = self.processing.get_packages('active', license_number=license_number)
            active_packages = active_response['Data'] if isinstance(active_response, dict) and 'Data' in active_response else active_response
            
            # Get inactive packages in last 48 hours (in 24-hour chunks)
            inactive_packages = []
            current_start = start
            
            while current_start < end:
                current_end = min(current_start + timedelta(hours=24), end)
                
                start_str = current_start.strftime('%Y-%m-%dT%H:%M:%S')
                end_str = current_end.strftime('%Y-%m-%dT%H:%M:%S')
                
                chunk_response = self.processing.get_packages(
                    'inactive',
                    license_number=license_number,
                    last_modified_start=start_str,
                    last_modified_end=end_str
                )
                chunk = chunk_response['Data'] if isinstance(chunk_response, dict) and 'Data' in chunk_response else chunk_response
                inactive_packages.extend(chunk)
                
                current_start = current_end
            
            # Get in-transit packages (packages currently being transferred)
            try:
                intransit_response = self.processing.client.get(
                    'packages/v2/intransit',
                    params={},
                    license_number=license_number,
                    paginate=True
                )
                intransit_packages = intransit_response if isinstance(intransit_response, list) else []
            except Exception as e:
                print(f"  Note: Could not fetch intransit packages: {e}")
                intransit_packages = []
            
            print(f"  Found {len(active_packages)} active, {len(inactive_packages)} inactive, {len(intransit_packages)} intransit = {len(active_packages) + len(inactive_packages) + len(intransit_packages)} total")
            
            # Upsert to Supabase with status tracking
            inserted_active, updated_active = self.upsert_packages(active_packages, license_number, status='active')
            inserted_inactive, updated_inactive = self.upsert_packages(inactive_packages, license_number, status='inactive')
            inserted_intransit, updated_intransit = self.upsert_packages(intransit_packages, license_number, status='intransit')
            
            total_inserted = inserted_active + inserted_inactive + inserted_intransit
            total_updated = updated_active + updated_inactive + updated_intransit
            
            print(f"  ✓ Inserted {total_inserted}, Updated {total_updated}")
            
            self.log_sync_end(sync_id, len(active_packages) + len(inactive_packages) + len(intransit_packages), total_inserted, total_updated)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            self.log_sync_end(sync_id, 0, 0, 0, 'failed', str(e))
            raise
    
    def sync_transfers_incremental(self, license_number: str, days: int = 7):
        """Sync transfers for last N days (chunked into 24-hour windows)."""
        print(f"Syncing transfers for {license_number} (last {days} days)...")
        
        end = datetime.now()
        start = end - timedelta(days=days)
        
        sync_id = self.log_sync_start('transfers', license_number, 'incremental', start, end)
        
        try:
            # Chunk into 24-hour windows
            all_transfers = []
            current = start
            
            while current < end:
                # Each chunk is 24 hours
                chunk_end = min(current + timedelta(hours=24), end)
                start_str = current.strftime('%Y-%m-%d')
                end_str = chunk_end.strftime('%Y-%m-%d')
                
                # Get incoming transfers
                incoming_response = self.processing.get_incoming_transfers(
                    license_number=license_number,
                    last_modified_start=start_str,
                    last_modified_end=end_str
                )
                incoming = incoming_response['Data'] if isinstance(incoming_response, dict) and 'Data' in incoming_response else []
                # Tag with direction
                for t in incoming:
                    t['_direction'] = 'incoming'
                
                # Get outgoing transfers
                outgoing_response = self.processing.get_outgoing_transfers(
                    license_number=license_number,
                    last_modified_start=start_str,
                    last_modified_end=end_str
                )
                outgoing = outgoing_response['Data'] if isinstance(outgoing_response, dict) and 'Data' in outgoing_response else []
                # Tag with direction
                for t in outgoing:
                    t['_direction'] = 'outgoing'
                
                all_transfers.extend(incoming + outgoing)
                current = chunk_end
            
            # Remove duplicates based on Id
            seen_ids = set()
            unique_transfers = []
            for transfer in all_transfers:
                if transfer['Id'] not in seen_ids:
                    seen_ids.add(transfer['Id'])
                    unique_transfers.append(transfer)
            
            print(f"  Found {len(unique_transfers)} unique transfers")
            
            # Ensure deliveries are present; fetch per-transfer if missing
            enriched_transfers = self.enrich_transfers_with_deliveries(unique_transfers, license_number)

            # Upsert to Supabase
            inserted, updated = self.upsert_transfers(enriched_transfers, license_number)
            
            print(f"  ✓ Inserted {inserted}, Updated {updated}")
            
            self.log_sync_end(sync_id, len(unique_transfers), inserted, updated)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            self.log_sync_end(sync_id, 0, 0, 0, 'failed', str(e))
            raise
    
    def sync_plants(self, license_number: str):
        """
        Sync plants and plant batches.
        Fetches all active and inactive plants/batches (no time filtering available).
        """
        print(f"Syncing plants for {license_number}...")
        
        sync_id = self.log_sync_start('plants', license_number, 'full', None, None)
        
        try:
            total_plants = 0
            total_batches = 0
            
            # Sync plants from all phases
            phases = ['vegetative', 'flowering', 'onhold', 'inactive']
            all_plants = []
            
            for phase in phases:
                try:
                    result = self.cultivation.get_plants(license_number=license_number, phase=phase)
                    # Handle response format
                    if isinstance(result, dict):
                        plants = result.get('Data', [])
                    elif isinstance(result, list):
                        plants = result
                    else:
                        plants = []
                    all_plants.extend(plants)
                    if len(plants) > 0:
                        print(f"  Found {len(plants)} {phase} plants")
                except Exception as e:
                    # Plant endpoints might not exist for processing licenses
                    if 'Authentication failed' not in str(e):
                        print(f"  Warning: Error fetching {phase} plants: {e}")
            
            # Upsert plants
            if all_plants:
                inserted, updated = self.upsert_plants(all_plants, license_number)
                total_plants = len(all_plants)
                print(f"  ✓ Plants: {inserted} inserted, {updated} updated")
            
            # Sync plant batches
            all_batches = []
            for status in ['active', 'inactive']:
                try:
                    result = self.cultivation.get_plant_batches(license_number=license_number, status=status)
                    # Handle response format
                    if isinstance(result, dict):
                        batches = result.get('Data', [])
                    elif isinstance(result, list):
                        batches = result
                    else:
                        batches = []
                    all_batches.extend(batches)
                    if len(batches) > 0:
                        print(f"  Found {len(batches)} {status} plant batches")
                except Exception as e:
                    if 'Authentication failed' not in str(e):
                        print(f"  Warning: Error fetching {status} batches: {e}")
            
            # Upsert plant batches
            if all_batches:
                inserted, updated = self.upsert_plant_batches(all_batches, license_number)
                total_batches = len(all_batches)
                print(f"  ✓ Plant Batches: {inserted} inserted, {updated} updated")
            
            self.log_sync_end(sync_id, total_plants + total_batches, 0, 0)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            self.log_sync_end(sync_id, 0, 0, 0, 'failed', str(e))
            raise
    
    def upsert_plants(self, plants: List[Dict], license_number: str) -> tuple:
        """Upsert plants to metrc_plants table."""
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for plant in plants:
            plant_id = plant.get('Id')
            plant_label = plant.get('Label')
            
            # Check if exists
            cursor.execute("""
                SELECT id FROM metrc_plants 
                WHERE id = %s AND license_number = %s
            """, (plant_id, license_number))
            
            exists = cursor.fetchone() is not None
            
            data = {
                'id': plant_id,
                'label': plant_label,
                'license_number': license_number,
                'plant_batch_id': plant.get('PlantBatchId'),
                'plant_batch_name': plant.get('PlantBatchName'),
                'strain_name': plant.get('StrainName'),
                'location_name': plant.get('LocationName'),
                'plant_state': plant.get('State'),
                'growth_phase': plant.get('GrowthPhase'),
                'planted_date': plant.get('PlantedDate'),
                'vegetative_date': plant.get('VegetativeDate'),
                'flowering_date': plant.get('FloweringDate'),
                'harvested_date': plant.get('HarvestedDate'),
                'destroyed_date': plant.get('DestroyedDate'),
                'is_on_hold': plant.get('IsOnHold'),
                'last_modified': plant.get('LastModified'),
                'data': json.dumps(plant),
                'synced_at': datetime.now()
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_plants SET
                        label = %(label)s,
                        plant_batch_id = %(plant_batch_id)s,
                        plant_batch_name = %(plant_batch_name)s,
                        strain_name = %(strain_name)s,
                        location_name = %(location_name)s,
                        plant_state = %(plant_state)s,
                        growth_phase = %(growth_phase)s,
                        planted_date = %(planted_date)s,
                        vegetative_date = %(vegetative_date)s,
                        flowering_date = %(flowering_date)s,
                        harvested_date = %(harvested_date)s,
                        destroyed_date = %(destroyed_date)s,
                        is_on_hold = %(is_on_hold)s,
                        last_modified = %(last_modified)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s AND license_number = %(license_number)s
                """, data)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO metrc_plants (
                        id, label, license_number, plant_batch_id, plant_batch_name,
                        strain_name, location_name, plant_state, growth_phase,
                        planted_date, vegetative_date, flowering_date, harvested_date,
                        destroyed_date, is_on_hold, last_modified, data, synced_at
                    ) VALUES (
                        %(id)s, %(label)s, %(license_number)s, %(plant_batch_id)s, %(plant_batch_name)s,
                        %(strain_name)s, %(location_name)s, %(plant_state)s, %(growth_phase)s,
                        %(planted_date)s, %(vegetative_date)s, %(flowering_date)s, %(harvested_date)s,
                        %(destroyed_date)s, %(is_on_hold)s, %(last_modified)s, %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        cursor.close()
        
        return (inserted, updated)
    
    def upsert_plant_batches(self, batches: List[Dict], license_number: str) -> tuple:
        """Upsert plant batches to metrc_plant_batches table."""
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for batch in batches:
            batch_id = batch.get('Id')
            batch_name = batch.get('Name')
            
            # Check if exists
            cursor.execute("""
                SELECT id FROM metrc_plant_batches 
                WHERE id = %s AND license_number = %s
            """, (batch_id, license_number))
            
            exists = cursor.fetchone() is not None
            
            data = {
                'id': batch_id,
                'batch_name': batch_name,
                'license_number': license_number,
                'batch_type': batch.get('Type'),
                'strain_name': batch.get('StrainName'),
                'location_name': batch.get('LocationName'),
                'plant_count': batch.get('Count'),
                'packaged_date': batch.get('PackagedDate'),
                'planted_date': batch.get('PlantedDate'),
                'destroyed_date': batch.get('DestroyedDate'),
                'is_destroyed': batch.get('DestroyedDate') is not None,
                'destroyed_count': batch.get('DestroyedCount'),
                'last_modified': batch.get('LastModified'),
                'data': json.dumps(batch),
                'synced_at': datetime.now()
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_plant_batches SET
                        batch_name = %(batch_name)s,
                        batch_type = %(batch_type)s,
                        strain_name = %(strain_name)s,
                        location_name = %(location_name)s,
                        plant_count = %(plant_count)s,
                        packaged_date = %(packaged_date)s,
                        planted_date = %(planted_date)s,
                        destroyed_date = %(destroyed_date)s,
                        is_destroyed = %(is_destroyed)s,
                        destroyed_count = %(destroyed_count)s,
                        last_modified = %(last_modified)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s AND license_number = %(license_number)s
                """, data)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO metrc_plant_batches (
                        id, batch_name, license_number, batch_type, strain_name,
                        location_name, plant_count, packaged_date, planted_date,
                        destroyed_date, is_destroyed, destroyed_count,
                        last_modified, data, synced_at
                    ) VALUES (
                        %(id)s, %(batch_name)s, %(license_number)s, %(batch_type)s, %(strain_name)s,
                        %(location_name)s, %(plant_count)s, %(packaged_date)s, %(planted_date)s,
                        %(destroyed_date)s, %(is_destroyed)s, %(destroyed_count)s,
                        %(last_modified)s, %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        cursor.close()
        
        return (inserted, updated)
    
    def upsert_transfer_packages(
        self, 
        transfer_id: int, 
        delivery_id: int, 
        packages: List[Dict],
        direction: str = 'incoming'
    ) -> int:
        """
        Store transfer package details with wholesale pricing.
        
        Args:
            transfer_id: Transfer ID
            delivery_id: Delivery ID
            packages: List of package dicts from delivery endpoint
            direction: 'incoming' or 'outgoing'
        
        Returns:
            Number of packages stored
        """
        if not packages:
            return 0
        
        self.connect_supabase()
        
        # Ensure we start with a clean transaction state
        try:
            self.conn.commit()
        except:
            try:
                self.conn.rollback()
            except:
                pass
        
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for pkg in packages:
            # Check if exists
            cursor.execute("""
                SELECT id FROM metrc_transfer_packages 
                WHERE transfer_id = %s AND package_label = %s AND direction = %s
            """, (transfer_id, pkg.get('PackageLabel'), direction))
            exists = cursor.fetchone() is not None
            
            data = {
                'transfer_id': transfer_id,
                'delivery_id': delivery_id,
                'direction': direction,  # Add direction field
                'package_id': pkg.get('PackageId'),
                'package_label': pkg.get('PackageLabel'),
                'package_type': pkg.get('PackageType'),
                'product_name': pkg.get('ProductName'),
                'product_category_name': pkg.get('ProductCategoryName'),
                'item_id': pkg.get('ItemId'),
                'item_name': pkg.get('ItemName'),
                'item_category_name': pkg.get('ItemCategoryName'),
                'item_strain_name': pkg.get('ItemStrainName'),
                'source_harvest_names': pkg.get('SourceHarvestNames'),
                'source_package_labels': pkg.get('SourcePackageLabels'),
                'quantity_shipped': pkg.get('QuantityShipped') or pkg.get('ShippedQuantity'),
                'quantity_received': pkg.get('QuantityReceived') or pkg.get('ReceivedQuantity'),
                'unit_of_measure_name': pkg.get('UnitOfMeasureName'),
                'unit_of_measure_abbreviation': pkg.get('UnitOfMeasureAbbreviation'),
                'gross_weight': pkg.get('GrossWeight'),
                'gross_unit_of_weight_name': pkg.get('GrossUnitOfWeightName'),
                'gross_unit_of_weight_abbreviation': pkg.get('GrossUnitOfWeightAbbreviation'),
                # WHOLESALE PRICING - KEY FIELDS
                'wholesale_price': pkg.get('WholesalePrice'),
                'shipper_wholesale_price': pkg.get('ShipperWholesalePrice'),
                'receiver_wholesale_price': pkg.get('ReceiverWholesalePrice'),
                # THC/CBD content
                'item_unit_thc_percent': pkg.get('ItemUnitThcPercent'),
                'item_unit_thc_content': pkg.get('ItemUnitThcContent'),
                'item_unit_thc_content_uom': pkg.get('ItemUnitThcContentUnitOfMeasureName'),
                'item_unit_cbd_percent': pkg.get('ItemUnitCbdPercent'),
                'item_unit_cbd_content': pkg.get('ItemUnitCbdContent'),
                'item_unit_cbd_content_uom': pkg.get('ItemUnitCbdContentUnitOfMeasureName'),
                # Package attributes
                'is_testing_sample': pkg.get('IsTestingSample', False),
                'is_process_validation_test_sample': pkg.get('IsProcessValidationTestSample', False),
                'is_production_batch': pkg.get('IsProductionBatch', False),
                'production_batch_number': pkg.get('ProductionBatchNumber'),
                'is_trade_sample': pkg.get('IsTradeSample', False),
                'is_on_hold': pkg.get('IsOnHold', False),
                # Dates
                'packaged_date': pkg.get('PackagedDate'),
                'received_date_time': pkg.get('ReceivedDateTime'),
                'archived_date': pkg.get('ArchivedDate'),
                'finished_date': pkg.get('FinishedDate'),
                'last_modified': pkg.get('LastModified'),
                'data': json.dumps(pkg),
                'synced_at': datetime.now()
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_transfer_packages SET
                        delivery_id = %(delivery_id)s, direction = %(direction)s,
                        package_id = %(package_id)s, package_type = %(package_type)s,
                        product_name = %(product_name)s, product_category_name = %(product_category_name)s,
                        item_id = %(item_id)s, item_name = %(item_name)s, item_category_name = %(item_category_name)s,
                        item_strain_name = %(item_strain_name)s, source_harvest_names = %(source_harvest_names)s,
                        source_package_labels = %(source_package_labels)s, quantity_shipped = %(quantity_shipped)s,
                        quantity_received = %(quantity_received)s, unit_of_measure_name = %(unit_of_measure_name)s,
                        wholesale_price = %(wholesale_price)s, shipper_wholesale_price = %(shipper_wholesale_price)s,
                        receiver_wholesale_price = %(receiver_wholesale_price)s,
                        packaged_date = %(packaged_date)s, received_date_time = %(received_date_time)s,
                        data = %(data)s, synced_at = %(synced_at)s
                    WHERE transfer_id = %(transfer_id)s AND package_label = %(package_label)s AND direction = %(direction)s
                """, data)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO metrc_transfer_packages (
                        transfer_id, delivery_id, direction, package_id, package_label, package_type,
                        product_name, product_category_name, item_id, item_name, item_category_name, item_strain_name,
                        source_harvest_names, source_package_labels, quantity_shipped, quantity_received,
                        unit_of_measure_name, wholesale_price, shipper_wholesale_price, receiver_wholesale_price,
                        packaged_date, received_date_time, data, synced_at
                    ) VALUES (
                        %(transfer_id)s, %(delivery_id)s, %(direction)s, %(package_id)s, %(package_label)s, %(package_type)s,
                        %(product_name)s, %(product_category_name)s, %(item_id)s, %(item_name)s, %(item_category_name)s, %(item_strain_name)s,
                        %(source_harvest_names)s, %(source_package_labels)s, %(quantity_shipped)s, %(quantity_received)s,
                        %(unit_of_measure_name)s, %(wholesale_price)s, %(shipper_wholesale_price)s, %(receiver_wholesale_price)s,
                        %(packaged_date)s, %(received_date_time)s, %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        cursor.close()
        return inserted + updated
    
    def upsert_transfer_transporters(self, transfer_id: int, delivery_id: int, transporters: List[Dict]) -> int:
        """Store transporter/driver/vehicle details."""
        if not transporters:
            return 0
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        for transporter in transporters:
            data = {
                'transfer_id': transfer_id,
                'delivery_id': delivery_id,
                'transporter_facility_license_number': transporter.get('TransporterFacilityLicenseNumber'),
                'driver_name': transporter.get('DriverName'),
                'driver_license_number': transporter.get('DriverLicenseNumber'),
                'vehicle_make': transporter.get('VehicleMake'),
                'vehicle_model': transporter.get('VehicleModel'),
                'vehicle_license_plate_number': transporter.get('VehicleLicensePlateNumber'),
                'phone_number_for_questions': transporter.get('PhoneNumberForQuestions'),
                'actual_departure_date_time': transporter.get('ActualDepartureDateTime'),
                'actual_arrival_date_time': transporter.get('ActualArrivalDateTime'),
                'data': json.dumps(transporter),
                'synced_at': datetime.now()
            }
            
            cursor.execute("""
                INSERT INTO metrc_transfer_transporters (
                    transfer_id, delivery_id, transporter_facility_license_number,
                    driver_name, driver_license_number, vehicle_make, vehicle_model,
                    vehicle_license_plate_number, phone_number_for_questions,
                    actual_departure_date_time, actual_arrival_date_time, data, synced_at
                ) VALUES (
                    %(transfer_id)s, %(delivery_id)s, %(transporter_facility_license_number)s,
                    %(driver_name)s, %(driver_license_number)s, %(vehicle_make)s, %(vehicle_model)s,
                    %(vehicle_license_plate_number)s, %(phone_number_for_questions)s,
                    %(actual_departure_date_time)s, %(actual_arrival_date_time)s, %(data)s, %(synced_at)s
                )
                ON CONFLICT (transfer_id, delivery_id, driver_license_number) 
                DO UPDATE SET synced_at = %(synced_at)s
            """, data)
            inserted += 1
        
        self.conn.commit()
        return inserted
    
    def upsert_transfers(self, transfers: List[Dict], license_number: str) -> tuple:
        """
        Upsert transfers to Supabase.
        
        Returns:
            (inserted_count, updated_count)
        """
        if not transfers:
            return (0, 0)
        
        self.connect_supabase()
        
        # Ensure we're starting with a clean transaction
        try:
            self.conn.rollback()
        except:
            pass
        
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for transfer in transfers:
            # Check if exists and fetch existing data to preserve Deliveries
            cursor.execute("SELECT data FROM metrc_transfers WHERE id = %s", (transfer['Id'],))
            result = cursor.fetchone()
            exists = result is not None
            
            # If updating and existing record has Deliveries but new transfer doesn't, preserve them
            if exists and result:
                existing_data = result[0]
                existing_deliveries = existing_data.get('Deliveries')
                if existing_deliveries and not transfer.get('Deliveries'):
                    transfer['Deliveries'] = existing_deliveries
            
            # Extract facility info from root transfer (not from Deliveries)
            # RecipientFacilityName may be in Deliveries[0] or root depending on context
            deliveries = transfer.get('Deliveries', [])
            recipient_name = transfer.get('RecipientFacilityName')
            recipient_license = transfer.get('RecipientFacilityLicenseNumber')
            if not recipient_name and deliveries:
                recipient_name = deliveries[0].get('RecipientFacilityName')
            if not recipient_license and deliveries:
                recipient_license = deliveries[0].get('RecipientFacilityLicenseNumber')
            
            # Determine transfer type based on shipper AND destination licenses
            # Company licenses: MC281599, MP281433, MR283288, MR284733, MR281800
            # Only intercompany if BOTH shipper and destination are company licenses
            shipper_license = transfer.get('ShipperFacilityLicenseNumber')
            company_licenses = {'MC281599', 'MP281433', 'MR283288', 'MR284733', 'MR281800'}
            is_intercompany = (shipper_license in company_licenses and 
                             recipient_license in company_licenses)
            transfer_type = 'intercompany' if is_intercompany else '3rd party'
            
            data = {
                'id': transfer['Id'],
                'manifest_number': transfer.get('ManifestNumber'),
                'license_number': license_number,
                'shipper_facility_name': transfer.get('ShipperFacilityName'),
                'shipper_facility_license_number': shipper_license,
                'transporter_facility_name': transfer.get('TransporterFacilityName'),
                'transporter_facility_license_number': transfer.get('TransporterFacilityLicenseNumber'),
                'destination_facility_name': recipient_name,
                'destination_facility_license_number': recipient_license,
                'created_date': transfer.get('CreatedDateTime'),
                'transfer_type': transfer_type,
                'shipment_type': transfer.get('ShipmentTypeName'),
                # Note: shipment_license_type not in schema
                'est_departure_datetime': transfer.get('EstimatedDepartureDateTime'),
                'est_arrival_datetime': transfer.get('EstimatedArrivalDateTime'),
                'actual_departure_datetime': transfer.get('ActualDepartureDateTime'),
                'actual_arrival_datetime': transfer.get('ActualArrivalDateTime'),
                'package_count': transfer.get('PackageCount'),
                'delivery_count': transfer.get('DeliveryCount'),
                'received_delivery_count': transfer.get('ReceivedDeliveryCount'),
                'last_modified': transfer.get('LastModified'),
                'direction': transfer.get('_direction', 'incoming'),  # Required by schema
                'data': json.dumps(transfer),
                'synced_at': datetime.now()
            }
            
            if exists:
                # Update existing
                cursor.execute("""
                    UPDATE metrc_transfers SET
                        manifest_number = %(manifest_number)s,
                        license_number = %(license_number)s,
                        shipper_facility_name = %(shipper_facility_name)s,
                        shipper_facility_license_number = %(shipper_facility_license_number)s,
                        transporter_facility_name = %(transporter_facility_name)s,
                        transporter_facility_license_number = %(transporter_facility_license_number)s,
                        destination_facility_name = %(destination_facility_name)s,
                        destination_facility_license_number = %(destination_facility_license_number)s,
                        created_date = %(created_date)s,
                        transfer_type = %(transfer_type)s,
                        shipment_type = %(shipment_type)s,
                        est_departure_datetime = %(est_departure_datetime)s,
                        est_arrival_datetime = %(est_arrival_datetime)s,
                        actual_departure_datetime = %(actual_departure_datetime)s,
                        actual_arrival_datetime = %(actual_arrival_datetime)s,
                        package_count = %(package_count)s,
                        delivery_count = %(delivery_count)s,
                        received_delivery_count = %(received_delivery_count)s,
                        last_modified = %(last_modified)s,
                        direction = %(direction)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s AND license_number = %(license_number)s AND direction = %(direction)s
                """, data)
                updated += 1
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO metrc_transfers (
                        id, manifest_number, license_number,
                        shipper_facility_name, shipper_facility_license_number,
                        transporter_facility_name, transporter_facility_license_number,
                        destination_facility_name, destination_facility_license_number,
                        created_date, transfer_type, shipment_type,
                        est_departure_datetime, est_arrival_datetime,
                        actual_departure_datetime, actual_arrival_datetime,
                        package_count, delivery_count, received_delivery_count,
                        last_modified, direction, data, synced_at
                    ) VALUES (
                        %(id)s, %(manifest_number)s, %(license_number)s,
                        %(shipper_facility_name)s, %(shipper_facility_license_number)s,
                        %(transporter_facility_name)s, %(transporter_facility_license_number)s,
                        %(destination_facility_name)s, %(destination_facility_license_number)s,
                        %(created_date)s, %(transfer_type)s, %(shipment_type)s,
                        %(est_departure_datetime)s, %(est_arrival_datetime)s,
                        %(actual_departure_datetime)s, %(actual_arrival_datetime)s,
                        %(package_count)s, %(delivery_count)s, %(received_delivery_count)s,
                        %(last_modified)s, %(direction)s, %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        return (inserted, updated)


def run_daily_sync():
    """Run daily incremental sync for both cultivation and processing licenses."""
    print("=" * 70)
    print("METRC DAILY INCREMENTAL SYNC")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    
    syncer = MetrcSupabaseSync()
    
    try:
        # Test Metrc connection
        print("Testing Metrc API connection...")
        if not syncer.metrc_client.test_connection():
            raise Exception("Failed to connect to Metrc API")
        print("✓ Metrc API connected")
        print()
        
        # Test Supabase connection
        print("Testing Supabase connection...")
        syncer.connect_supabase()
        print("✓ Supabase connected")
        print()
        
        # Sync cultivation license (MC281599)
        print(f"CULTIVATION LICENSE: {CULTIVATION_LICENSE}")
        print("-" * 70)
        syncer.sync_harvests_incremental(CULTIVATION_LICENSE, hours=48)
        syncer.sync_packages_incremental(CULTIVATION_LICENSE, hours=48)
        syncer.sync_transfers_incremental(CULTIVATION_LICENSE, days=7)
        syncer.sync_plants(CULTIVATION_LICENSE)
        print()
        
        # Sync processing license (MP281433)  
        print(f"PROCESSING LICENSE: {PROCESSING_LICENSE}")
        print("-" * 70)
        syncer.sync_packages_incremental(PROCESSING_LICENSE, hours=48)
        syncer.sync_transfers_incremental(PROCESSING_LICENSE, days=7)
        syncer.sync_plants(PROCESSING_LICENSE)  # Will skip if no cultivation access
        print()
        
        print("=" * 70)
        print("✓ DAILY SYNC COMPLETED SUCCESSFULLY")
        print("=" * 70)
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"✗ SYNC FAILED: {e}")
        print("=" * 70)
        raise
        
    finally:
        syncer.close()


if __name__ == "__main__":
    run_daily_sync()
