#!/usr/bin/env python3
"""
Enrich historical transfer packages with full API data.

Fetches complete package details from Metrc API for existing packages
that only have minimal data (PackageId, PackageLabel, pricing).
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from typing import Dict, List, Optional
import time
from dotenv import load_dotenv

from supabase_config import get_connection_string
from client import MetrcClient
from config import MetrcConfig
from processing import ProcessingClient

load_dotenv()

PROCESSING_LICENSE = "MP281433"

class HistoricalPackageEnricher:
    def __init__(self):
        self.conn = None
        self.connect_supabase()
        
        # Initialize Metrc client
        self.config = MetrcConfig.from_env()
        self.client = MetrcClient(self.config)
        self.processing = ProcessingClient(self.client)
    
    def connect_supabase(self):
        """Connect to Supabase database."""
        if self.conn and not self.conn.closed:
            return
            
        self.conn = psycopg2.connect(get_connection_string())
        print("✓ Connected to Supabase")
    
    def get_transfers_needing_enrichment(self) -> List[Dict]:
        """Get transfers that have packages but need full details."""
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        
        # Find transfers with packages that have NULL product_name (indicator of minimal data)
        cursor.execute("""
            SELECT DISTINCT
                t.id as transfer_id,
                t.manifest_number,
                t.data
            FROM metrc_transfers t
            INNER JOIN metrc_transfer_packages tp ON tp.transfer_id = t.id
            WHERE tp.product_name IS NULL
            ORDER BY t.id
        """)
        
        transfers = cursor.fetchall()
        print(f"Found {len(transfers)} transfers with packages needing enrichment")
        return transfers
    
    def extract_delivery_id(self, transfer_data: Dict) -> Optional[int]:
        """Extract delivery ID from transfer JSON."""
        # Check top-level DeliveryId
        delivery_id = transfer_data.get('DeliveryId')
        if delivery_id:
            return delivery_id
        
        # Check if Deliveries array has an Id
        deliveries = transfer_data.get('Deliveries', [])
        if deliveries and isinstance(deliveries, list):
            for delivery in deliveries:
                if isinstance(delivery, dict) and delivery.get('Id'):
                    return delivery['Id']
        
        # Fall back to transfer Id
        return transfer_data.get('Id')
    
    def fetch_full_packages(self, delivery_id: int, license_number: str) -> Optional[List[Dict]]:
        """Fetch full package details from Metrc API."""
        try:
            detail = self.processing.get_transfer_delivery(delivery_id, license_number=license_number)
            
            packages = None
            if isinstance(detail, dict):
                packages = detail.get('Data', [])
            elif isinstance(detail, list):
                packages = detail
            
            return packages
        except Exception as e:
            print(f"    API error: {e}")
            return None
    
    def update_package_with_full_data(self, package_id: int, package_label: str, 
                                     transfer_id: int, full_data: Dict) -> bool:
        """Update package record with full API data."""
        cursor = self.conn.cursor()
        
        try:
            # Extract all fields from full package data - using ACTUAL column names
            update_data = {
                'package_type': full_data.get('PackageType'),
                'product_name': full_data.get('ProductName'),
                'product_category_name': full_data.get('ProductCategoryName'),
                'item_id': full_data.get('ItemId'),
                'item_name': full_data.get('ItemName'),
                'item_category_name': full_data.get('ItemCategoryName'),
                'item_strain_name': full_data.get('ItemStrainName'),
                'item_unit_cbd_percent': full_data.get('ItemUnitCbdPercent'),
                'item_unit_cbd_content': full_data.get('ItemUnitCbdContent'),
                'item_unit_cbd_content_uom': full_data.get('ItemUnitCbdContentUnitOfMeasureName'),
                'item_unit_thc_percent': full_data.get('ItemUnitThcPercent'),
                'item_unit_thc_content': full_data.get('ItemUnitThcContent'),
                'item_unit_thc_content_uom': full_data.get('ItemUnitThcContentUnitOfMeasureName'),
                'source_harvest_names': full_data.get('SourceHarvestNames'),
                'source_package_labels': full_data.get('SourcePackageLabels'),
                'quantity_shipped': full_data.get('ShippedQuantity'),
                'quantity_received': full_data.get('ReceivedQuantity'),
                'unit_of_measure_name': full_data.get('ShippedUnitOfMeasureName'),
                'unit_of_measure_abbreviation': full_data.get('ShippedUnitOfMeasureAbbreviation'),
                'gross_weight': full_data.get('GrossWeight'),
                'gross_unit_of_weight_name': full_data.get('GrossUnitOfWeightName'),
                'gross_unit_of_weight_abbreviation': full_data.get('GrossUnitOfWeightAbbreviation'),
                'packaged_date': full_data.get('PackagedDate'),
                'received_date_time': full_data.get('ReceivedDateTime'),
                'is_testing_sample': full_data.get('IsTestingSample'),
                'is_process_validation_test_sample': full_data.get('IsProcessValidationTestSample'),
                'is_production_batch': full_data.get('IsProductionBatch'),
                'production_batch_number': full_data.get('ProductionBatchNumber'),
                'is_trade_sample': full_data.get('IsTradeSample'),
                'is_on_hold': full_data.get('IsOnHold'),
                'archived_date': full_data.get('ArchivedDate'),
                'finished_date': full_data.get('FinishedDate'),
                'last_modified': full_data.get('LastModified'),
                'data': json.dumps(full_data),
                'transfer_id': transfer_id,
                'package_label': package_label
            }
            
            cursor.execute("""
                UPDATE metrc_transfer_packages
                SET 
                    package_type = %(package_type)s,
                    product_name = %(product_name)s,
                    product_category_name = %(product_category_name)s,
                    item_id = %(item_id)s,
                    item_name = %(item_name)s,
                    item_category_name = %(item_category_name)s,
                    item_strain_name = %(item_strain_name)s,
                    item_unit_cbd_percent = %(item_unit_cbd_percent)s,
                    item_unit_cbd_content = %(item_unit_cbd_content)s,
                    item_unit_cbd_content_uom = %(item_unit_cbd_content_uom)s,
                    item_unit_thc_percent = %(item_unit_thc_percent)s,
                    item_unit_thc_content = %(item_unit_thc_content)s,
                    item_unit_thc_content_uom = %(item_unit_thc_content_uom)s,
                    source_harvest_names = %(source_harvest_names)s,
                    source_package_labels = %(source_package_labels)s,
                    quantity_shipped = %(quantity_shipped)s,
                    quantity_received = %(quantity_received)s,
                    unit_of_measure_name = %(unit_of_measure_name)s,
                    unit_of_measure_abbreviation = %(unit_of_measure_abbreviation)s,
                    gross_weight = %(gross_weight)s,
                    gross_unit_of_weight_name = %(gross_unit_of_weight_name)s,
                    gross_unit_of_weight_abbreviation = %(gross_unit_of_weight_abbreviation)s,
                    packaged_date = %(packaged_date)s,
                    received_date_time = %(received_date_time)s,
                    is_testing_sample = %(is_testing_sample)s,
                    is_process_validation_test_sample = %(is_process_validation_test_sample)s,
                    is_production_batch = %(is_production_batch)s,
                    production_batch_number = %(production_batch_number)s,
                    is_trade_sample = %(is_trade_sample)s,
                    is_on_hold = %(is_on_hold)s,
                    archived_date = %(archived_date)s,
                    finished_date = %(finished_date)s,
                    last_modified = %(last_modified)s,
                    data = %(data)s,
                    synced_at = CURRENT_TIMESTAMP
                WHERE transfer_id = %(transfer_id)s 
                AND package_label = %(package_label)s
            """, update_data)
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"    Update error: {e}")
            self.conn.rollback()
            return False
    
    def enrich_all(self):
        """Main enrichment process."""
        print("\n=== Historical Package Enrichment ===\n")
        
        transfers = self.get_transfers_needing_enrichment()
        
        if not transfers:
            print("\nNo transfers need enrichment!")
            return
        
        total_packages_updated = 0
        total_transfers_enriched = 0
        failed_transfers = 0
        api_calls = 0
        
        for i, transfer in enumerate(transfers, 1):
            transfer_id = transfer['transfer_id']
            manifest = transfer['manifest_number']
            
            try:
                # Parse JSON data
                transfer_data = transfer['data']
                if isinstance(transfer_data, str):
                    transfer_data = json.loads(transfer_data)
                
                # Get delivery ID
                delivery_id = self.extract_delivery_id(transfer_data)
                if not delivery_id:
                    print(f"  {i}/{len(transfers)} ✗ {manifest}: No delivery ID")
                    failed_transfers += 1
                    continue
                
                # Fetch full package data from API
                print(f"  {i}/{len(transfers)} Fetching {manifest} (delivery {delivery_id})...", end=" ")
                full_packages = self.fetch_full_packages(delivery_id, PROCESSING_LICENSE)
                api_calls += 1
                
                if not full_packages:
                    print("✗ No data from API")
                    failed_transfers += 1
                    time.sleep(0.5)  # Rate limiting
                    continue
                
                # Update each package
                packages_updated = 0
                for pkg in full_packages:
                    pkg_label = pkg.get('PackageLabel')
                    pkg_id = pkg.get('PackageId')
                    
                    if pkg_label and self.update_package_with_full_data(
                        pkg_id, pkg_label, transfer_id, pkg
                    ):
                        packages_updated += 1
                
                print(f"✓ {packages_updated} packages enriched")
                total_packages_updated += packages_updated
                total_transfers_enriched += 1
                
                # Rate limiting - 10 requests per second max
                if api_calls % 10 == 0:
                    time.sleep(1)
                
            except Exception as e:
                print(f"  {i}/{len(transfers)} ✗ {manifest}: {e}")
                failed_transfers += 1
        
        print(f"\n=== Enrichment Complete ===")
        print(f"Transfers enriched: {total_transfers_enriched}")
        print(f"Packages updated: {total_packages_updated}")
        print(f"Failed: {failed_transfers}")
        print(f"API calls made: {api_calls}")
        print(f"\nVerify with:")
        print(f"  SELECT COUNT(*) FROM metrc_transfer_packages WHERE product_name IS NOT NULL;")
        print(f"  SELECT product_name, item_name, quantity_shipped FROM metrc_transfer_packages LIMIT 10;")

def main():
    try:
        enricher = HistoricalPackageEnricher()
        enricher.enrich_all()
    except Exception as e:
        print(f"\n✗ Enrichment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
