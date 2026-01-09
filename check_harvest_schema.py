#!/usr/bin/env python3
"""Quick script to check actual metrc_harvests schema in Supabase."""

import psycopg2
from psycopg2.extras import DictCursor
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor(cursor_factory=DictCursor)

# Get actual column names from metrc_harvests
cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'metrc_harvests' 
    ORDER BY ordinal_position
""")

print("metrc_harvests columns:")
print("-" * 60)
for row in cursor.fetchall():
    print(f"  {row['column_name']:<30} {row['data_type']}")

cursor.close()
conn.close()
