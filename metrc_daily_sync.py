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
from supabase_config import get_connection_string, get_connection
from package_history import capture_history_before_update, create_initial_history_entry

# License configuration
CULTIVATION_LICENSE = os.getenv('METRC_LICENSE_CULTIVATION', 'MC281599')
PROCESSING_LICENSE = os.getenv('METRC_LICENSE_PROCESSING', 'MP281433')


class MetrcSupabaseSync:
    """Handles syncing Metrc data to Supabase."""
    
    def __init__(self, password: Optional[str] = None, dry_run: bool = False,
                 limit: Optional[int] = None):
        """Initialize sync with Metrc and Supabase connections.

        Args:
            dry_run: If True, all entity upserts are rolled back instead of committed
                     (only metrc_sync_log audit rows persist). Use to preview safely.
            limit:   If set, only the first N rows per entity are processed (test scoping).
        """
        # Metrc API clients
        config = MetrcConfig.from_env()
        self.metrc_client = MetrcClient(config)
        self.cultivation = CultivationClient(self.metrc_client)
        self.processing = ProcessingClient(self.metrc_client)

        # Supabase connection
        self.conn_string = get_connection_string(password)
        self.conn = None

        # NSOS schema support
        self.dry_run = dry_run
        self.limit = limit
        self._conn_id_cache: Dict[str, str] = {}
        
    def connect_supabase(self):
        """Connect to Supabase database with schema-aware search_path."""
        if self.conn is None or self.conn.closed:
            self.conn = get_connection()
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
    
    # ── NSOS schema helpers ──────────────────────────────────────────────────
    def resolve_connection_id(self, license_number: str) -> str:
        """Map a METRC license number to its NSOS metrcConnectionId (uuid)."""
        if license_number in self._conn_id_cache:
            return self._conn_id_cache[license_number]
        self.connect_supabase()
        cur = self.conn.cursor()
        cur.execute(
            'SELECT id FROM metrc_connections '
            'WHERE "licenseNumber" = %s AND "deletedAt" IS NULL',
            (license_number,),
        )
        row = cur.fetchone()
        cur.close()
        self.conn.commit()
        if not row:
            raise ValueError(
                f"No metrc_connections row for license {license_number}; "
                "cannot map to a metrcConnectionId."
            )
        self._conn_id_cache[license_number] = row[0]
        return row[0]

    def _finish(self):
        """Commit, or roll back entity writes when in dry-run mode."""
        if self.dry_run:
            self.conn.rollback()
        else:
            self.conn.commit()

    def _upsert_entity(self, table: str, key_col: str, conn_id: str, fields: Dict) -> str:
        """Insert or update one NSOS row, keyed on the table's UNIQUE business key
        (metrcConnectionId, <key_col>) — packageLabel / harvestName / plantLabel /
        batchName / manifestNumber. Uses INSERT ... ON CONFLICT so a record that
        reappears under a different metric id (e.g. a package seen via a transfer
        endpoint carries a different PackageId than it did as an active package)
        updates the existing row instead of colliding on the unique constraint.

        The uuid `id` PK defaults server-side; createdAt is set once on insert;
        updatedAt/lastSyncedAt are stamped every time. Identity columns (metric*) and
        the conflict key are never overwritten on update, so the authoritative id is
        preserved. Returns 'inserted' or 'updated'.
        """
        # Drop None values so column defaults apply (NSOS marks many columns NOT NULL
        # with a default); never force a NULL into a defaulted NOT-NULL column.
        fields = {k: v for k, v in fields.items() if v is not None}
        fields['metrcConnectionId'] = conn_id
        now = datetime.now()

        ins_cols = list(fields.keys()) + ['createdAt', 'updatedAt', 'lastSyncedAt']
        ins_vals = list(fields.values()) + [now, now, now]
        col_list = ', '.join(f'"{c}"' for c in ins_cols)
        placeholders = ', '.join(['%s'] * len(ins_cols))

        # On conflict, refresh data columns only — never the identity columns (metric*),
        # the conflict key, or createdAt.
        upd_cols = [c for c in fields if not c.startswith('metrc') and c != key_col]
        upd_cols += ['updatedAt', 'lastSyncedAt']
        set_clause = ', '.join(f'"{c}" = EXCLUDED."{c}"' for c in upd_cols)

        sql = (f'INSERT INTO {table} ({col_list}) VALUES ({placeholders}) '
               f'ON CONFLICT ("metrcConnectionId", "{key_col}") DO UPDATE SET {set_clause} '
               f'RETURNING (xmax = 0) AS inserted')
        cur = self.conn.cursor()
        cur.execute(sql, ins_vals)
        inserted = cur.fetchone()[0]
        cur.close()
        return 'inserted' if inserted else 'updated'

    def _upsert_many(self, table: str, key_col: str, license_number: str,
                     items: List[Dict], mapper) -> tuple:
        """Map and upsert a batch of METRC API dicts into an NSOS table, keyed on the
        table's unique business column (key_col). Rows missing that key are skipped."""
        if not items:
            return (0, 0)
        self.connect_supabase()
        conn_id = self.resolve_connection_id(license_number)
        if self.limit:
            items = items[:self.limit]
        inserted = updated = 0
        for item in items:
            fields = mapper(item)
            if not fields.get(key_col):
                continue
            if self._upsert_entity(table, key_col, conn_id, fields) == 'inserted':
                inserted += 1
            else:
                updated += 1
        self._finish()
        return (inserted, updated)

    # ── METRC API → NSOS column mappers ──────────────────────────────────────
    @staticmethod
    def _as_array(v):
        """Coerce a METRC value into a Python list for a Postgres text[] column.

        METRC returns these fields as a comma-separated string (or a single value);
        Postgres array columns need a list (or None).
        """
        if v is None:
            return None
        if isinstance(v, list):
            return v or None
        if isinstance(v, str):
            parts = [s.strip() for s in v.split(',') if s.strip()]
            return parts or None
        return [str(v)]

    @staticmethod
    def _map_harvest(h: Dict) -> Dict:
        return {
            'metrcHarvestId': h.get('Id'),
            'harvestName': h.get('Name'),
            'harvestType': h.get('HarvestType'),
            'currentWeight': h.get('CurrentWeight'),
            'unitOfWeight': h.get('UnitOfWeightName') or 'Grams',
            'isFinished': h.get('IsFinished', False),
            'strainName': h.get('SourceStrainNames'),
            'dryingLocationName': h.get('DryingLocationName'),
            'harvestStartDate': h.get('HarvestStartDate'),
            'finishedDate': h.get('FinishedDate'),
            'lastModifiedAt': h.get('LastModified'),
            'totalWasteWeight': h.get('TotalWasteWeight'),
            'totalWetWeight': h.get('TotalWetWeight'),
            'totalRestorativeWasteWeight': h.get('TotalRestorativeWasteWeight'),
        }

    @staticmethod
    def _map_package(p: Dict, status: str = 'active') -> Dict:
        item = p.get('Item') if isinstance(p.get('Item'), dict) else {}
        state_map = {'active': 'Active', 'inactive': 'Inactive',
                     'intransit': 'Active', 'transferred': 'Inactive'}
        return {
            'metrcPackageId': p.get('Id') or p.get('PackageId'),
            'packageLabel': p.get('Label') or p.get('PackageLabel'),
            'packageType': p.get('PackageType'),
            'packageState': p.get('PackageState') or state_map.get(status, 'Active'),
            'itemName': (item.get('Name') if item else None) or p.get('ItemName') or p.get('ProductName'),
            'itemCategory': (item.get('ProductCategoryName') if item else None) or p.get('ProductCategoryName'),
            'productCategoryName': (item.get('ProductCategoryName') if item else None) or p.get('ProductCategoryName'),
            'quantity': p.get('Quantity'),
            'unitOfMeasure': p.get('UnitOfMeasureName'),
            'initialQuantity': p.get('OriginalPackageQuantity'),
            'locationName': p.get('LocationName'),
            'packagedDate': p.get('PackagedDate'),
            'receivedDate': p.get('ReceivedDateTime'),
            'finishedDate': p.get('FinishedDate'),
            'lastModifiedAt': p.get('LastModified'),
            'sourceHarvestNames': MetrcSupabaseSync._as_array(p.get('SourceHarvestNames')),
            'sourcePackageLabels': MetrcSupabaseSync._as_array(p.get('SourcePackageLabels')),
            'labTestingState': p.get('LabTestingState'),
            'isTestingSample': p.get('IsTestingSample', False),
            'isTradeSample': p.get('IsTradeSample', False),
            'note': p.get('Note'),
            'isOnHold': p.get('IsOnHold', False),
            'isProductionBatch': p.get('IsProductionBatch', False),
            'productionBatchNumber': p.get('ProductionBatchNumber'),
            'isDonation': p.get('IsDonation', False),
        }

    @staticmethod
    def _map_plant(p: Dict) -> Dict:
        return {
            'metrcPlantId': p.get('Id'),
            'plantLabel': p.get('Label'),
            'plantState': p.get('State'),
            'growthPhase': p.get('GrowthPhase'),
            'strainName': p.get('StrainName'),
            'locationName': p.get('LocationName'),
            'plantedDate': p.get('PlantedDate'),
            'vegetativeDate': p.get('VegetativeDate'),
            'floweringDate': p.get('FloweringDate'),
            'harvestedDate': p.get('HarvestedDate'),
            'destroyedDate': p.get('DestroyedDate'),
            'lastModifiedAt': p.get('LastModified'),
            'plantBatchName': p.get('PlantBatchName'),
            'isOnHold': p.get('IsOnHold', False),
        }

    @staticmethod
    def _map_plant_batch(b: Dict) -> Dict:
        return {
            'metrcBatchId': b.get('Id'),
            'batchName': b.get('Name'),
            'batchType': b.get('Type'),
            'count': b.get('Count') or 0,
            'destroyedCount': b.get('DestroyedCount'),
            'strainName': b.get('StrainName'),
            'locationName': b.get('LocationName'),
            'plantedDate': b.get('PlantedDate'),
            'lastModifiedAt': b.get('LastModified'),
        }

    @staticmethod
    def _map_transfer(t: Dict) -> Dict:
        deliveries = t.get('Deliveries', []) or []
        recipient_name = t.get('RecipientFacilityName')
        recipient_license = t.get('RecipientFacilityLicenseNumber')
        if not recipient_name and deliveries:
            recipient_name = deliveries[0].get('RecipientFacilityName')
        if not recipient_license and deliveries:
            recipient_license = deliveries[0].get('RecipientFacilityLicenseNumber')
        shipper_license = t.get('ShipperFacilityLicenseNumber')
        company_licenses = {'MC281599', 'MP281433', 'MR283288', 'MR284733', 'MR281800'}
        is_intercompany = shipper_license in company_licenses and recipient_license in company_licenses
        return {
            'metrcTransferId': t.get('Id'),
            'manifestNumber': t.get('ManifestNumber'),
            'transferType': 'intercompany' if is_intercompany else '3rd party',
            'shipmentTypeName': t.get('ShipmentTypeName'),
            'shipperFacilityLicenseNumber': shipper_license,
            'shipperFacilityName': t.get('ShipperFacilityName'),
            'destinationFacilityLicenseNumber': recipient_license,
            'destinationFacilityName': recipient_name,
            'transporterFacilityLicenseNumber': t.get('TransporterFacilityLicenseNumber'),
            'transporterFacilityName': t.get('TransporterFacilityName'),
            'transferState': t.get('_direction'),
            'createdDate': t.get('CreatedDateTime'),
            'shippedDate': t.get('ActualDepartureDateTime'),
            'estimatedDepartureDate': t.get('EstimatedDepartureDateTime'),
            'estimatedArrivalDate': t.get('EstimatedArrivalDateTime'),
            'receivedDate': t.get('ActualArrivalDateTime'),
            'lastModifiedAt': t.get('LastModified'),
            'packageCount': t.get('PackageCount'),
            'isOnHold': t.get('IsOnHold', False),
            'containsPlantPackage': t.get('ContainsPlantPackage', False),
            'containsProductPackage': t.get('ContainsProductPackage', False),
        }

    # ── Entity upserts (NSOS schema, connection-scoped) ──────────────────────
    def upsert_harvests(self, harvests: List[Dict], license_number: str) -> tuple:
        """Upsert harvests to metrc_harvests (NSOS schema). Returns (inserted, updated)."""
        return self._upsert_many('metrc_harvests', 'harvestName',
                                 license_number, harvests, self._map_harvest)
    
    def upsert_packages(self, packages: List[Dict], license_number: str, status: str = 'active') -> tuple:
        """Upsert packages to metrc_packages (NSOS schema). Returns (inserted, updated).

        `status` is the endpoint the packages came from (active/inactive/intransit/
        transferred); it supplies packageState when the API payload omits it.
        """
        return self._upsert_many('metrc_packages', 'packageLabel', license_number,
                                 packages, lambda p: self._map_package(p, status))


    # --------------------------- transfer enrichment ---------------------------
    def enrich_transfers_with_deliveries(self, transfers: List[Dict], license_number: str) -> List[Dict]:
        """Pass-through under the NSOS schema.

        Delivery-package / transporter enrichment is disabled: the
        metrc_transfer_transporters table was dropped in the NSOS migration and
        delivery-package enrichment is out of scope for this rebuild. Transfers
        still sync via upsert_transfers; this just returns them unchanged.
        """
        return transfers

    
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
            
            print(f"  [OK] Inserted {inserted}, Updated {updated}")

            self.log_sync_end(sync_id, len(all_harvests), inserted, updated)

        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            # Rollback the failed transaction before trying to log
            if self.conn and not self.conn.closed:
                self.conn.rollback()
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
                intransit_response = self.processing.get_packages('intransit', license_number=license_number)
                intransit_packages = intransit_response if isinstance(intransit_response, list) else []
            except Exception as e:
                print(f"  Note: Could not fetch intransit packages: {e}")
                intransit_packages = []
            
            # Get transferred packages (packages that have been sent out)
            try:
                transferred_response = self.processing.get_packages('transferred', license_number=license_number)
                transferred_packages = transferred_response if isinstance(transferred_response, list) else []
            except Exception as e:
                print(f"  Note: Could not fetch transferred packages: {e}")
                transferred_packages = []
            
            print(f"  Found {len(active_packages)} active, {len(inactive_packages)} inactive, {len(intransit_packages)} intransit, {len(transferred_packages)} transferred = {len(active_packages) + len(inactive_packages) + len(intransit_packages) + len(transferred_packages)} total")
            
            # Upsert to Supabase with status tracking
            inserted_active, updated_active = self.upsert_packages(active_packages, license_number, status='active')
            inserted_inactive, updated_inactive = self.upsert_packages(inactive_packages, license_number, status='inactive')
            inserted_intransit, updated_intransit = self.upsert_packages(intransit_packages, license_number, status='intransit')
            inserted_transferred, updated_transferred = self.upsert_packages(transferred_packages, license_number, status='transferred')
            
            total_inserted = inserted_active + inserted_inactive + inserted_intransit + inserted_transferred
            total_updated = updated_active + updated_inactive + updated_intransit + updated_transferred
            
            print(f"  [OK] Inserted {total_inserted}, Updated {total_updated}")

            self.log_sync_end(sync_id, len(active_packages) + len(inactive_packages) + len(intransit_packages) + len(transferred_packages), total_inserted, total_updated)

        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            # Rollback the failed transaction before trying to log
            if self.conn and not self.conn.closed:
                self.conn.rollback()
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
            
            print(f"  [OK] Inserted {inserted}, Updated {updated}")

            self.log_sync_end(sync_id, len(unique_transfers), inserted, updated)

        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            # Rollback the failed transaction before trying to log
            if self.conn and not self.conn.closed:
                self.conn.rollback()
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
                print(f"  [OK] Plants: {inserted} inserted, {updated} updated")
            
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
                print(f"  [OK] Plant Batches: {inserted} inserted, {updated} updated")
            
            self.log_sync_end(sync_id, total_plants + total_batches, 0, 0)
            
        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            # Rollback the failed transaction before trying to log
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            self.log_sync_end(sync_id, 0, 0, 0, 'failed', str(e))
            raise
    
    def upsert_plants(self, plants: List[Dict], license_number: str) -> tuple:
        """Upsert plants to metrc_plants (NSOS schema). Returns (inserted, updated)."""
        return self._upsert_many('metrc_plants', 'plantLabel',
                                 license_number, plants, self._map_plant)

    
    def upsert_plant_batches(self, batches: List[Dict], license_number: str) -> tuple:
        """Upsert plant batches to metrc_plant_batches (NSOS schema). Returns (inserted, updated)."""
        return self._upsert_many('metrc_plant_batches', 'batchName',
                                 license_number, batches, self._map_plant_batch)

    
    def upsert_transfers(self, transfers: List[Dict], license_number: str) -> tuple:
        """Upsert transfers to metrc_transfers (NSOS schema). Returns (inserted, updated)."""
        return self._upsert_many('metrc_transfers', 'manifestNumber',
                                 license_number, transfers, self._map_transfer)


def run_daily_sync(dry_run: bool = False, limit: Optional[int] = None,
                   licenses: Optional[List[str]] = None):
    """Run daily incremental sync for cultivation and/or processing licenses.

    Args:
        dry_run:  Preview only — entity writes are rolled back (NSOS tables untouched).
        limit:    Cap rows processed per entity (test scoping).
        licenses: Restrict to these license numbers; default is both.
    """
    run_set = set(licenses) if licenses else {CULTIVATION_LICENSE, PROCESSING_LICENSE}

    print("=" * 70)
    print("METRC DAILY INCREMENTAL SYNC" + ("  [DRY RUN]" if dry_run else ""))
    print(f"Timestamp: {datetime.now().isoformat()}")
    if limit:
        print(f"Row limit per entity: {limit}")
    print(f"Licenses: {', '.join(sorted(run_set))}")
    print("=" * 70)
    print()

    syncer = MetrcSupabaseSync(dry_run=dry_run, limit=limit)

    try:
        # Test Metrc connection
        print("Testing Metrc API connection...")
        if not syncer.metrc_client.test_connection():
            raise Exception("Failed to connect to Metrc API")
        print("[OK] Metrc API connected")
        print()

        # Test Supabase connection
        print("Testing Supabase connection...")
        syncer.connect_supabase()
        print("[OK] Supabase connected")
        print()

        if CULTIVATION_LICENSE in run_set:
            print(f"CULTIVATION LICENSE: {CULTIVATION_LICENSE}")
            print("-" * 70)
            syncer.sync_harvests_incremental(CULTIVATION_LICENSE, hours=48)
            syncer.sync_packages_incremental(CULTIVATION_LICENSE, hours=48)
            syncer.sync_transfers_incremental(CULTIVATION_LICENSE, days=7)
            syncer.sync_plants(CULTIVATION_LICENSE)
            print()

        if PROCESSING_LICENSE in run_set:
            print(f"PROCESSING LICENSE: {PROCESSING_LICENSE}")
            print("-" * 70)
            syncer.sync_packages_incremental(PROCESSING_LICENSE, hours=48)
            syncer.sync_transfers_incremental(PROCESSING_LICENSE, days=7)
            syncer.sync_plants(PROCESSING_LICENSE)  # Will skip if no cultivation access
            print()

        print("=" * 70)
        if dry_run:
            print("[DRY RUN COMPLETE] no entity rows committed")
        else:
            print("[SUCCESS] DAILY SYNC COMPLETED SUCCESSFULLY")
        print("=" * 70)

    except Exception as e:
        print()
        print("=" * 70)
        print(f"[ERROR] SYNC FAILED: {e}")
        print("=" * 70)
        raise

    finally:
        syncer.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="METRC daily incremental sync (NSOS schema)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview: roll back all entity writes (NSOS tables untouched)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max rows processed per entity (test scoping)")
    parser.add_argument("--license", action="append", dest="licenses", default=None,
                        help="Restrict to a license number (repeatable); default runs both")
    args = parser.parse_args()
    run_daily_sync(dry_run=args.dry_run, limit=args.limit, licenses=args.licenses)
