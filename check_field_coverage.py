"""Check how many packages have new fields populated"""
import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# Check coverage of new transfer fields
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE item_from_facility_license_number IS NOT NULL) as has_item_from_facility,
        COUNT(*) FILTER (WHERE received_datetime IS NOT NULL) as has_received_datetime,
        COUNT(*) FILTER (WHERE source_harvest_count IS NOT NULL) as has_source_harvest_count,
        COUNT(*) FILTER (WHERE location_id IS NOT NULL) as has_location_id
    FROM metrc_packages 
    WHERE license_number = 'MC281599' 
      AND finished_date IS NULL 
      AND archived_date IS NULL
""")

row = cursor.fetchone()
total = row[0]
print(f"\nActive Package Field Coverage (MC281599):")
print("=" * 60)
print(f"Total active packages: {total}")
print(f"\nNew field population:")
print(f"  item_from_facility_license_number: {row[1]:4d} ({row[1]/total*100:.1f}%)")
print(f"  received_datetime:                 {row[2]:4d} ({row[2]/total*100:.1f}%)")
print(f"  source_harvest_count:              {row[3]:4d} ({row[3]/total*100:.1f}%)")
print(f"  location_id:                       {row[4]:4d} ({row[4]/total*100:.1f}%)")

# Show some NULL examples
print(f"\n{'-'*60}")
print("Sample packages WITHOUT new fields populated:")
cursor.execute("""
    SELECT label, packaged_date, product_name
    FROM metrc_packages 
    WHERE license_number = 'MC281599' 
      AND finished_date IS NULL 
      AND archived_date IS NULL
      AND item_from_facility_license_number IS NULL
      AND source_harvest_count IS NULL
    ORDER BY packaged_date DESC
    LIMIT 5
""")

for label, packaged, product in cursor.fetchall():
    print(f"  {label} - {packaged} - {product}")

conn.close()
