#!/usr/bin/env python3
"""Verify if schema columns exist."""

import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# Check if new columns exist
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'metrc_transfer_packages'
    ORDER BY ordinal_position
""")

columns = [row[0] for row in cursor.fetchall()]

print("Columns in metrc_transfer_packages:")
for col in columns:
    print(f"  - {col}")

print(f"\nTotal columns: {len(columns)}")

expected_new_columns = [
    'item_unit_cbd_content_unit_of_measure_name',
    'product_name',
    'item_name',
    'quantity_shipped'
]

print(f"\nChecking for expected new columns:")
for col in expected_new_columns:
    exists = col in columns
    print(f"  - {col}: {'✓' if exists else '✗ MISSING'}")
