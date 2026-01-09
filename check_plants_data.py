import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cur = conn.cursor()

# Group by phase
cur.execute("""
    SELECT 
        license_number,
        growth_phase,
        COUNT(*) as count
    FROM metrc_plants 
    GROUP BY license_number, growth_phase 
    ORDER BY license_number, growth_phase
""")

print("Plants by phase:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} = {row[2]}")

# Total count
cur.execute("SELECT COUNT(*) FROM metrc_plants")
print(f"\nTotal plants: {cur.fetchone()[0]}")

cur.close()
conn.close()
