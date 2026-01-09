import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cur = conn.cursor()

cur.execute("""
    SELECT constraint_name, constraint_type 
    FROM information_schema.table_constraints 
    WHERE table_name = %s
""", ('metrc_plant_batches',))

print("Constraints on metrc_plant_batches:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Get unique constraints details
cur.execute("""
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.table_name = %s 
        AND tc.constraint_type = 'UNIQUE'
    ORDER BY kcu.ordinal_position
""", ('metrc_plant_batches',))

print("\nUnique constraint columns:")
for row in cur.fetchall():
    print(f"  {row[0]}")

# Get primary key
cur.execute("""
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.table_name = %s 
        AND tc.constraint_type = 'PRIMARY KEY'
    ORDER BY kcu.ordinal_position
""", ('metrc_plant_batches',))

print("\nPrimary key columns:")
for row in cur.fetchall():
    print(f"  {row[0]}")

conn.close()
