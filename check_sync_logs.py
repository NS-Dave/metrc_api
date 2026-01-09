#!/usr/bin/env python3
"""Check package sync logs."""

from supabase_config import get_connection_string
import psycopg2

conn = psycopg2.connect(get_connection_string())
cur = conn.cursor()

cur.execute("""
    SELECT sync_start, status, records_pulled, records_inserted, records_updated, error_message 
    FROM metrc_sync_log 
    WHERE entity_type = 'packages' 
    AND sync_start >= '2026-01-05' 
    ORDER BY sync_start DESC
""")

print(f"{'Sync Start':20} {'Status':10} {'Pulled':8} {'Inserted':9} {'Updated':8} {'Error'}")
print("-" * 100)
for row in cur.fetchall():
    print(f"{str(row[0]):20} {row[1]:10} {row[2] or 0:8} {row[3] or 0:9} {row[4] or 0:8} {row[5] or ''}")

cur.close()
conn.close()
