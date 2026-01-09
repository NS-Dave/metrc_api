#!/usr/bin/env python3
"""
Historical data backfill for Metrc data warehouse.

Backfills harvests, packages, and transfers from March 9, 2023 to present
using 24-hour windows (Metrc last-modified limit). Resumable via metrc_sync_log.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import psycopg2
from dotenv import load_dotenv

from client import MetrcClient
from config import MetrcConfig
from cultivation import CultivationClient
from processing import ProcessingClient
from supabase_config import get_connection_string

load_dotenv()

CULTIVATION_LICENSE = "MC281599"
PROCESSING_LICENSE = "MP281433"
BACKFILL_START = datetime(2023, 3, 9)

class MetrcHistoricalBackfill:
    """Runs historical backfill in 24-hour windows."""

    def __init__(self):
        self.config = MetrcConfig.from_env()
        self.client = MetrcClient(self.config)
        self.cultivation = CultivationClient(self.client)
        self.processing = ProcessingClient(self.client)
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.start_time = datetime.now()

    # --------------------------- connections ---------------------------
    def connect_supabase(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(get_connection_string())

    # --------------------------- logging ---------------------------
    def log_sync_start(self, entity_type: str, license_number: str,
                       window_start: datetime, window_end: datetime) -> str:
        self.connect_supabase()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO metrc_sync_log (
                entity_type, license_number, sync_type,
                date_range_start, date_range_end, status, sync_start
            ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (entity_type, license_number, 'backfill', window_start, window_end, 'running')
        )
        sync_id = cursor.fetchone()[0]
        self.conn.commit()
        cursor.close()
        return str(sync_id)

    def log_sync_end(self, sync_id: str, records_pulled: int, inserted: int, updated: int,
                     status: str = 'completed', error_msg: Optional[str] = None):
        self.connect_supabase()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE metrc_sync_log SET
                status = %s,
                records_pulled = %s,
                records_inserted = %s,
                records_updated = %s,
                error_message = %s,
                sync_end = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, records_pulled, inserted, updated, error_msg, sync_id)
        )
        self.conn.commit()
        cursor.close()

    def get_last_completed_window(self, license_number: str) -> Optional[datetime]:
        self.connect_supabase()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT date_range_end
            FROM metrc_sync_log
            WHERE license_number = %s
              AND sync_type = 'backfill'
              AND status = 'completed'
            ORDER BY date_range_end DESC
            LIMIT 1
            """,
            (license_number,)
        )
        row = cursor.fetchone()
        cursor.close()
        # Normalize to naive datetime for comparisons with datetime.now()
        return row[0].replace(tzinfo=None) if row and row[0] else None

    # --------------------------- upserts ---------------------------
    def upsert_harvests(self, harvests: List[Dict], license_number: str) -> Tuple[int, int]:
        if not harvests:
            return (0, 0)
        self.connect_supabase()
        cursor = self.conn.cursor()
        inserted = updated = 0
        for harvest in harvests:
            cursor.execute("SELECT id FROM metrc_harvests WHERE id = %s", (harvest['Id'],))
            exists = cursor.fetchone() is not None
            data = {
                'id': harvest['Id'],
                'harvest_name': harvest.get('Name'),
                'license_number': license_number,
                'harvest_type': harvest.get('HarvestType'),
                'source_strain_count': harvest.get('SourceStrainCount'),
                'source_strain_names': harvest.get('SourceStrainNames'),
                'drying_location_name': harvest.get('DryingLocationName'),
                'harvest_start_date': harvest.get('HarvestStartDate'),
                'finished_date': harvest.get('FinishedDate'),
                'is_finished': harvest.get('IsFinished'),
                'current_weight': harvest.get('CurrentWeight'),
                'total_waste_weight': harvest.get('TotalWasteWeight'),
                'total_packaged_weight': harvest.get('TotalPackagedWeight'),
                'total_restorative_waste_weight': harvest.get('TotalRestorativeWasteWeight'),
                'unit_of_weight': harvest.get('UnitOfWeightName'),
                'lab_testing_state': harvest.get('LabTestingState'),
                'lab_testing_state_date': harvest.get('LabTestingStateDate'),
                'is_on_hold': harvest.get('IsOnHold'),
                'last_modified': harvest.get('LastModified'),
                'data': json.dumps(harvest)
            }
            if exists:
                cursor.execute(
                    """
                    UPDATE metrc_harvests SET
                        harvest_name = %(harvest_name)s,
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
                        data = %(data)s
                    WHERE id = %(id)s
                    """,
                    data,
                )
                updated += 1
            else:
                cursor.execute(
                    """
                    INSERT INTO metrc_harvests (
                        id, harvest_name, license_number, harvest_type,
                        source_strain_count, source_strain_names,
                        drying_location_name, harvest_start_date, harvest_date,
                        finished_date, is_finished, current_weight,
                        total_waste_weight, total_packaged_weight,
                        total_restorative_waste_weight, packaged_date,
                        unit_of_weight, lab_testing_state,
                        lab_testing_state_date, is_on_hold, last_modified, data
                    ) VALUES (
                        %(id)s, %(harvest_name)s, %(license_number)s, %(harvest_type)s,
                        %(source_strain_count)s, %(source_strain_names)s,
                        %(drying_location_name)s, %(harvest_start_date)s, %(harvest_date)s,
                        %(finished_date)s, %(is_finished)s, %(current_weight)s,
                        %(total_waste_weight)s, %(total_packaged_weight)s,
                        %(total_restorative_waste_weight)s, %(packaged_date)s,
                        %(unit_of_weight)s, %(lab_testing_state)s,
                        %(lab_testing_state_date)s, %(is_on_hold)s, %(last_modified)s,
                        %(data)s
                    )
                    """,
                    data,
                )
                inserted += 1
        self.conn.commit()
        cursor.close()
        return (inserted, updated)

    def upsert_packages(self, packages: List[Dict], license_number: str) -> Tuple[int, int]:
        if not packages:
            return (0, 0)
        self.connect_supabase()
        cursor = self.conn.cursor()
        inserted = updated = 0
        for package in packages:
            cursor.execute("SELECT id FROM metrc_packages WHERE id = %s", (package['Id'],))
            exists = cursor.fetchone() is not None
            data = {
                'id': package['Id'],
                'label': package.get('Label'),
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
                'data': json.dumps(package)
            }
            if exists:
                cursor.execute(
                    """
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
                        data = %(data)s
                    WHERE id = %(id)s
                    """,
                    data,
                )
                updated += 1
            else:
                cursor.execute(
                    """
                    INSERT INTO metrc_packages (
                        id, label, package_type, license_number,
                        product_name, product_category_name, item_name,
                        item_id, quantity, unit_of_measure, packaged_date,
                        initial_lab_testing_state, lab_testing_state,
                        lab_testing_state_date, is_production_batch,
                        production_batch_number, source_production_batch_numbers,
                        source_package_labels, source_harvest_names,
                        is_trade_sample, is_testing_sample,
                        is_process_validation_test_sample, is_donation,
                        is_on_hold, archived_date, finished_date,
                        location_name, note, last_modified, data
                    ) VALUES (
                        %(id)s, %(label)s, %(package_type)s, %(license_number)s,
                        %(product_name)s, %(product_category_name)s, %(item_name)s,
                        %(item_id)s, %(quantity)s, %(unit_of_measure)s, %(packaged_date)s,
                        %(initial_lab_testing_state)s, %(lab_testing_state)s,
                        %(lab_testing_state_date)s, %(is_production_batch)s,
                        %(production_batch_number)s, %(source_production_batch_numbers)s,
                        %(source_package_labels)s, %(source_harvest_names)s,
                        %(is_trade_sample)s, %(is_testing_sample)s,
                        %(is_process_validation_test_sample)s, %(is_donation)s,
                        %(is_on_hold)s, %(archived_date)s, %(finished_date)s,
                        %(location_name)s, %(note)s, %(last_modified)s, %(data)s
                    )
                    """,
                    data,
                )
                inserted += 1
        self.conn.commit()
        cursor.close()
        return (inserted, updated)

    def upsert_transfers(self, transfers: List[Dict], license_number: str) -> Tuple[int, int]:
        if not transfers:
            return (0, 0)
        self.connect_supabase()
        cursor = self.conn.cursor()
        inserted = updated = 0
        for transfer in transfers:
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
            deliveries = transfer.get('Deliveries', [])
            recipient_name = transfer.get('RecipientFacilityName')
            recipient_license = transfer.get('RecipientFacilityLicenseNumber')
            if not recipient_name and deliveries:
                recipient_name = deliveries[0].get('RecipientFacilityName')
            if not recipient_license and deliveries:
                recipient_license = deliveries[0].get('RecipientFacilityLicenseNumber')
            
            data = {
                'id': transfer['Id'],
                'manifest_number': transfer.get('ManifestNumber'),
                'license_number': license_number,
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
                cursor.execute(
                    """
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
                        data = %(data)s
                    WHERE id = %(id)s
                    """,
                    data,
                )
                updated += 1
            else:
                cursor.execute(
                    """
                    INSERT INTO metrc_transfers (
                        id, manifest_number, license_number,
                        shipper_facility_name, shipper_facility_license_number,
                        transporter_facility_name, transporter_facility_license_number,
                        destination_facility_name, destination_facility_license_number,
                        created_date, transfer_type, shipment_type,
                        est_departure_datetime, est_arrival_datetime,
                        actual_departure_datetime, actual_arrival_datetime,
                        package_count, delivery_count, received_delivery_count,
                        last_modified, data
                    ) VALUES (
                        %(id)s, %(manifest_number)s, %(license_number)s,
                        %(shipper_facility_name)s, %(shipper_facility_license_number)s,
                        %(transporter_facility_name)s, %(transporter_facility_license_number)s,
                        %(destination_facility_name)s, %(destination_facility_license_number)s,
                        %(created_date)s, %(transfer_type)s, %(shipment_type)s,
                        %(est_departure_datetime)s, %(est_arrival_datetime)s,
                        %(actual_departure_datetime)s, %(actual_arrival_datetime)s,
                        %(package_count)s, %(delivery_count)s, %(received_delivery_count)s,
                        %(last_modified)s, %(data)s
                    )
                    """,
                    data,
                )
                inserted += 1
        self.conn.commit()
        cursor.close()
        return (inserted, updated)

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
            
            # Check if transfer already has Deliveries embedded
            if transfer.get('Deliveries'):
                enriched.append(transfer)
                # Still try to get transporter details even if Deliveries exist
                self._fetch_and_store_transporter_details(transfer_id, transfer.get('DeliveryId'), license_number)
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
                    # Store packages in database
                    stored_count = self.upsert_transfer_packages(transfer_id, delivery_id, packages)
                    
                    # Add to transfer object for JSON storage
                    transfer['Deliveries'] = [{'Packages': packages, 'Id': delivery_id}]
                    packages_enriched += 1
                
                # Fetch and store transporter details
                transporter_stored = self._fetch_and_store_transporter_details(
                    transfer_id, delivery_id, license_number
                )
                if transporter_stored:
                    transporters_enriched += 1
                    
            except Exception as e:
                pass  # Silent fail for historical - some deliveries may be inaccessible

            enriched.append(transfer)

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
            pass
        
        return False
    
    def upsert_transfer_packages(self, transfer_id: int, delivery_id: int, packages: List[Dict]) -> int:
        """Store transfer package details with wholesale pricing."""
        if not packages:
            return 0
        
        self.connect_supabase()
        cursor = self.conn.cursor()
        
        inserted = 0
        for pkg in packages:
            # Check if exists
            cursor.execute("""
                SELECT id FROM metrc_transfer_packages 
                WHERE transfer_id = %s AND package_label = %s
            """, (transfer_id, pkg.get('PackageLabel')))
            exists = cursor.fetchone() is not None
            
            data = {
                'transfer_id': transfer_id,
                'delivery_id': delivery_id,
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
                'wholesale_price': pkg.get('WholesalePrice'),
                'shipper_wholesale_price': pkg.get('ShipperWholesalePrice'),
                'receiver_wholesale_price': pkg.get('ReceiverWholesalePrice'),
                'packaged_date': pkg.get('PackagedDate'),
                'received_date_time': pkg.get('ReceivedDateTime'),
                'data': json.dumps(pkg),
                'synced_at': datetime.now()
            }
            
            if not exists:
                cursor.execute("""
                    INSERT INTO metrc_transfer_packages (
                        transfer_id, delivery_id, package_id, package_label, package_type,
                        product_name, product_category_name, item_id, item_name, item_category_name, item_strain_name,
                        source_harvest_names, source_package_labels, quantity_shipped, quantity_received,
                        unit_of_measure_name, wholesale_price, shipper_wholesale_price, receiver_wholesale_price,
                        packaged_date, received_date_time, data, synced_at
                    ) VALUES (
                        %(transfer_id)s, %(delivery_id)s, %(package_id)s, %(package_label)s, %(package_type)s,
                        %(product_name)s, %(product_category_name)s, %(item_id)s, %(item_name)s, %(item_category_name)s, %(item_strain_name)s,
                        %(source_harvest_names)s, %(source_package_labels)s, %(quantity_shipped)s, %(quantity_received)s,
                        %(unit_of_measure_name)s, %(wholesale_price)s, %(shipper_wholesale_price)s, %(receiver_wholesale_price)s,
                        %(packaged_date)s, %(received_date_time)s, %(data)s, %(synced_at)s
                    )
                """, data)
                inserted += 1
        
        self.conn.commit()
        return inserted
    
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

    # --------------------------- window sync ---------------------------
    def sync_window(self, license_number: str, window_start: datetime, window_end: datetime) -> Tuple[int, int, int]:
        start_str = window_start.strftime('%Y-%m-%dT%H:%M:%S')
        end_str = window_end.strftime('%Y-%m-%dT%H:%M:%S')
        total_records = total_inserted = total_updated = 0

        # Harvests (active snapshot + inactive window) - CULTIVATION ONLY
        if license_number == CULTIVATION_LICENSE:
            try:
                active_resp = self.cultivation.get_harvests('active', license_number=license_number)
                active = active_resp['Data'] if isinstance(active_resp, dict) and 'Data' in active_resp else active_resp
                inactive_resp = self.cultivation.get_harvests('inactive', last_modified_start=start_str, last_modified_end=end_str, license_number=license_number)
                inactive = inactive_resp['Data'] if isinstance(inactive_resp, dict) and 'Data' in inactive_resp else inactive_resp
                harvests = (active or []) + (inactive or [])
                if harvests:
                    ins, upd = self.upsert_harvests(harvests, license_number)
                    total_records += len(harvests)
                    total_inserted += ins
                    total_updated += upd
            except Exception as e:
                print(f"      ✗ Harvests error: {e}")

        # Packages (active + inactive window)
        try:
            active_resp = self.processing.get_packages('active', last_modified_start=start_str, last_modified_end=end_str, license_number=license_number)
            active = active_resp['Data'] if isinstance(active_resp, dict) and 'Data' in active_resp else active_resp
            inactive_resp = self.processing.get_packages('inactive', last_modified_start=start_str, last_modified_end=end_str, license_number=license_number)
            inactive = inactive_resp['Data'] if isinstance(inactive_resp, dict) and 'Data' in inactive_resp else inactive_resp
            packages = (active or []) + (inactive or [])
            if packages:
                ins, upd = self.upsert_packages(packages, license_number)
                total_records += len(packages)
                total_inserted += ins
                total_updated += upd
        except Exception as e:
            print(f"      ✗ Packages error: {e}")

        # Transfers (incoming + outgoing window)
        try:
            incoming_resp = self.processing.get_incoming_transfers(last_modified_start=start_str, last_modified_end=end_str, license_number=license_number)
            incoming = incoming_resp['Data'] if isinstance(incoming_resp, dict) and 'Data' in incoming_resp else incoming_resp
        except Exception as e:
            print(f"      ✗ Transfers (incoming) error: {e}")
            incoming = []
        try:
            outgoing_resp = self.processing.get_outgoing_transfers(last_modified_start=start_str, last_modified_end=end_str, license_number=license_number)
            outgoing = outgoing_resp['Data'] if isinstance(outgoing_resp, dict) and 'Data' in outgoing_resp else outgoing_resp
        except Exception as e:
            print(f"      ✗ Transfers (outgoing) error: {e}")
            outgoing = []

        transfers = (incoming or []) + (outgoing or [])
        if transfers:
            transfers = self.enrich_transfers_with_deliveries(transfers, license_number)
            ins, upd = self.upsert_transfers(transfers, license_number)
            total_records += len(transfers)
            total_inserted += ins
            total_updated += upd

        return total_records, total_inserted, total_updated

    # --------------------------- backfill loop ---------------------------
    def backfill(self, license_number: str, start_date: datetime, end_date: datetime):
        print("=" * 70)
        print(f"BACKFILL: {license_number}")
        print(f"Range: {start_date.date()} to {end_date.date()}")
        print("=" * 70)
        print()

        last_window_end = self.get_last_completed_window(license_number)
        current = last_window_end if last_window_end and last_window_end > start_date else start_date

        window_count = 0
        total_records = total_inserted = total_updated = 0

        while current < end_date:
            window_start = current
            window_end = min(current + timedelta(hours=24), end_date)
            window_count += 1

            total_days = (end_date - start_date).days or 1
            completed_days = (current - start_date).days
            percent = int((completed_days / total_days) * 100)

            print(f"Window {window_count}: {window_start.date()} → {window_end.date()} [{percent}%]", end=" ")
            sync_id = self.log_sync_start('harvests_packages_transfers', license_number, window_start, window_end)

            try:
                records, ins, upd = self.sync_window(license_number, window_start, window_end)
                self.log_sync_end(sync_id, records, ins, upd)
                total_records += records
                total_inserted += ins
                total_updated += upd
                if records:
                    print(f"✓ {records} records ({ins} new, {upd} updated)")
                else:
                    print("✓ (no changes)")
            except Exception as e:
                self.conn.rollback()
                self.log_sync_end(sync_id, 0, 0, 0, 'failed', str(e))
                print(f"✗ {e}")

            current = window_end

        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
        print()
        print("=" * 70)
        print(f"BACKFILL COMPLETE: {license_number}")
        print(f"  Windows processed: {window_count}")
        print(f"  Total records: {total_records}")
        print(f"  Inserted: {total_inserted}")
        print(f"  Updated: {total_updated}")
        print(f"  Time elapsed: {elapsed:.1f} minutes")
        print("=" * 70)
        print()


def run_backfill():
    print("\n" + "=" * 70)
    print("METRC HISTORICAL BACKFILL")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)
    print()

    # Test connections
    print("Testing Metrc API connection...", end=" ")
    try:
        cfg = MetrcConfig.from_env()
        cli = MetrcClient(cfg)
        cli.get_facilities()
        print("✓ Connected")
    except Exception as e:
        print(f"✗ Failed: {e}")
        sys.exit(1)

    print("Testing Supabase connection...", end=" ")
    try:
        conn = psycopg2.connect(get_connection_string())
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        print("✓ Connected\n")
    except Exception as e:
        print(f"✗ Failed: {e}")
        sys.exit(1)

    backfill = MetrcHistoricalBackfill()
    end_date = datetime.now()

    backfill.backfill(CULTIVATION_LICENSE, BACKFILL_START, end_date)
    backfill.backfill(PROCESSING_LICENSE, BACKFILL_START, end_date)


if __name__ == "__main__":
    run_backfill()
