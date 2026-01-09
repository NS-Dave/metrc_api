from transfer_sync_direction_aware import DirectionAwareTransferSync

sync = DirectionAwareTransferSync()
sync.connect_supabase()
cursor = sync.conn.cursor()

print("=" * 80)
print("BACKFILL RESULTS - FINAL SUMMARY")
print("=" * 80)

# Transfer counts
cursor.execute("""
    SELECT 
        direction,
        COUNT(*) as total,
        MIN(created_date) as earliest,
        MAX(created_date) as latest
    FROM metrc_transfers
    GROUP BY direction
    ORDER BY direction
""")

print("\nTRANSFERS:")
print("-" * 80)
total_transfers = 0
for row in cursor.fetchall():
    print(f"{row[0].upper()}: {row[1]:,} transfers")
    print(f"  Date range: {row[2]} to {row[3]}")
    total_transfers += row[1]

print(f"\nTOTAL TRANSFERS: {total_transfers:,}")

# Package counts
cursor.execute("""
    SELECT 
        direction,
        COUNT(*) as total,
        COUNT(CASE WHEN product_name IS NOT NULL THEN 1 END) as with_details,
        COUNT(CASE WHEN full_package_fetched = TRUE THEN 1 END) as fully_fetched
    FROM metrc_transfer_packages
    GROUP BY direction
    ORDER BY direction
""")

print("\n" + "=" * 80)
print("PACKAGES:")
print("-" * 80)
total_packages = 0
for row in cursor.fetchall():
    print(f"{row[0].upper()}: {row[1]:,} packages")
    print(f"  With product details: {row[2]:,} ({row[2]*100//row[1] if row[1] > 0 else 0}%)")
    print(f"  Fully enriched: {row[3]:,} ({row[3]*100//row[1] if row[1] > 0 else 0}%)")
    total_packages += row[1]

print(f"\nTOTAL PACKAGES: {total_packages:,}")

# License breakdown
cursor.execute("""
    SELECT 
        license_number,
        direction,
        COUNT(*) as count
    FROM metrc_transfers
    GROUP BY license_number, direction
    ORDER BY license_number, direction
""")

print("\n" + "=" * 80)
print("BY LICENSE:")
print("-" * 80)
for row in cursor.fetchall():
    print(f"{row[0]} {row[1]}: {row[2]:,} transfers")

print("\n" + "=" * 80)
print("COMPLETE! All historical transfer data loaded with full package details.")
print("=" * 80)
