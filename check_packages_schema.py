#!/usr/bin/env python3
"""Check metrc_packages schema."""

from supabase_config import get_connection_string
import psycopg2

conn = psycopg2.connect(get_connection_string())
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'metrc_packages' 
    ORDER BY ordinal_position
""")

print("metrc_packages columns:")
print("-" * 60)
for row in cur.fetchall():
    print(f"  {row[0]:40} {row[1]}")

cur.close()
conn.close()
