"""
Metrc Reference Data Sync to Supabase

Populates reference/fact tables that change infrequently:
- Facilities
- Strains
- Locations (rooms)
- Items (product catalog)

Run this:
- Once initially to populate
- Weekly to keep reference data fresh
"""

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
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


class MetrcReferenceDataSync:
    """Handles syncing Metrc reference data to Supabase."""
    
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
    
    def sync_facilities(self):
        """Sync all facilities."""
        print("Syncing facilities...")
        
        facilities = self.metrc_client.get_facilities()
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for facility in facilities:
            # Check if exists
            cursor.execute("SELECT id FROM metrc_facilities WHERE id = %s", (facility['FacilityId'],))
            exists = cursor.fetchone() is not None
            
            data = {
                'id': facility['FacilityId'],
                'license_number': facility.get('License', {}).get('Number'),
                'license_type': facility.get('License', {}).get('LicenseType'),
                'display_name': facility.get('DisplayName'),
                'facility_name': facility.get('Name'),
                'alias': facility.get('Alias'),
                'credentialing_authority': facility.get('License', {}).get('LicensingAuthorityName'),
                'data': json.dumps(facility),
                'synced_at': datetime.now()
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_facilities SET
                        license_number = %(license_number)s,
                        license_type = %(license_type)s,
                        display_name = %(display_name)s,
                        facility_name = %(facility_name)s,
                        alias = %(alias)s,
                        credentialing_authority = %(credentialing_authority)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s
                """, data)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO metrc_facilities (
                        id, license_number, license_type, display_name,
                        facility_name, alias, credentialing_authority,
                        data, synced_at
                    ) VALUES (
                        %(id)s, %(license_number)s, %(license_type)s, %(display_name)s,
                        %(facility_name)s, %(alias)s, %(credentialing_authority)s,
                        %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        print(f"  ✓ Facilities: {len(facilities)} total ({inserted} new, {updated} updated)")
    
    def sync_strains(self, license_number: str):
        """Sync strains for a license."""
        print(f"Syncing strains for {license_number}...")
        
        response = self.cultivation.get_strains(license_number=license_number)
        strains = response.get('Data', []) if isinstance(response, dict) else response
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for strain in strains:
            cursor.execute("SELECT id FROM metrc_strains WHERE id = %s", (strain['Id'],))
            exists = cursor.fetchone() is not None
            
            data = {
                'id': strain['Id'],
                'strain_name': strain['Name'],
                'license_number': license_number,
                'testing_status': strain.get('TestingStatus'),
                'thc_level': strain.get('ThcLevel'),
                'cbd_level': strain.get('CbdLevel'),
                'indica_percentage': strain.get('IndicaPercentage'),
                'sativa_percentage': strain.get('SativaPercentage'),
                'is_used': strain.get('IsUsed'),
                'data': json.dumps(strain),
                'synced_at': datetime.now()
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_strains SET
                        strain_name = %(strain_name)s,
                        license_number = %(license_number)s,
                        testing_status = %(testing_status)s,
                        thc_level = %(thc_level)s,
                        cbd_level = %(cbd_level)s,
                        indica_percentage = %(indica_percentage)s,
                        sativa_percentage = %(sativa_percentage)s,
                        is_used = %(is_used)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s
                """, data)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO metrc_strains (
                        id, strain_name, license_number, testing_status,
                        thc_level, cbd_level, indica_percentage, sativa_percentage,
                        is_used, data, synced_at
                    ) VALUES (
                        %(id)s, %(strain_name)s, %(license_number)s, %(testing_status)s,
                        %(thc_level)s, %(cbd_level)s, %(indica_percentage)s, %(sativa_percentage)s,
                        %(is_used)s, %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        print(f"  ✓ Strains: {len(strains)} total ({inserted} new, {updated} updated)")
    
    def sync_locations(self, license_number: str):
        """Sync locations for a license."""
        print(f"Syncing locations for {license_number}...")
        
        response = self.processing.get_locations(license_number=license_number)
        locations = response.get('Data', []) if isinstance(response, dict) else response
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for location in locations:
            cursor.execute("SELECT id FROM metrc_locations WHERE id = %s", (location['Id'],))
            exists = cursor.fetchone() is not None
            
            data = {
                'id': location['Id'],
                'location_name': location['Name'],
                'license_number': license_number,
                'location_type_name': location.get('LocationTypeName'),
                'for_plant_batches': location.get('ForPlantBatches', False),
                'for_plants': location.get('ForPlants', False),
                'for_harvests': location.get('ForHarvests', False),
                'for_packages': location.get('ForPackages', False),
                'data': json.dumps(location),
                'synced_at': datetime.now()
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_locations SET
                        location_name = %(location_name)s,
                        license_number = %(license_number)s,
                        location_type_name = %(location_type_name)s,
                        for_plant_batches = %(for_plant_batches)s,
                        for_plants = %(for_plants)s,
                        for_harvests = %(for_harvests)s,
                        for_packages = %(for_packages)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s
                """, data)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO metrc_locations (
                        id, location_name, license_number, location_type_name,
                        for_plant_batches, for_plants, for_harvests, for_packages,
                        data, synced_at
                    ) VALUES (
                        %(id)s, %(location_name)s, %(license_number)s, %(location_type_name)s,
                        %(for_plant_batches)s, %(for_plants)s, %(for_harvests)s, %(for_packages)s,
                        %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        print(f"  ✓ Locations: {len(locations)} total ({inserted} new, {updated} updated)")
    
    def sync_items(self, license_number: str):
        """Sync items for a license."""
        print(f"Syncing items for {license_number}...")
        
        response = self.processing.get_items(license_number=license_number)
        items = response.get('Data', []) if isinstance(response, dict) else response
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for item in items:
            cursor.execute("SELECT id FROM metrc_items WHERE id = %s", (item['Id'],))
            exists = cursor.fetchone() is not None
            
            data = {
                'id': item['Id'],
                'item_name': item['Name'],
                'license_number': license_number,
                'product_category_name': item.get('ProductCategoryName'),
                'product_category_type': item.get('ProductCategoryType'),
                'quantity_type': item.get('QuantityType'),
                'default_lab_testing_state': item.get('DefaultLabTestingState'),
                'unit_of_measure': item.get('UnitOfMeasureName'),
                'approval_status': item.get('ApprovalStatus'),
                'strain_id': item.get('StrainId'),
                'strain_name': item.get('StrainName'),
                'data': json.dumps(item),
                'synced_at': datetime.now()
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_items SET
                        item_name = %(item_name)s,
                        license_number = %(license_number)s,
                        product_category_name = %(product_category_name)s,
                        product_category_type = %(product_category_type)s,
                        quantity_type = %(quantity_type)s,
                        default_lab_testing_state = %(default_lab_testing_state)s,
                        unit_of_measure = %(unit_of_measure)s,
                        approval_status = %(approval_status)s,
                        strain_id = %(strain_id)s,
                        strain_name = %(strain_name)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE id = %(id)s
                """, data)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO metrc_items (
                        id, item_name, license_number, product_category_name,
                        product_category_type, quantity_type, default_lab_testing_state,
                        unit_of_measure, approval_status, strain_id, strain_name,
                        data, synced_at
                    ) VALUES (
                        %(id)s, %(item_name)s, %(license_number)s, %(product_category_name)s,
                        %(product_category_type)s, %(quantity_type)s, %(default_lab_testing_state)s,
                        %(unit_of_measure)s, %(approval_status)s, %(strain_id)s, %(strain_name)s,
                        %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        print(f"  ✓ Items: {len(items)} total ({inserted} new, {updated} updated)")


def run_reference_data_sync():
    """Run reference data sync for all licenses."""
    print("=" * 70)
    print("METRC REFERENCE DATA SYNC")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    
    syncer = MetrcReferenceDataSync()
    
    try:
        # Test connections
        print("Testing Metrc API connection...")
        if not syncer.metrc_client.test_connection():
            raise Exception("Failed to connect to Metrc API")
        print("✓ Metrc API connected")
        print()
        
        print("Testing Supabase connection...")
        syncer.connect_supabase()
        print("✓ Supabase connected")
        print()
        
        # Sync facilities (all licenses)
        print("FACILITIES (All Licenses)")
        print("-" * 70)
        syncer.sync_facilities()
        print()
        
        # Sync cultivation license reference data
        print(f"CULTIVATION LICENSE: {CULTIVATION_LICENSE}")
        print("-" * 70)
        syncer.sync_strains(CULTIVATION_LICENSE)
        syncer.sync_locations(CULTIVATION_LICENSE)
        syncer.sync_items(CULTIVATION_LICENSE)
        print()
        
        # Sync processing license reference data
        print(f"PROCESSING LICENSE: {PROCESSING_LICENSE}")
        print("-" * 70)
        syncer.sync_strains(PROCESSING_LICENSE)
        syncer.sync_locations(PROCESSING_LICENSE)
        syncer.sync_items(PROCESSING_LICENSE)
        print()
        
        print("=" * 70)
        print("✓ REFERENCE DATA SYNC COMPLETED")
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
    run_reference_data_sync()
