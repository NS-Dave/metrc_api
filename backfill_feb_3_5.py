"""
Backfill Metrc Data for February 3-5, 2026

This script backfills the missing data from when the automation was broken.
Syncs data for the specific date range when scheduled task was misconfigured.
"""

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import json
import os
import sys

from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from processing import ProcessingClient
from supabase_config import get_connection_string
from utils import DateUtils

# License configuration
CULTIVATION_LICENSE = os.getenv('METRC_LICENSE_CULTIVATION', 'MC281599')
PROCESSING_LICENSE = os.getenv('METRC_LICENSE_PROCESSING', 'MP281433')


class MetrcBackfill:
    """Handles backfilling Metrc data for specific date ranges."""
    
    def __init__(self, password=None):
        """Initialize backfill with Metrc and Supabase connections."""
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
    
    def upsert_harvests(self, harvests, license_number):
        """Upsert harvests to database."""
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for harvest in harvests:
            harvest_name = harvest.get('Name')
            harvest_id = harvest.get('Id')
            
            # Check if exists
            cursor.execute("""
                SELECT id FROM metrc_harvests 
                WHERE harvest_name = %s AND license_number = %s
            """, (harvest_name, license_number))
            
            existing = cursor.fetchone()
            exists = existing is not None
            
            # Prepare data matching the actual schema
            data = {
                'id': harvest_id,
                'harvest_name': harvest_name,
                'license_number': license_number,
                'harvest_type': harvest.get('HarvestType'),
                'source_strain_count': harvest.get('SourceStrainCount'),
                'source_strain_names': harvest.get('SourceStrainNames'),
                'drying_location_name': harvest.get('DryingLocationName'),
                'harvest_start_date': harvest.get('HarvestStartDate'),
                'harvest_date': harvest.get('HarvestDate'),
                'finished_date': harvest.get('FinishedDate'),
                'packaged_date': harvest.get('PackagedDate'),
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
                # Update
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
                # Insert
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
        return inserted, updated
    
    def upsert_packages(self, packages, license_number):
        """Upsert packages to database."""
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for package in packages:
            package_label = package.get('Label')
            package_id = package.get('Id')
            
            if not package_id or not package_label:
                continue
            
            # Check if exists
            cursor.execute("""
                SELECT id FROM metrc_packages 
                WHERE label = %s
            """, (package_label,))
            
            existing = cursor.fetchone()
            exists = existing is not None
            
            # Prepare data matching the actual schema
            data = {
                'id': package_id,
                'label': package_label,
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
                'data': json.dumps(package),
                'synced_at': datetime.now()
            }
            
            if exists:
                # Update
                cursor.execute("""
                    UPDATE metrc_packages SET
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
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE label = %(label)s
                """, data)
                updated += 1
            else:
                # Insert
                cursor.execute("""
                    INSERT INTO metrc_packages (
                        id, label, package_type, license_number,
                        product_name, product_category_name, item_name, item_id,
                        quantity, unit_of_measure, packaged_date,
                        initial_lab_testing_state, lab_testing_state, lab_testing_state_date,
                        is_production_batch, production_batch_number,
                        source_production_batch_numbers, source_package_labels, source_harvest_names,
                        is_trade_sample, is_testing_sample, is_process_validation_test_sample,
                        is_donation, is_on_hold,
                        archived_date, finished_date, location_name, note,
                        last_modified, data, synced_at
                    ) VALUES (
                        %(id)s, %(label)s, %(package_type)s, %(license_number)s,
                        %(product_name)s, %(product_category_name)s, %(item_name)s, %(item_id)s,
                        %(quantity)s, %(unit_of_measure)s, %(packaged_date)s,
                        %(initial_lab_testing_state)s, %(lab_testing_state)s, %(lab_testing_state_date)s,
                        %(is_production_batch)s, %(production_batch_number)s,
                        %(source_production_batch_numbers)s, %(source_package_labels)s, %(source_harvest_names)s,
                        %(is_trade_sample)s, %(is_testing_sample)s, %(is_process_validation_test_sample)s,
                        %(is_donation)s, %(is_on_hold)s,
                        %(archived_date)s, %(finished_date)s, %(location_name)s, %(note)s,
                        %(last_modified)s, %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        return inserted, updated
    
    def backfill_date_range(self, start_date, end_date):
        """Backfill data for a specific date range."""
        print("=" * 70)
        print(f"METRC DATA BACKFILL: {start_date.date()} to {end_date.date()}")
        print("=" * 70)
        print()
        
        # Convert dates to ISO format for API
        start_iso = DateUtils.to_iso(start_date)
        end_iso = DateUtils.to_iso(end_date)
        
        # Process Cultivation License
        print(f"CULTIVATION LICENSE: {CULTIVATION_LICENSE}")
        print("-" * 70)
        
        # Harvests
        print(f"Fetching harvests modified between {start_date.date()} and {end_date.date()}...")
        active_harvests = self.cultivation.get_harvests('active', None, None, CULTIVATION_LICENSE)
        inactive_harvests = self.cultivation.get_harvests(
            'inactive', start_iso, end_iso, CULTIVATION_LICENSE
        )
        all_harvests = active_harvests + inactive_harvests
        print(f"  Found {len(active_harvests)} active, {len(inactive_harvests)} inactive = {len(all_harvests)} total")
        
        if all_harvests:
            ins, upd = self.upsert_harvests(all_harvests, CULTIVATION_LICENSE)
            print(f"  [OK] Inserted {ins}, Updated {upd}")
        else:
            print(f"  [OK] No harvests to sync")
        
        # Packages
        print(f"Fetching packages modified between {start_date.date()} and {end_date.date()}...")
        active_pkgs = self.processing.get_packages('active', None, None, CULTIVATION_LICENSE)
        inactive_pkgs = self.processing.get_packages('inactive', start_iso, end_iso, CULTIVATION_LICENSE)
        all_packages = active_pkgs + inactive_pkgs
        print(f"  Found {len(active_pkgs)} active, {len(inactive_pkgs)} inactive = {len(all_packages)} total")
        
        if all_packages:
            ins, upd = self.upsert_packages(all_packages, CULTIVATION_LICENSE)
            print(f"  [OK] Inserted {ins}, Updated {upd}")
        else:
            print(f"  [OK] No packages to sync")
        
        print()
        
        # Process Processing License
        print(f"PROCESSING LICENSE: {PROCESSING_LICENSE}")
        print("-" * 70)
        
        # Packages
        print(f"Fetching packages modified between {start_date.date()} and {end_date.date()}...")
        active_pkgs = self.processing.get_packages('active', None, None, PROCESSING_LICENSE)
        inactive_pkgs = self.processing.get_packages('inactive', start_iso, end_iso, PROCESSING_LICENSE)
        all_packages = active_pkgs + inactive_pkgs
        print(f"  Found {len(active_pkgs)} active, {len(inactive_pkgs)} inactive = {len(all_packages)} total")
        
        if all_packages:
            ins, upd = self.upsert_packages(all_packages, PROCESSING_LICENSE)
            print(f"  [OK] Inserted {ins}, Updated {upd}")
        else:
            print(f"  [OK] No packages to sync")
        
        print()
        print("=" * 70)
        print("[SUCCESS] BACKFILL COMPLETED")
        print("=" * 70)


def main():
    """Main backfill execution."""
    print()
    print("=" * 70)
    print("METRC BACKFILL: February 3-5, 2026")
    print("=" * 70)
    print()
    print("This will backfill data that was missed when automation was broken.")
    print()
    
    # Define date ranges for each day
    dates = [
        (datetime(2026, 2, 3, 0, 0, 0), datetime(2026, 2, 3, 23, 59, 59)),
        (datetime(2026, 2, 4, 0, 0, 0), datetime(2026, 2, 4, 23, 59, 59)),
        (datetime(2026, 2, 5, 0, 0, 0), datetime(2026, 2, 5, 23, 59, 59)),
    ]
    
    try:
        backfiller = MetrcBackfill()
        
        for start_date, end_date in dates:
            print()
            backfiller.backfill_date_range(start_date, end_date)
            print()
        
        backfiller.close()
        
        print()
        print("=" * 70)
        print("ALL BACKFILLS COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print()
        print("Data for February 3-5, 2026 has been synced to Supabase.")
        print()
        
    except Exception as e:
        print()
        print("=" * 70)
        print("[ERROR] BACKFILL FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
