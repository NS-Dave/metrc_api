#!/usr/bin/env python3
"""
Backfill missing Deliveries for metrc_transfers.

Finds transfer records whose stored JSON lacks Deliveries and fetches delivery
details from Metrc per transfer, updating metrc_transfers in-place.
"""

import json
import sys
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

from config import MetrcConfig
from client import MetrcClient
from processing import ProcessingClient
from supabase_config import get_connection_string


def fetch_transfers_with_delivery_ids(conn) -> List[Dict[str, Any]]:
    """Return transfers that have DeliveryId in data but missing Deliveries array."""
    sql = """
        SELECT id, license_number, data
        FROM metrc_transfers
        WHERE
            (data -> 'DeliveryId') IS NOT NULL
            AND (
                (data -> 'Deliveries') IS NULL
                OR jsonb_typeof(data -> 'Deliveries') = 'null'
            )
        LIMIT 500
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def normalize_deliveries(detail: Any) -> Optional[List[Dict[str, Any]]]:
    """Normalize delivery detail responses into a list of deliveries."""
    deliveries = None
    if isinstance(detail, dict):
        deliveries = detail.get('Deliveries') or detail.get('Delivery')
        if deliveries is None and {'RecipientFacilityName', 'Packages'} <= set(detail.keys()):
            deliveries = [detail]
    elif isinstance(detail, list):
        deliveries = detail
    return deliveries if deliveries else None


def update_transfer_delivery(conn, transfer_id: int, license_number: str, transfer_data: Dict[str, Any], delivery_detail: Dict[str, Any]):
    """Update metrc_transfers row with fetched delivery detail."""
    # Create Deliveries array if it doesn't exist
    if not isinstance(transfer_data.get('Deliveries'), list):
        transfer_data['Deliveries'] = []
    
    # Add the delivery detail as the first (and usually only) delivery
    transfer_data['Deliveries'] = [delivery_detail]

    sql = """
        UPDATE metrc_transfers
        SET data = %s
        WHERE id = %s AND license_number = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (json.dumps(transfer_data), transfer_id, license_number))


def main():
    print("\n=== Fill Transfer Delivery Packages ===")

    # Load environment variables from .env if present
    load_dotenv()

    cfg = MetrcConfig.from_env()
    client = MetrcClient(cfg)
    processing = ProcessingClient(client)

    conn = psycopg2.connect(get_connection_string())

    transfers = fetch_transfers_with_delivery_ids(conn)
    print(f"Transfers with DeliveryId but no Deliveries array: {len(transfers)}")

    updated = 0
    skipped = 0
    failed = 0

    for row in transfers:
        transfer_id = row['id']
        license_number = row['license_number']
        data = row['data'] or {}
        delivery_id = data.get('DeliveryId')

        if not delivery_id:
            skipped += 1
            continue
        
        try:
            detail = processing.get_transfer_delivery(delivery_id, license_number=license_number)
            
            if not detail:
                skipped += 1
                continue

            update_transfer_delivery(conn, transfer_id, license_number, data, detail)
            updated += 1
        except Exception as e:
            failed += 1
            print(f"✗ Transfer {transfer_id} / Delivery {delivery_id} ({license_number}) failed: {e}")

    conn.commit()
    conn.close()

    print(f"Done. Updated: {updated}, Skipped: {skipped}, Failed: {failed}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
