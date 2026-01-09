#!/usr/bin/env python3
"""
Backfill transfer enrichment for existing transfers in database.

This script:
1. Reads existing transfers that have Deliveries in their JSON data column
2. Extracts package and transporter details from the stored JSON
3. Populates metrc_transfer_packages and metrc_transfer_transporters tables
4. Updates received timestamps and counts in metrc_transfers

Run this AFTER schema_transfer_enrichment.sql has been applied.
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from typing import Dict, List, Optional

from supabase_config import get_connection_string

class TransferEnrichmentBackfill:
    def __init__(self):
        self.conn = None
        self.connect_supabase()
    
    def connect_supabase(self):
        """Connect to Supabase database."""
        if self.conn and not self.conn.closed:
            return
            
        self.conn = psycopg2.connect(get_connection_string())
        print("✓ Connected to Supabase")
    
    def get_transfers_to_enrich(self) -> List[Dict]:
        """Get all transfers that have Deliveries in JSON but not in packages table."""
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        
        # Find transfers with Deliveries in JSON but no packages extracted
        cursor.execute("""
            SELECT 
                t.id,
                t.manifest_number,
                t.data,
                t.received_date_time as current_received_date
            FROM metrc_transfers t
            WHERE t.data::text LIKE '%Deliveries%'
            AND NOT EXISTS (
                SELECT 1 FROM metrc_transfer_packages tp 
                WHERE tp.transfer_id = t.id
            )
            ORDER BY t.id
        """)
        
        transfers = cursor.fetchall()
        print(f"Found {len(transfers)} transfers with deliveries to enrich")
        return transfers
    
    def extract_packages_from_json(self, transfer_data: Dict) -> Optional[List[Dict]]:
        """Extract package data from transfer JSON."""
        try:
            deliveries = transfer_data.get('Deliveries', [])
            if not deliveries:
                return None
            
            # Usually one delivery per transfer
            for delivery in deliveries:
                packages = delivery.get('Packages', [])
                if packages:
                    return packages
            
            return None
        except Exception as e:
            print(f"  Error extracting packages: {e}")
            return None
    
    def extract_delivery_id(self, transfer_data: Dict) -> Optional[int]:
        """Extract delivery ID from JSON - returns transfer Id if no separate delivery ID."""
        # Check if DeliveryId exists at transfer level
        delivery_id = transfer_data.get('DeliveryId')
        if delivery_id:
            return delivery_id
        
        # Deliveries in JSON don't have separate IDs - use transfer ID
        return transfer_data.get('Id')
    
    def upsert_transfer_packages(self, transfer_id: int, packages: List[Dict]) -> int:
        """Store transfer package details with wholesale pricing."""
        if not packages:
            return 0
        
        cursor = self.conn.cursor()
        inserted = 0
        
        # Use transfer_id as delivery_id since deliveries in JSON don't have separate IDs
        delivery_id = transfer_id
        
        for pkg in packages:
            # Check if exists
            cursor.execute("""
                SELECT id FROM metrc_transfer_packages 
                WHERE transfer_id = %s AND package_label = %s
            """, (transfer_id, pkg.get('PackageLabel')))
            exists = cursor.fetchone() is not None
            
            if exists:
                continue
            
            # Build data dict with only fields that exist in the package
            data = {
                'transfer_id': transfer_id,
                'delivery_id': delivery_id,
                'package_id': pkg.get('PackageId'),
                'package_label': pkg.get('PackageLabel'),
                'wholesale_price': pkg.get('WholesalePrice'),
                'shipper_wholesale_price': pkg.get('ShipperWholesalePrice'),
                'receiver_wholesale_price': pkg.get('ReceiverWholesalePrice'),
                'data': json.dumps(pkg),
                'synced_at': datetime.now()
            }
            
            try:
                cursor.execute("""
                    INSERT INTO metrc_transfer_packages (
                        transfer_id, delivery_id, package_id, package_label,
                        wholesale_price, shipper_wholesale_price, receiver_wholesale_price,
                        data, synced_at
                    ) VALUES (
                        %(transfer_id)s, %(delivery_id)s, %(package_id)s, %(package_label)s,
                        %(wholesale_price)s, %(shipper_wholesale_price)s, %(receiver_wholesale_price)s,
                        %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
            except Exception as e:
                # Roll back this insert but continue
                self.conn.rollback()
                self.connect_supabase()  # Get new connection
                cursor = self.conn.cursor()
                raise  # Re-raise to track in outer loop
        
        self.conn.commit()
        return inserted
    
    def update_transfer_received_info(self, transfer_id: int, packages: List[Dict]):
        """Update transfer with received package count and timestamp."""
        if not packages:
            return
        
        cursor = self.conn.cursor()
        
        # Extract received info from packages
        received_dates = [p.get('ReceivedDateTime') for p in packages if p.get('ReceivedDateTime')]
        received_date = received_dates[0] if received_dates else None
        package_count = len(packages)
        
        cursor.execute("""
            UPDATE metrc_transfers
            SET 
                received_package_count = %s,
                delivery_received_package_count = %s,
                received_date_time = COALESCE(%s, received_date_time)
            WHERE id = %s
        """, (package_count, package_count, received_date, transfer_id))
        
        self.conn.commit()
    
    def backfill_all(self):
        """Main backfill process."""
        print("\n=== Transfer Enrichment Backfill ===\n")
        
        # Get transfers to process
        transfers = self.get_transfers_to_enrich()
        
        if not transfers:
            print("\nNo transfers to enrich!")
            return
        
        total_packages = 0
        total_transfers = 0
        failed = 0
        
        for i, transfer in enumerate(transfers, 1):
            transfer_id = transfer['id']
            manifest = transfer['manifest_number']
            
            try:
                # Parse JSON data
                transfer_data = transfer['data']
                if isinstance(transfer_data, str):
                    transfer_data = json.loads(transfer_data)
                
                # Extract packages
                packages = self.extract_packages_from_json(transfer_data)
                if not packages:
                    continue
                
                # Get delivery ID (will use transfer ID if no separate delivery ID)
                delivery_id = self.extract_delivery_id(transfer_data)
                if not delivery_id:
                    print(f"  {i}/{len(transfers)} ✗ {manifest}: No ID in data")
                    failed += 1
                    continue
                
                # Store packages
                pkg_count = self.upsert_transfer_packages(transfer_id, packages)
                
                # Update transfer with received info
                self.update_transfer_received_info(transfer_id, packages)
                
                total_packages += pkg_count
                total_transfers += 1
                
                if i % 100 == 0:
                    print(f"  Progress: {i}/{len(transfers)} transfers, {total_packages} packages")
                
            except Exception as e:
                print(f"  {i}/{len(transfers)} ✗ {manifest}: {e}")
                failed += 1
        
        print(f"\n=== Backfill Complete ===")
        print(f"Transfers enriched: {total_transfers}")
        print(f"Packages extracted: {total_packages}")
        print(f"Failed: {failed}")
        print(f"\nVerify with:")
        print(f"  SELECT COUNT(*) FROM metrc_transfer_packages;")
        print(f"  SELECT * FROM transfer_package_summary LIMIT 10;")

def main():
    try:
        backfill = TransferEnrichmentBackfill()
        backfill.backfill_all()
    except Exception as e:
        print(f"\n✗ Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
