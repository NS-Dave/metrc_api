"""Test if UPDATE statement is actually working."""
from supabase_config import get_connection_string
import psycopg2
import json

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# Simulate what the enrichment script does
transfer_id = 3138613
package_label = '1A40A030000DC51000032203'  # First package from the list

print(f"\n{'='*80}")
print(f"Testing UPDATE for transfer_id={transfer_id}, package_label={package_label}")
print(f"{'='*80}\n")

# Check before
cursor.execute("""
    SELECT product_name, item_name, quantity_shipped 
    FROM metrc_transfer_packages 
    WHERE transfer_id = %s AND package_label = %s
""", (transfer_id, package_label))

before = cursor.fetchone()
print(f"BEFORE UPDATE:")
print(f"  product_name: {before[0]}")
print(f"  item_name: {before[1]}")
print(f"  quantity_shipped: {before[2]}")

# Try update with fake data
update_data = {
    'product_name': 'TEST PRODUCT NAME',
    'item_name': 'TEST ITEM NAME',
    'quantity_shipped': 99.99,
    'transfer_id': transfer_id,
    'package_label': package_label
}

cursor.execute("""
    UPDATE metrc_transfer_packages
    SET 
        product_name = %(product_name)s,
        item_name = %(item_name)s,
        quantity_shipped = %(quantity_shipped)s,
        synced_at = CURRENT_TIMESTAMP
    WHERE transfer_id = %(transfer_id)s 
    AND package_label = %(package_label)s
""", update_data)

rows_affected = cursor.rowcount
print(f"\nUPDATE statement executed: {rows_affected} rows affected")

# Commit
conn.commit()
print("Changes committed")

# Check after
cursor.execute("""
    SELECT product_name, item_name, quantity_shipped 
    FROM metrc_transfer_packages 
    WHERE transfer_id = %s AND package_label = %s
""", (transfer_id, package_label))

after = cursor.fetchone()
print(f"\nAFTER UPDATE:")
print(f"  product_name: {after[0]}")
print(f"  item_name: {after[1]}")
print(f"  quantity_shipped: {after[2]}")

if after[0] == 'TEST PRODUCT NAME':
    print(f"\n✓ UPDATE WORKED! The problem is elsewhere.")
else:
    print(f"\n✗ UPDATE FAILED! Something is wrong with the WHERE clause or commit.")

cursor.close()
conn.close()
