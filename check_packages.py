from transfer_sync_direction_aware import DirectionAwareTransferSync

sync = DirectionAwareTransferSync()
sync.connect_supabase()
cursor = sync.conn.cursor()

cursor.execute("SELECT direction, COUNT(*) FROM metrc_transfer_packages GROUP BY direction")
print("Packages by direction:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

cursor.execute("""
    SELECT transfer_id, direction, COUNT(*) 
    FROM metrc_transfer_packages 
    GROUP BY transfer_id, direction
    ORDER BY transfer_id, direction
    LIMIT 10
""")
print("\nFirst 10 transfer_id + direction combinations:")
for row in cursor.fetchall():
    print(f"  Transfer {row[0]} ({row[1]}): {row[2]} packages")
