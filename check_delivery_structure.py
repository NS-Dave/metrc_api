#!/usr/bin/env python3
"""Check the structure of Deliveries in transfer JSON."""

import psycopg2
import json
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

cursor.execute("""
    SELECT manifest_number, data
    FROM metrc_transfers
    WHERE data::text LIKE '%Deliveries%'
    LIMIT 1
""")

manifest, data = cursor.fetchone()

print(f"Manifest: {manifest}")
print(f"\nDeliveries structure:")
print(json.dumps(data.get('Deliveries'), indent=2)[:1000])

print(f"\n\nFull transfer keys:")
print(list(data.keys()))
