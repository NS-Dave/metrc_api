"""
Updated transfer sync logic with proper direction handling.

Key changes:
1. Store incoming and outgoing separately (same ID can appear twice)
2. Deduplicate by (transfer_id, license, direction) instead of just transfer_id
3. Enrich packages with full data from /packages/v2/{id} endpoint
"""

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values, DictCursor
from datetime import datetime, timedelta
import json
import os
from typing import List, Dict, Optional, Tuple
import time

from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from processing import ProcessingClient
from supabase_config import get_connection_string

CULTIVATION_LICENSE = os.getenv('METRC_LICENSE_CULTIVATION', 'MC281599')
PROCESSING_LICENSE = os.getenv('METRC_LICENSE_PROCESSING', 'MP281433')


class DirectionAwareTransferSync:
    """Syncs transfers with proper direction tracking."""
    
    def __init__(self, password: Optional[str] = None):
        config = MetrcConfig.from_env()
        self.metrc_client = MetrcClient(config)
        self.cultivation = CultivationClient(self.metrc_client)
        self.processing = ProcessingClient(self.metrc_client)
        
        self.conn_string = get_connection_string(password)
        self.conn = None
    
    def connect_supabase(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(self.conn_string)
            self.conn.autocommit = False
    
    def sync_transfers_with_direction(self, license_number: str, days: int = 7):
        """
        Sync transfers with proper direction handling.
        
        Key difference from old logic:
        - Incoming and outgoing stored separately
        - No deduplication between directions
        - Each transfer tagged with 'incoming' or 'outgoing'
        """
        print(f"\nSyncing transfers for {license_number} (last {days} days)...")
        
        end = datetime.now()
        start = end - timedelta(days=days)
        
        try:
            # Fetch INCOMING transfers
            print("  Fetching incoming transfers...")
            incoming_transfers = []
            current = start
            
            while current < end:
                chunk_end = min(current + timedelta(hours=24), end)
                start_str = current.strftime('%Y-%m-%d')
                end_str = chunk_end.strftime('%Y-%m-%d')
                
                response = self.processing.get_incoming_transfers(
                    license_number=license_number,
                    last_modified_start=start_str,
                    last_modified_end=end_str
                )
                chunk = response['Data'] if isinstance(response, dict) else []
                incoming_transfers.extend(chunk)
                current = chunk_end
            
            # Deduplicate incoming by transfer ID
            incoming_unique = self._deduplicate_by_id(incoming_transfers)
            print(f"    Found {len(incoming_unique)} unique incoming transfers")
            
            # Fetch OUTGOING transfers
            print("  Fetching outgoing transfers...")
            outgoing_transfers = []
            current = start
            
            while current < end:
                chunk_end = min(current + timedelta(hours=24), end)
                start_str = current.strftime('%Y-%m-%d')
                end_str = chunk_end.strftime('%Y-%m-%d')
                
                response = self.processing.get_outgoing_transfers(
                    license_number=license_number,
                    last_modified_start=start_str,
                    last_modified_end=end_str
                )
                chunk = response['Data'] if isinstance(response, dict) else []
                outgoing_transfers.extend(chunk)
                current = chunk_end
            
            # Deduplicate outgoing by transfer ID
            outgoing_unique = self._deduplicate_by_id(outgoing_transfers)
            print(f"    Found {len(outgoing_unique)} unique outgoing transfers")
            
            # Store incoming with direction='incoming'
            incoming_inserted, incoming_updated = self.upsert_transfers_with_direction(
                incoming_unique, license_number, 'incoming'
            )
            print(f"    ✓ Incoming: {incoming_inserted} inserted, {incoming_updated} updated")
            
            # Store outgoing with direction='outgoing'
            outgoing_inserted, outgoing_updated = self.upsert_transfers_with_direction(
                outgoing_unique, license_number, 'outgoing'
            )
            print(f"    ✓ Outgoing: {outgoing_inserted} inserted, {outgoing_updated} updated")
            
            # Enrich outgoing transfers with full package data
            print("  Enriching outgoing transfer packages...")
            enriched_count = self.enrich_outgoing_transfer_packages(license_number)
            print(f"    ✓ Enriched {enriched_count} outgoing packages with full data")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            raise
    
    def _deduplicate_by_id(self, transfers: List[Dict]) -> List[Dict]:
        """Deduplicate transfers by ID within same direction."""
        seen_ids = set()
        unique = []
        for transfer in transfers:
            if transfer['Id'] not in seen_ids:
                seen_ids.add(transfer['Id'])
                unique.append(transfer)
        return unique
    
    def upsert_transfers_with_direction(
        self, 
        transfers: List[Dict], 
        license_number: str, 
        direction: str
    ) -> Tuple[int, int]:
        """
        Upsert transfers with direction tracking.
        
        Unique key: (id, license_number, direction)
        This allows same transfer ID to exist as both incoming and outgoing.
        """
        if not transfers:
            return (0, 0)
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        updated = 0
        
        for transfer in transfers:
            transfer_id = transfer['Id']
            
            # Check if exists with this direction
            cursor.execute("""
                SELECT id FROM metrc_transfers 
                WHERE id = %s AND license_number = %s AND direction = %s
            """, (transfer_id, license_number, direction))
            
            exists = cursor.fetchone() is not None
            
            # Extract facility info
            deliveries = transfer.get('Deliveries', [])
            recipient_name = transfer.get('RecipientFacilityName')
            recipient_license = transfer.get('RecipientFacilityLicenseNumber')
            if not recipient_name and deliveries:
                recipient_name = deliveries[0].get('RecipientFacilityName')
            if not recipient_license and deliveries:
                recipient_license = deliveries[0].get('RecipientFacilityLicenseNumber')
            
            data = {
                'id': transfer_id,
                'manifest_number': transfer.get('ManifestNumber'),
                'license_number': license_number,
                'direction': direction,
                'shipper_facility_name': transfer.get('ShipperFacilityName'),
                'shipper_facility_license_number': transfer.get('ShipperFacilityLicenseNumber'),
                'transporter_facility_name': transfer.get('TransporterFacilityName'),
                'transporter_facility_license_number': transfer.get('TransporterFacilityLicenseNumber'),
                'destination_facility_name': recipient_name,
                'destination_facility_license_number': recipient_license,
                'created_date': transfer.get('CreatedDateTime'),
                'transfer_type': transfer.get('TransferTypeName'),
                'shipment_type': transfer.get('ShipmentTypeName'),
                'est_departure_datetime': transfer.get('EstimatedDepartureDateTime'),
                'est_arrival_datetime': transfer.get('EstimatedArrivalDateTime'),
                'actual_departure_datetime': transfer.get('ActualDepartureDateTime'),
                'actual_arrival_datetime': transfer.get('ActualArrivalDateTime'),
                'package_count': transfer.get('PackageCount'),
                'delivery_count': transfer.get('DeliveryCount'),
                'received_delivery_count': transfer.get('ReceivedDeliveryCount'),
                'last_modified': transfer.get('LastModified'),
                'data': json.dumps(transfer)
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_transfers SET
                        manifest_number = %(manifest_number)s,
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
                        data = %(data)s,
                        synced_at = CURRENT_TIMESTAMP
                    WHERE id = %(id)s 
                      AND license_number = %(license_number)s 
                      AND direction = %(direction)s
                """, data)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO metrc_transfers (
                        id, manifest_number, license_number, direction,
                        shipper_facility_name, shipper_facility_license_number,
                        transporter_facility_name, transporter_facility_license_number,
                        destination_facility_name, destination_facility_license_number,
                        created_date, transfer_type, shipment_type,
                        est_departure_datetime, est_arrival_datetime,
                        actual_departure_datetime, actual_arrival_datetime,
                        package_count, delivery_count, received_delivery_count,
                        last_modified, data
                    ) VALUES (
                        %(id)s, %(manifest_number)s, %(license_number)s, %(direction)s,
                        %(shipper_facility_name)s, %(shipper_facility_license_number)s,
                        %(transporter_facility_name)s, %(transporter_facility_license_number)s,
                        %(destination_facility_name)s, %(destination_facility_license_number)s,
                        %(created_date)s, %(transfer_type)s, %(shipment_type)s,
                        %(est_departure_datetime)s, %(est_arrival_datetime)s,
                        %(actual_departure_datetime)s, %(actual_arrival_datetime)s,
                        %(package_count)s, %(delivery_count)s, %(received_delivery_count)s,
                        %(last_modified)s, %(data)s
                    )
                """, data)
                inserted += 1
            
            # Fetch and store delivery packages
            delivery_id = transfer.get('DeliveryId')
            
            # For outgoing transfers, DeliveryId is often 0
            # Need to fetch deliveries separately
            if direction == 'outgoing' and (not delivery_id or delivery_id == 0):
                try:
                    # Get deliveries for this transfer
                    url = f"/transfers/v2/{transfer_id}/deliveries"
                    deliveries_response = self.processing.client.get(url, license_number=license_number)
                    deliveries = None
                    if isinstance(deliveries_response, dict):
                        deliveries = deliveries_response.get('Data', [])
                    elif isinstance(deliveries_response, list):
                        deliveries = deliveries_response
                    
                    # Process each delivery
                    if deliveries:
                        # Update transfer with delivery data from first delivery
                        # (most transfers have 1 delivery, but this enriches with the primary one)
                        first_delivery = deliveries[0]
                        cursor.execute("""
                            UPDATE metrc_transfers SET
                                destination_facility_name = %s,
                                destination_facility_license_number = %s,
                                shipment_type = %s,
                                actual_departure_datetime = %s,
                                actual_arrival_datetime = %s,
                                est_departure_datetime = %s,
                                est_arrival_datetime = %s
                            WHERE id = %s AND license_number = %s AND direction = %s
                        """, (
                            first_delivery.get('RecipientFacilityName'),
                            first_delivery.get('RecipientFacilityLicenseNumber'),
                            first_delivery.get('ShipmentTypeName'),
                            first_delivery.get('ActualDepartureDateTime'),
                            first_delivery.get('ReceivedDateTime'),  # Use ReceivedDateTime for actual arrival
                            first_delivery.get('EstimatedDepartureDateTime'),
                            first_delivery.get('EstimatedArrivalDateTime'),
                            transfer_id,
                            license_number,
                            direction
                        ))
                        
                        for delivery in deliveries:
                            delivery_id = delivery.get('Id')
                            if delivery_id:
                                # Fetch full package details (not /wholesale)
                                try:
                                    url = f"/transfers/v2/deliveries/{delivery_id}/packages"
                                    detail = self.processing.client.get(url, license_number=license_number)
                                    packages = None
                                    if isinstance(detail, dict):
                                        packages = detail.get('Data', [])
                                    elif isinstance(detail, list):
                                        packages = detail
                                    
                                    if packages:
                                        print(f"      -> Found {len(packages)} packages for delivery {delivery_id}")
                                        self.upsert_transfer_packages_with_direction(
                                            transfer_id, delivery_id, packages, direction
                                        )
                                except Exception as e:
                                    print(f"      ! Package fetch error for delivery {delivery_id}: {e}")
                except Exception as e:
                    print(f"      ! Could not fetch deliveries for transfer {transfer_id}: {e}")
            
            # For incoming transfers, DeliveryId is embedded
            elif delivery_id and delivery_id != 0:
                try:
                    # Fetch full package details (not /wholesale)
                    url = f"/transfers/v2/deliveries/{delivery_id}/packages"
                    detail = self.processing.client.get(url, license_number=license_number)
                    packages = None
                    if isinstance(detail, dict):
                        packages = detail.get('Data', [])
                    elif isinstance(detail, list):
                        packages = detail
                    
                    if packages:
                        print(f"      -> Found {len(packages)} packages for delivery {delivery_id}")
                        self.upsert_transfer_packages_with_direction(
                            transfer_id, delivery_id, packages, direction
                        )
                except Exception as e:
                    # Some deliveries might not have package data available
                    print(f"      ! Package fetch error for delivery {delivery_id}: {e}")
        
        self.conn.commit()
        cursor.close()
        return (inserted, updated)
    
    def upsert_transfer_packages_with_direction(
        self,
        transfer_id: int,
        delivery_id: int,
        packages: List[Dict],
        direction: str
    ):
        """Store transfer packages with direction."""
        if not packages:
            return
        
        cursor = self.conn.cursor()
        
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
                'direction': direction,
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
                'quantity_shipped': pkg.get('ShippedQuantity'),
                'quantity_received': pkg.get('ReceivedQuantity'),
                'unit_of_measure_name': pkg.get('ShippedUnitOfMeasureName') or pkg.get('ReceivedUnitOfMeasureName'),
                'unit_of_measure_abbreviation': pkg.get('ShippedUnitOfMeasureAbbreviation') or pkg.get('ReceivedUnitOfMeasureAbbreviation'),
                'gross_weight': pkg.get('GrossWeight'),
                'gross_unit_of_weight_name': pkg.get('GrossUnitOfWeightName'),
                'gross_unit_of_weight_abbreviation': pkg.get('GrossUnitOfWeightAbbreviation'),
                'wholesale_price': pkg.get('WholesalePrice'),
                'shipper_wholesale_price': pkg.get('ShipperWholesalePrice'),
                'receiver_wholesale_price': pkg.get('ReceiverWholesalePrice'),
                'item_unit_thc_percent': pkg.get('ItemUnitThcPercent'),
                'item_unit_thc_content': pkg.get('ItemUnitThcContent'),
                'item_unit_thc_content_uom': pkg.get('ItemUnitThcContentUnitOfMeasureName'),
                'item_unit_cbd_percent': pkg.get('ItemUnitCbdPercent'),
                'item_unit_cbd_content': pkg.get('ItemUnitCbdContent'),
                'item_unit_cbd_content_uom': pkg.get('ItemUnitCbdContentUnitOfMeasureName'),
                'lab_testing_state': pkg.get('LabTestingState'),
                'lab_testing_state_date': pkg.get('LabTestingStateDate'),
                'is_testing_sample': pkg.get('IsTestingSample'),
                'is_process_validation_test_sample': pkg.get('IsProcessValidationTestSample'),
                'is_production_batch': pkg.get('ProductionBatchNumber') is not None,
                'production_batch_number': pkg.get('ProductionBatchNumber'),
                'is_trade_sample': pkg.get('IsTradeSample'),
                'is_on_hold': pkg.get('IsOnHold'),
                'packaged_date': pkg.get('PackagedDate'),
                'received_date_time': pkg.get('ReceivedDateTime'),
                'archived_date': pkg.get('ArchivedDate'),
                'finished_date': pkg.get('FinishedDate'),
                'last_modified': pkg.get('LastModified'),
                'full_package_fetched': True,  # We now have full data from /packages endpoint
                'data': json.dumps(pkg),
                'synced_at': datetime.now()
            }
            
            if exists:
                cursor.execute("""
                    UPDATE metrc_transfer_packages SET
                        delivery_id = %(delivery_id)s,
                        package_id = %(package_id)s,
                        package_type = %(package_type)s,
                        product_name = %(product_name)s,
                        product_category_name = %(product_category_name)s,
                        item_id = %(item_id)s,
                        item_name = %(item_name)s,
                        item_category_name = %(item_category_name)s,
                        item_strain_name = %(item_strain_name)s,
                        source_harvest_names = %(source_harvest_names)s,
                        source_package_labels = %(source_package_labels)s,
                        quantity_shipped = %(quantity_shipped)s,
                        quantity_received = %(quantity_received)s,
                        unit_of_measure_name = %(unit_of_measure_name)s,
                        unit_of_measure_abbreviation = %(unit_of_measure_abbreviation)s,
                        gross_weight = %(gross_weight)s,
                        gross_unit_of_weight_name = %(gross_unit_of_weight_name)s,
                        gross_unit_of_weight_abbreviation = %(gross_unit_of_weight_abbreviation)s,
                        wholesale_price = %(wholesale_price)s,
                        shipper_wholesale_price = %(shipper_wholesale_price)s,
                        receiver_wholesale_price = %(receiver_wholesale_price)s,
                        item_unit_thc_percent = %(item_unit_thc_percent)s,
                        item_unit_thc_content = %(item_unit_thc_content)s,
                        item_unit_thc_content_uom = %(item_unit_thc_content_uom)s,
                        item_unit_cbd_percent = %(item_unit_cbd_percent)s,
                        item_unit_cbd_content = %(item_unit_cbd_content)s,
                        item_unit_cbd_content_uom = %(item_unit_cbd_content_uom)s,
                        lab_testing_state = %(lab_testing_state)s,
                        lab_testing_state_date = %(lab_testing_state_date)s,
                        is_testing_sample = %(is_testing_sample)s,
                        is_process_validation_test_sample = %(is_process_validation_test_sample)s,
                        is_production_batch = %(is_production_batch)s,
                        production_batch_number = %(production_batch_number)s,
                        is_trade_sample = %(is_trade_sample)s,
                        is_on_hold = %(is_on_hold)s,
                        packaged_date = %(packaged_date)s,
                        received_date_time = %(received_date_time)s,
                        archived_date = %(archived_date)s,
                        finished_date = %(finished_date)s,
                        last_modified = %(last_modified)s,
                        full_package_fetched = %(full_package_fetched)s,
                        data = %(data)s,
                        synced_at = %(synced_at)s
                    WHERE transfer_id = %(transfer_id)s 
                      AND package_label = %(package_label)s 
                      AND direction = %(direction)s
                """, data)
            else:
                cursor.execute("""
                    INSERT INTO metrc_transfer_packages (
                        transfer_id, delivery_id, direction, package_id, package_label,
                        package_type, product_name, product_category_name,
                        item_id, item_name, item_category_name, item_strain_name,
                        source_harvest_names, source_package_labels,
                        quantity_shipped, quantity_received, 
                        unit_of_measure_name, unit_of_measure_abbreviation,
                        gross_weight, gross_unit_of_weight_name, gross_unit_of_weight_abbreviation,
                        wholesale_price, shipper_wholesale_price, receiver_wholesale_price,
                        item_unit_thc_percent, item_unit_thc_content, item_unit_thc_content_uom,
                        item_unit_cbd_percent, item_unit_cbd_content, item_unit_cbd_content_uom,
                        lab_testing_state, lab_testing_state_date,
                        is_testing_sample, is_process_validation_test_sample,
                        is_production_batch, production_batch_number,
                        is_trade_sample, is_on_hold,
                        packaged_date, received_date_time, archived_date, finished_date, last_modified,
                        full_package_fetched, data, synced_at
                    ) VALUES (
                        %(transfer_id)s, %(delivery_id)s, %(direction)s, %(package_id)s, %(package_label)s,
                        %(package_type)s, %(product_name)s, %(product_category_name)s,
                        %(item_id)s, %(item_name)s, %(item_category_name)s, %(item_strain_name)s,
                        %(source_harvest_names)s, %(source_package_labels)s,
                        %(quantity_shipped)s, %(quantity_received)s,
                        %(unit_of_measure_name)s, %(unit_of_measure_abbreviation)s,
                        %(gross_weight)s, %(gross_unit_of_weight_name)s, %(gross_unit_of_weight_abbreviation)s,
                        %(wholesale_price)s, %(shipper_wholesale_price)s, %(receiver_wholesale_price)s,
                        %(item_unit_thc_percent)s, %(item_unit_thc_content)s, %(item_unit_thc_content_uom)s,
                        %(item_unit_cbd_percent)s, %(item_unit_cbd_content)s, %(item_unit_cbd_content_uom)s,
                        %(lab_testing_state)s, %(lab_testing_state_date)s,
                        %(is_testing_sample)s, %(is_process_validation_test_sample)s,
                        %(is_production_batch)s, %(production_batch_number)s,
                        %(is_trade_sample)s, %(is_on_hold)s,
                        %(packaged_date)s, %(received_date_time)s, %(archived_date)s, %(finished_date)s, %(last_modified)s,
                        %(full_package_fetched)s, %(data)s, %(synced_at)s
                    )
                """, data)
        
        self.conn.commit()
    
    def enrich_outgoing_transfer_packages(self, license_number: str, limit: int = 100) -> int:
        """
        Enrich outgoing transfer packages with full package data.
        
        Uses /packages/v2/{id} endpoint to get complete package information
        for packages that were shipped out.
        """
        self.connect_supabase()
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        
        # Find outgoing packages that need enrichment
        cursor.execute("""
            SELECT 
                tp.id,
                tp.package_id,
                tp.package_label,
                tp.transfer_id,
                t.manifest_number
            FROM metrc_transfer_packages tp
            JOIN metrc_transfers t ON t.id = tp.transfer_id AND t.direction = tp.direction
            WHERE tp.direction = 'outgoing'
              AND tp.package_id IS NOT NULL
              AND (tp.full_package_fetched = FALSE OR tp.full_package_fetched IS NULL)
              AND (tp.full_package_fetch_attempted_at IS NULL 
                   OR tp.full_package_fetch_attempted_at < NOW() - INTERVAL '7 days')
            LIMIT %s
        """, (limit,))
        
        packages_to_enrich = cursor.fetchall()
        
        if not packages_to_enrich:
            return 0
        
        enriched_count = 0
        
        for pkg_record in packages_to_enrich:
            package_id = pkg_record['package_id']
            
            try:
                # Fetch full package data from packages endpoint
                endpoint = f"packages/v2/{package_id}"
                full_package = self.processing.client.get(endpoint, license_number=license_number)
                
                if full_package:
                    # Update with full package details
                    self._update_package_with_full_data(
                        pkg_record['id'], 
                        full_package
                    )
                    enriched_count += 1
                    print(f"      ✓ Enriched package {pkg_record['package_label']} (transfer {pkg_record['manifest_number']})")
                else:
                    # Mark as attempted
                    self._mark_package_fetch_attempted(pkg_record['id'], "No data returned")
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"      ✗ Failed to enrich package {pkg_record['package_label']}: {e}")
                self._mark_package_fetch_attempted(pkg_record['id'], str(e))
        
        self.conn.commit()
        return enriched_count
    
    def _update_package_with_full_data(self, transfer_package_id: int, full_package: Dict):
        """Update transfer package with full package data."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE metrc_transfer_packages SET
                product_name = %s,
                product_category_name = %s,
                item_id = %s,
                item_name = %s,
                item_category_name = %s,
                item_strain_name = %s,
                source_harvest_names = %s,
                source_package_labels = %s,
                quantity_shipped = %s,
                unit_of_measure_name = %s,
                unit_of_measure_abbreviation = %s,
                item_unit_thc_percent = %s,
                item_unit_thc_content = %s,
                item_unit_thc_content_uom = %s,
                item_unit_cbd_percent = %s,
                item_unit_cbd_content = %s,
                item_unit_cbd_content_uom = %s,
                packaged_date = %s,
                lab_testing_state = %s,
                is_production_batch = %s,
                production_batch_number = %s,
                is_testing_sample = %s,
                is_trade_sample = %s,
                full_package_fetched = TRUE,
                full_package_fetch_attempted_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            full_package.get('Item', {}).get('Name') if isinstance(full_package.get('Item'), dict) else full_package.get('ProductName'),
            full_package.get('Item', {}).get('ProductCategoryName') if isinstance(full_package.get('Item'), dict) else full_package.get('ProductCategoryName'),
            full_package.get('Item', {}).get('Id') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemId'),
            full_package.get('Item', {}).get('Name') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemName'),
            full_package.get('Item', {}).get('CategoryName') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemCategoryName'),
            full_package.get('Item', {}).get('StrainName') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemStrainName'),
            full_package.get('SourceHarvestNames'),
            full_package.get('SourcePackageLabels'),
            full_package.get('Quantity'),
            full_package.get('UnitOfMeasureName'),
            full_package.get('UnitOfMeasureAbbreviation'),
            full_package.get('Item', {}).get('UnitThcPercent') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemUnitThcPercent'),
            full_package.get('Item', {}).get('UnitThcContent') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemUnitThcContent'),
            full_package.get('Item', {}).get('UnitThcContentUnitOfMeasureName') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemUnitThcContentUnitOfMeasureName'),
            full_package.get('Item', {}).get('UnitCbdPercent') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemUnitCbdPercent'),
            full_package.get('Item', {}).get('UnitCbdContent') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemUnitCbdContent'),
            full_package.get('Item', {}).get('UnitCbdContentUnitOfMeasureName') if isinstance(full_package.get('Item'), dict) else full_package.get('ItemUnitCbdContentUnitOfMeasureName'),
            full_package.get('PackagedDate'),
            full_package.get('LabTestingState'),
            full_package.get('IsProductionBatch', False),
            full_package.get('ProductionBatchNumber'),
            full_package.get('IsTestingSample', False),
            full_package.get('IsTradeSample', False),
            transfer_package_id
        ))
    
    def _mark_package_fetch_attempted(self, transfer_package_id: int, error: str = None):
        """Mark that we attempted to fetch full package data."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE metrc_transfer_packages SET
                full_package_fetch_attempted_at = CURRENT_TIMESTAMP,
                full_package_fetch_error = %s
            WHERE id = %s
        """, (error, transfer_package_id))
    
    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()


if __name__ == '__main__':
    syncer = DirectionAwareTransferSync()
    
    try:
        # Sync both licenses
        syncer.sync_transfers_with_direction(PROCESSING_LICENSE, days=7)
        syncer.sync_transfers_with_direction(CULTIVATION_LICENSE, days=7)
        
    finally:
        syncer.close()
