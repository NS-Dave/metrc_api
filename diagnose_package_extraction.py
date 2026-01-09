#!/usr/bin/env python3
"""Diagnose why package columns are NULL."""

import psycopg2
import json
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        package_id,
        package_label,
        wholesale_price,
        shipper_wholesale_price,
        receiver_wholesale_price,
        data
    FROM metrc_transfer_packages
    LIMIT 5
""")

print("Sample rows from metrc_transfer_packages:\n")
for row in cursor.fetchall():
    pkg_id, pkg_label, wp, swp, rwp, data = row
    print(f"Package ID (column): {pkg_id}")
    print(f"Package Label (column): {pkg_label}")
    print(f"Wholesale Price (column): {wp}")
    print(f"Shipper Wholesale (column): {swp}")
    print(f"Receiver Wholesale (column): {rwp}")
    
    if data:
        parsed = json.loads(data) if isinstance(data, str) else data
        print(f"\nData from JSON:")
        print(f"  PackageId: {parsed.get('PackageId')}")
        print(f"  PackageLabel: {parsed.get('PackageLabel')}")
        print(f"  ShipperWholesalePrice: {parsed.get('ShipperWholesalePrice')}")
        print(f"  ReceiverWholesalePrice: {parsed.get('ReceiverWholesalePrice')}")
        print(f"  WholesalePrice: {parsed.get('WholesalePrice')}")
        print(f"\nAll keys in JSON: {list(parsed.keys())}")
    
    print("\n" + "="*80 + "\n")
