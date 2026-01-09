"""Quick check to see if new columns are populated"""
import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# Check if new columns have data
cursor.execute("""
    SELECT 
        label,
        item_from_facility_license_number,
        received_datetime,
        is_on_retailer_delivery,
        source_harvest_count,
        location_name,
        product_name
    FROM metrc_packages 
    WHERE license_number = 'MC281599' 
      AND finished_date IS NULL 
      AND archived_date IS NULL
    ORDER BY received_datetime NULLS FIRST, item_from_facility_license_number
    LIMIT 10
""")

rows = cursor.fetchall()

print("\nFirst 10 active packages (in-transit should be at top):\n")
print(f"{'Label':<32} {'From Facility':<12} {'Received':<20} {'OnDeliv':<8} {'Src':<4} Location / Product")
print("-" * 130)

for r in rows:
    label = r[0] or ""
    from_fac = r[1] or "MC281599"  # NULL means created here
    received = str(r[2])[:19] if r[2] else "NOT RECEIVED"
    on_deliv = "Yes" if r[3] else "No"
    src_count = str(r[4]) if r[4] is not None else "?"
    location = r[5] or ""
    product = r[6] or ""
    
    print(f"{label:<32} {from_fac:<12} {received:<20} {on_deliv:<8} {src_count:<4} {location} / {product}")

# Count in-transit vs local
cursor.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE item_from_facility_license_number = 'MP281433' AND received_datetime IS NULL) as in_transit,
        COUNT(*) FILTER (WHERE item_from_facility_license_number IS NULL OR item_from_facility_license_number = 'MC281599' OR received_datetime IS NOT NULL) as local,
        COUNT(*) as total
    FROM metrc_packages 
    WHERE license_number = 'MC281599' 
      AND finished_date IS NULL 
      AND archived_date IS NULL
""")

counts = cursor.fetchone()
print(f"\n{'='*130}")
print(f"SUMMARY: {counts[2]} total active packages")
print(f"  - In-transit from MP281433 (not yet received): {counts[0]}")
print(f"  - Local to MC281599: {counts[1]}")

conn.close()
