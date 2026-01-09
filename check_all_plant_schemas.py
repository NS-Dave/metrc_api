import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cur = conn.cursor()

# Check both tables
for table_name in ['metrc_plants', 'metrc_plant_batches']:
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    
    rows = cur.fetchall()
    if rows:
        print(f"\n{table_name} columns:")
        for row in rows:
            print(f"  {row[0]}: {row[1]}")
    else:
        print(f"\n{table_name}: TABLE NOT FOUND")

cur.close()
conn.close()
