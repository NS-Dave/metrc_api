"""Check if UPDATE WHERE clause is matching correctly."""
from supabase_config import get_connection_string
import psycopg2
from psycopg2.extras import DictCursor

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor(cursor_factory=DictCursor)

# Get the transfer the user looked up
cursor.execute("""
    SELECT t.id, t.manifest_number, tp.package_label, tp.product_name, tp.item_name 
    FROM metrc_transfers t
    JOIN metrc_transfer_packages tp ON tp.transfer_id = t.id
    WHERE t.manifest_number = %s
    LIMIT 10
""", ('0003138613',))

packages = cursor.fetchall()
print(f"\n{'='*80}")
print(f"Database state for manifest 0003138613:")
print(f"{'='*80}")

if packages:
    first = packages[0]
    print(f"\nDatabase transfer_id: {first['id']}")
    print(f"Manifest number: {first['manifest_number']}")
    print(f"\nPackage samples:")
    for pkg in packages[:5]:
        print(f"  - Label: {pkg['package_label']}, Product: {pkg['product_name']}, Item: {pkg['item_name']}")
else:
    print("No packages found!")

# Now check what the enrichment script would match
cursor.execute("""
    SELECT DISTINCT
        t.id as transfer_id,
        t.manifest_number,
        (SELECT COUNT(*) FROM metrc_transfer_packages tp2 WHERE tp2.transfer_id = t.id) as package_count
    FROM metrc_transfers t
    INNER JOIN metrc_transfer_packages tp ON tp.transfer_id = t.id
    WHERE t.manifest_number = %s
    AND tp.product_name IS NULL
""", ('0003138613',))

match = cursor.fetchone()
if match:
    print(f"\n{'='*80}")
    print(f"Enrichment script would match:")
    print(f"{'='*80}")
    print(f"Transfer ID: {match['transfer_id']}")
    print(f"Manifest: {match['manifest_number']}")
    print(f"Package count: {match['package_count']}")
else:
    print(f"\n{'='*80}")
    print(f"NO MATCH - enrichment script would NOT select this transfer")
    print(f"Reason: product_name is already populated (not NULL)")
    print(f"{'='*80}")

cursor.close()
conn.close()
