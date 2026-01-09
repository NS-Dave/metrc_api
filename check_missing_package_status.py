#!/usr/bin/env python3
"""Check status of synced packages."""

from supabase_config import get_connection_string
import psycopg2

conn = psycopg2.connect(get_connection_string())
cur = conn.cursor()

labels = [
    '1A40A030000C289000031650',
    '1A40A030000C289000031651',
    '1A40A030000C289000031652',
    '1A40A030000C289000031653',
    '1A40A030000C28A000015548',
    '1A40A030000C28A000016570',
    '1A40A030000C28A000016712'
]

cur.execute("""
    SELECT label, finished_date, archived_date 
    FROM metrc_packages 
    WHERE label IN %s
""", (tuple(labels),))

print(f"{'Label':30} {'Finished':20} {'Archived':20} {'Status'}")
print("-" * 90)
for row in cur.fetchall():
    label = row[0]
    finished = str(row[1])[:19] if row[1] else None
    archived = str(row[2])[:19] if row[2] else None
    
    if archived:
        status = "ARCHIVED (inactive)"
    elif finished:
        status = "FINISHED (inactive)"
    else:
        status = "ACTIVE"
    
    print(f"{label:30} {finished or 'None':20} {archived or 'None':20} {status}")

cur.close()
conn.close()
