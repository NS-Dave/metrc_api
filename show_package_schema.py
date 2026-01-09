from transfer_sync_direction_aware import DirectionAwareTransferSync

sync = DirectionAwareTransferSync()
sync.connect_supabase()
cursor = sync.conn.cursor()

# Get column names
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'metrc_transfer_packages'
    ORDER BY ordinal_position
""")

print("Columns in metrc_transfer_packages:")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

# Check sample data
cursor.execute("""
    SELECT * FROM metrc_transfer_packages 
    WHERE transfer_id = 3133703
    LIMIT 1
""")

print("\n\nSample row from transfer 3133703:")
row = cursor.fetchone()
if row:
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'metrc_transfer_packages'
        ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cursor.fetchall()]
    
    for i, col in enumerate(cols):
        print(f"  {col}: {row[i]}")
