#!/usr/bin/env python3
"""
Sync plants and plant batches from Metrc API to Supabase.

This script fetches active and inactive plants and plant batches,
storing them in metrc_plants and metrc_plants_batches tables.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import DictCursor

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from supabase_config import get_connection_string


class PlantsSync:
    """Sync plants and plant batches from Metrc to Supabase."""
    
    def __init__(self):
        config = MetrcConfig.from_env()
        self.metrc_client = MetrcClient(config)
        self.cultivation = CultivationClient(self.metrc_client)
        self.conn = None
        
        # Supabase connection
        self.conn_string = get_connection_string()
    
    def connect_supabase(self):
        """Connect to Supabase."""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(self.conn_string)
    
    def sync_plants(self, license_number: str) -> tuple:
        """
        Sync plants for a license.
        
        Returns:
            (active_count, inactive_count, inserted, updated)
        """
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        print(f"\nSyncing plants for {license_number}...")
        
        # Fetch plants from all phases
        print("  Fetching vegetative plants...")
        vegetative_plants = []
        try:
            result = self.cultivation.get_plants(license_number=license_number, phase='vegetative')
            # Handle response format
            if isinstance(result, dict):
                vegetative_plants = result.get('Data', [])
            elif isinstance(result, list):
                vegetative_plants = result
            print(f"    Found {len(vegetative_plants)} vegetative plants")
        except Exception as e:
            print(f"    ERROR fetching vegetative plants: {e}")
        
        print("  Fetching flowering plants...")
        flowering_plants = []
        try:
            result = self.cultivation.get_plants(license_number=license_number, phase='flowering')
            # Handle response format
            if isinstance(result, dict):
                flowering_plants = result.get('Data', [])
            elif isinstance(result, list):
                flowering_plants = result
            print(f"    Found {len(flowering_plants)} flowering plants")
        except Exception as e:
            print(f"    ERROR fetching flowering plants: {e}")
        
        print("  Fetching on-hold plants...")
        onhold_plants = []
        try:
            result = self.cultivation.get_plants(license_number=license_number, phase='onhold')
            # Handle response format
            if isinstance(result, dict):
                onhold_plants = result.get('Data', [])
            elif isinstance(result, list):
                onhold_plants = result
            print(f"    Found {len(onhold_plants)} on-hold plants")
        except Exception as e:
            print(f"    ERROR fetching on-hold plants: {e}")
        
        print("  Fetching inactive plants...")
        inactive_plants = []
        try:
            result = self.cultivation.get_plants(license_number=license_number, phase='inactive')
            # Handle response format
            if isinstance(result, dict):
                inactive_plants = result.get('Data', [])
            elif isinstance(result, list):
                inactive_plants = result
            print(f"    Found {len(inactive_plants)} inactive plants")
        except Exception as e:
            print(f"    ERROR fetching inactive plants: {e}")
        
        # Process all plants
        all_plants = vegetative_plants + flowering_plants + onhold_plants + inactive_plants
        active_count = len(vegetative_plants) + len(flowering_plants) + len(onhold_plants)
        inactive_count = len(inactive_plants)
        
        for plant in all_plants:
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
                'growth_phase': plant.get('GrowthPhase'),  # Changed from GrowthPhaseName
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
        
        print(f"  OK Plants: {inserted} inserted, {updated} updated")
        
        return (active_count, inactive_count, inserted, updated)
    
    def sync_plant_batches(self, license_number: str) -> tuple:
        """
        Sync plant batches for a license.
        
        Returns:
            (active_count, inactive_count, inserted, updated)
        """
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        print(f"\nSyncing plant batches for {license_number}...")
        
        # Fetch active plant batches
        print("  Fetching active plant batches...")
        active_batches = []
        try:
            result = self.cultivation.get_plant_batches(license_number=license_number, status='active')
            # Handle response format
            if isinstance(result, dict):
                active_batches = result.get('Data', [])
            elif isinstance(result, list):
                active_batches = result
            print(f"    Found {len(active_batches)} active plant batches")
        except Exception as e:
            print(f"    ERROR fetching active batches: {e}")
        
        # Fetch inactive plant batches
        print("  Fetching inactive plant batches...")
        inactive_batches = []
        try:
            result = self.cultivation.get_plant_batches(license_number=license_number, status='inactive')
            # Handle response format
            if isinstance(result, dict):
                inactive_batches = result.get('Data', [])
            elif isinstance(result, list):
                inactive_batches = result
            print(f"    Found {len(inactive_batches)} inactive plant batches")
        except Exception as e:
            print(f"    ERROR fetching inactive batches: {e}")
        
        # Process all batches
        all_batches = active_batches + inactive_batches
        
        for batch in all_batches:
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
        
        print(f"  OK Plant Batches: {inserted} inserted, {updated} updated")
        
        return (len(active_batches), len(inactive_batches), inserted, updated)


def main():
    """Run plants and plant batches sync."""
    licenses = ['MP281433', 'MC281599']
    
    print("=" * 80)
    print("PLANTS & PLANT BATCHES SYNC")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Licenses: {', '.join(licenses)}")
    print("=" * 80)
    
    sync = PlantsSync()
    
    total_plants_active = 0
    total_plants_inactive = 0
    total_batches_active = 0
    total_batches_inactive = 0
    
    for license_number in licenses:
        print(f"\n{'=' * 80}")
        print(f"License: {license_number}")
        print('=' * 80)
        
        # Sync plants
        try:
            active, inactive, ins, upd = sync.sync_plants(license_number)
            total_plants_active += active
            total_plants_inactive += inactive
        except Exception as e:
            print(f"ERROR syncing plants: {e}")
            import traceback
            traceback.print_exc()
        
        # Sync plant batches
        try:
            active, inactive, ins, upd = sync.sync_plant_batches(license_number)
            total_batches_active += active
            total_batches_inactive += inactive
        except Exception as e:
            print(f"ERROR syncing plant batches: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'=' * 80}")
    print("SYNC COMPLETE")
    print('=' * 80)
    print(f"Plants: {total_plants_active} active, {total_plants_inactive} inactive")
    print(f"Plant Batches: {total_batches_active} active, {total_batches_inactive} inactive")
    print('=' * 80)


if __name__ == '__main__':
    main()
