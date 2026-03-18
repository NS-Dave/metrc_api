#!/usr/bin/env python3
"""
Ad-hoc Package Sync Tool

Syncs specific packages or missing packages from Metrc to Supabase.
Idempotent - safe to run multiple times.

Usage:
    # Sync specific package labels
    python sync_missing_packages.py --labels 1A40A030000C289000031650 1A40A030000C289000031651
    
    # Sync all active packages (full refresh)
    python sync_missing_packages.py --all-active
    
    # Sync packages from last N days
    python sync_missing_packages.py --days 7
    
    # Check if packages exist in Supabase
    python sync_missing_packages.py --check 1A40A030000C289000031650
"""

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta
import json
import argparse
from typing import List, Dict, Optional

from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from processing import ProcessingClient
from supabase_config import get_connection_string
from package_history import capture_history_before_update, create_initial_history_entry


class PackageSyncTool:
    """Tool for syncing missing or specific packages."""
    
    def __init__(self, license_number: str = 'MC281599'):
        config = MetrcConfig.from_env()
        self.metrc_client = MetrcClient(config)
        self.cultivation = CultivationClient(self.metrc_client)
        self.processing = ProcessingClient(self.metrc_client)
        self.license_number = license_number
        self.conn = psycopg2.connect(get_connection_string())
    
    def check_package_in_supabase(self, label: str) -> Optional[Dict]:
        """Check if package exists in Supabase."""
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        cursor.execute("""
            SELECT id, label, product_name, quantity, unit_of_measure,
                   packaged_date, finished_date, archived_date, last_modified
            FROM metrc_packages
            WHERE label = %s AND license_number = %s
        """, (label, self.license_number))
        
        result = cursor.fetchone()
        cursor.close()
        return dict(result) if result else None
    
    def get_package_from_metrc(self, label: str) -> Optional[Dict]:
        """Get package details from Metrc API."""
        try:
            endpoint = f'packages/v2/{label}'
            result = self.metrc_client.get(endpoint, license_number=self.license_number)
            return result
        except Exception as e:
            print(f"  ✗ Error fetching {label} from Metrc: {e}")
            return None
    
    def upsert_package(self, package: Dict) -> str:
        """
        Upsert single package to Supabase.
        
        Returns: 'inserted', 'updated', or 'error'
        """
        cursor = self.conn.cursor()
        
        try:
            # Check if exists
            cursor.execute("SELECT id FROM metrc_packages WHERE id = %s", (package['Id'],))
            exists = cursor.fetchone() is not None
            
            # Prepare data - comprehensive field mapping matching metrc_daily_sync.py
            data = {
                'id': package['Id'],
                'label': package['Label'],
                'package_type': package.get('PackageType'),
                'license_number': self.license_number,
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
                'synced_at': datetime.now()
            }
            
            if exists:
                # Capture history before updating
                capture_history_before_update(cursor, data['label'], data, data['synced_at'])
                
                # Update - comprehensive field update
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
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s
                """, data)
                result = 'updated'
            else:
                # Insert - comprehensive field insert
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
                        data, synced_at
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
                        %(data)s, %(synced_at)s
                    )
                """, data)
                
                # Create initial history entry for new package
                create_initial_history_entry(cursor, data, data['synced_at'])
                
                result = 'inserted'
            
            self.conn.commit()
            return result
            
        except Exception as e:
            self.conn.rollback()
            print(f"  ✗ Error upserting package: {e}")
            return 'error'
        finally:
            cursor.close()
    
    def sync_packages_by_labels(self, labels: List[str]):
        """Sync specific package labels from Metrc to Supabase."""
        print(f"\nSyncing {len(labels)} packages for license {self.license_number}")
        print("=" * 80)
        
        inserted = 0
        updated = 0
        errors = 0
        
        for label in labels:
            print(f"\n{label}:")
            
            # Check Supabase first
            existing = self.check_package_in_supabase(label)
            if existing:
                print(f"  Found in Supabase: ID={existing['id']}, Modified={existing['last_modified']}")
            else:
                print(f"  Not found in Supabase")
            
            # Get from Metrc
            print(f"  Fetching from Metrc API...")
            package = self.get_package_from_metrc(label)
            
            if not package:
                errors += 1
                continue
            
            print(f"  ✓ Found in Metrc: {package.get('ProductName')}")
            print(f"    ID: {package['Id']}")
            print(f"    Quantity: {package.get('Quantity')} {package.get('UnitOfMeasure')}")
            print(f"    Packaged: {package.get('PackagedDate')}")
            print(f"    Last Modified: {package.get('LastModified')}")
            
            # Upsert to Supabase
            result = self.upsert_package(package)
            
            if result == 'inserted':
                inserted += 1
                print(f"  ✓ Inserted into Supabase")
            elif result == 'updated':
                updated += 1
                print(f"  ✓ Updated in Supabase")
            else:
                errors += 1
        
        print("\n" + "=" * 80)
        print(f"RESULTS: {inserted} inserted, {updated} updated, {errors} errors")
        print("=" * 80)
    
    def sync_all_active_packages(self):
        """
        Sync all active packages from Metrc.
        
        NOTE: The /packages/v2/active endpoint only returns recently modified packages.
        To backfill historical active packages, we query inactive packages over a wide
        date range, then filter for packages that aren't actually finished/archived.
        """
        print(f"\nBackfilling ALL active packages for license {self.license_number}")
        print("=" * 80)
        
        try:
            # Get recently active packages (last 48-72 hours)
            print("Fetching recently active packages...")
            recent_active = self.cultivation.client.get(
                'packages/v2/active',
                params={},
                license_number=self.license_number,
                paginate=True
            )
            print(f"  Found {len(recent_active)} recently active packages")
            
            # Get historical packages using inactive endpoint with wide date range
            # These include BOTH truly inactive AND older active packages
            print("\nFetching historical packages (2024-01-01 to now)...")
            start_date = '2024-01-01'
            end_date = datetime.now().strftime('%Y-%m-%d')
            
            historical = self.cultivation.client.get(
                'packages/v2/inactive',
                params={
                    'lastModifiedStart': start_date,
                    'lastModifiedEnd': end_date
                },
                license_number=self.license_number,
                paginate=True
            )
            print(f"  Found {len(historical)} historical packages")
            
            # Merge both datasets (deduplicate by ID)
            all_packages = {p['Id']: p for p in recent_active}
            all_packages.update({p['Id']: p for p in historical})
            
            packages_list = list(all_packages.values())
            print(f"\nTotal unique packages: {len(packages_list)}")
            
            # Now sync all packages
            # The database will filter to only active (finished_date IS NULL) during reconciliation
            print("\nSyncing to Supabase...")
            inserted = 0
            updated = 0
            errors = 0
            
            for i, package in enumerate(packages_list, 1):
                if i % 250 == 0:
                    print(f"  Progress: {i}/{len(packages_list)} packages...")
                
                result = self.upsert_package(package)
                if result == 'inserted':
                    inserted += 1
                elif result == 'updated':
                    updated += 1
                else:
                    errors += 1
            
            print("\n" + "=" * 80)
            print(f"RESULTS: {inserted} inserted, {updated} updated, {errors} errors")
            print("=" * 80)
            
        except Exception as e:
            print(f"Error fetching packages: {e}")
            import traceback
            traceback.print_exc()
    
    def sync_packages_by_date_range(self, days: int):
        """Sync packages modified in last N days."""
        print(f"\nSyncing packages from last {days} days for license {self.license_number}")
        print("=" * 80)
        
        try:
            # Get packages using last_modified endpoint
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # For cultivation packages, we need to query both active and inactive
            active = self.cultivation.get_packages(
                license_number=self.license_number,
                active_only=True
            )
            
            # Filter by last_modified
            recent = [
                p for p in active
                if p.get('LastModified') and 
                datetime.fromisoformat(p['LastModified'].replace('Z', '+00:00')) >= start_date
            ]
            
            print(f"Found {len(recent)} packages modified since {start_date.strftime('%Y-%m-%d')}")
            
            labels = [p['Label'] for p in recent]
            self.sync_packages_by_labels(labels)
            
        except Exception as e:
            print(f"Error fetching packages by date: {e}")
    
    def close(self):
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Sync missing packages from Metrc to Supabase')
    parser.add_argument('--labels', nargs='+', help='Specific package labels to sync')
    parser.add_argument('--check', type=str, help='Check if label exists in Supabase')
    parser.add_argument('--all-active', action='store_true', help='Sync all active packages')
    parser.add_argument('--days', type=int, help='Sync packages from last N days')
    parser.add_argument('--license', type=str, default='MC281599', help='License number (default: MC281599)')
    
    args = parser.parse_args()
    
    tool = PackageSyncTool(license_number=args.license)
    
    try:
        if args.check:
            # Check mode
            result = tool.check_package_in_supabase(args.check)
            if result:
                print(f"\n✓ Package {args.check} found in Supabase:")
                for key, value in result.items():
                    print(f"  {key}: {value}")
            else:
                print(f"\n✗ Package {args.check} NOT found in Supabase")
                
                # Try to fetch from Metrc
                print(f"\nChecking Metrc API...")
                package = tool.get_package_from_metrc(args.check)
                if package:
                    print(f"✓ Found in Metrc: {package.get('ProductName')}")
                    print(f"  Last Modified: {package.get('LastModified')}")
                    print(f"\nRun with --labels {args.check} to sync")
                else:
                    print(f"✗ Not found in Metrc either")
        
        elif args.labels:
            # Sync specific labels
            tool.sync_packages_by_labels(args.labels)
        
        elif args.all_active:
            # Sync all active
            tool.sync_all_active_packages()
        
        elif args.days:
            # Sync by date range
            tool.sync_packages_by_date_range(args.days)
        
        else:
            parser.print_help()
    
    finally:
        tool.close()


if __name__ == '__main__':
    main()
