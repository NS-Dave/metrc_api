from transfer_sync_direction_aware import DirectionAwareTransferSync

sync = DirectionAwareTransferSync()
sync.connect_supabase()
cursor = sync.conn.cursor()

# Check what data we have for packages from transfer 3133703
cursor.execute("""
    SELECT 
        package_id,
        package_label,
        wholesale_price,
        shipper_wholesale_price,
        receiver_wholesale_price,
        full_package_fetched,
        product_name,
        item_strain_name,
        quantity,
        unit_of_measure_name
    FROM metrc_transfer_packages 
    WHERE transfer_id = 3133703
    ORDER BY package_label
    LIMIT 5
""")

print("First 5 packages from transfer 3133703:")
print("=" * 120)
for row in cursor.fetchall():
    print(f"\nPackage ID: {row[0]}")
    print(f"  Label: {row[1]}")
    print(f"  Wholesale Price: {row[2]}")
    print(f"  Shipper Wholesale: {row[3]}")
    print(f"  Receiver Wholesale: {row[4]}")
    print(f"  Full Data Fetched: {row[5]}")
    print(f"  Product Name: {row[6]}")
    print(f"  Strain: {row[7]}")
    print(f"  Quantity: {row[8]} {row[9]}")

# Check enrichment stats
cursor.execute("""
    SELECT 
        direction,
        COUNT(*) as total,
        COUNT(CASE WHEN full_package_fetched = TRUE THEN 1 END) as enriched,
        COUNT(CASE WHEN full_package_fetched = FALSE OR full_package_fetched IS NULL THEN 1 END) as not_enriched
    FROM metrc_transfer_packages
    GROUP BY direction
""")

print("\n\n" + "=" * 120)
print("Enrichment status by direction:")
print("=" * 120)
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]} total, {row[2]} enriched ({row[2]*100//row[1] if row[1] > 0 else 0}%), {row[3]} not enriched")
