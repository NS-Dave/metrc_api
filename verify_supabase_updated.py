from transfer_sync_direction_aware import DirectionAwareTransferSync

sync = DirectionAwareTransferSync()
sync.connect_supabase()
cursor = sync.conn.cursor()

# Check 5 random packages from transfer 3133703 to see if they all have full data
cursor.execute("""
    SELECT 
        package_label,
        product_name,
        item_strain_name,
        quantity_shipped,
        unit_of_measure_name,
        lab_testing_state,
        full_package_fetched
    FROM metrc_transfer_packages 
    WHERE transfer_id = 3133703
    ORDER BY package_label
    LIMIT 10
""")

print("Sample packages from transfer 3133703:")
print("=" * 120)
for row in cursor.fetchall():
    print(f"\n{row[0]}")
    print(f"  Product: {row[1]}")
    print(f"  Strain: {row[2]}")
    print(f"  Quantity: {row[3]} {row[4]}")
    print(f"  Lab Test: {row[5]}")
    print(f"  Full Data: {row[6]}")

# Check stats across all packages
cursor.execute("""
    SELECT 
        direction,
        COUNT(*) as total,
        COUNT(CASE WHEN product_name IS NOT NULL THEN 1 END) as with_product_name,
        COUNT(CASE WHEN quantity_shipped IS NOT NULL THEN 1 END) as with_quantity,
        COUNT(CASE WHEN full_package_fetched = TRUE THEN 1 END) as marked_enriched
    FROM metrc_transfer_packages
    GROUP BY direction
""")

print("\n\n" + "=" * 120)
print("Package data completeness by direction:")
print("=" * 120)
for row in cursor.fetchall():
    print(f"\n{row[0].upper()}:")
    print(f"  Total packages: {row[1]}")
    print(f"  With product name: {row[2]} ({row[2]*100//row[1] if row[1] > 0 else 0}%)")
    print(f"  With quantity: {row[3]} ({row[3]*100//row[1] if row[1] > 0 else 0}%)")
    print(f"  Marked as fully fetched: {row[4]} ({row[4]*100//row[1] if row[1] > 0 else 0}%)")
