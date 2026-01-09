"""Check package_status field population"""
import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

# Check status distribution
cursor.execute("""
    SELECT 
        package_status,
        COUNT(*) as count,
        COUNT(*) FILTER (WHERE finished_date IS NULL AND archived_date IS NULL) as active_unfinished
    FROM metrc_packages 
    WHERE license_number = 'MC281599'
    GROUP BY package_status
    ORDER BY package_status
""")

print("\nPackage Status Distribution (MC281599):")
print("=" * 70)
print(f"{'Status':<15} {'Total':<10} {'Active (Unfinished)':<20}")
print("-" * 70)

total = 0
total_active = 0
for status, count, active in cursor.fetchall():
    status_display = status or "(NULL)"
    print(f"{status_display:<15} {count:<10} {active:<20}")
    total += count
    total_active += active

print("-" * 70)
print(f"{'TOTAL':<15} {total:<10} {total_active:<20}")

# Show sample intransit packages (if any)
cursor.execute("""
    SELECT label, item_from_facility_license_number, received_datetime, location_name
    FROM metrc_packages 
    WHERE license_number = 'MC281599' 
      AND package_status = 'intransit'
    LIMIT 5
""")

intransit = cursor.fetchall()
if intransit:
    print(f"\n{'-'*70}")
    print("Sample In-Transit Packages:")
    for label, from_fac, received, location in intransit:
        print(f"  {label} - From: {from_fac}, Received: {received}, Location: {location}")
else:
    print(f"\n{'-'*70}")
    print("No packages currently marked as 'intransit'")

# Check for packages that should be intransit based on fields
cursor.execute("""
    SELECT 
        COUNT(*) as potential_intransit
    FROM metrc_packages 
    WHERE license_number = 'MC281599' 
      AND item_from_facility_license_number = 'MP281433'
      AND received_datetime IS NULL
      AND finished_date IS NULL
      AND archived_date IS NULL
""")

potential = cursor.fetchone()[0]
if potential > 0:
    print(f"\nNote: {potential} packages match in-transit criteria but may be marked 'active'")
    print("      (item_from_facility = MP281433, received_datetime = NULL)")

conn.close()
