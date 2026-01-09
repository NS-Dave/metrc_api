import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'metrc_plants' 
    ORDER BY ordinal_position
""")

print("metrc_plants columns:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

cur.close()
conn.close()
