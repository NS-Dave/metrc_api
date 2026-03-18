"""
Initialize package history tracking system.

This creates the history table and captures current state as baseline.
"""
import psycopg2
from supabase_config import get_connection_string

print("="*70)
print("PACKAGE HISTORY SYSTEM - INITIALIZATION")
print("="*70)

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

print("\nReading migration SQL...")
with open('schema_package_history.sql', 'r') as f:
    migration_sql = f.read()

try:
    print("Creating history table and functions...")
    cursor.execute(migration_sql)
    conn.commit()
    
    print("\n✓ Migration completed successfully!")
    
    # Verify
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)
    
    # Check table exists
    cursor.execute("""
        SELECT COUNT(*) FROM metrc_packages_history
    """)
    history_count = cursor.fetchone()[0]
    print(f"\n✓ History table created with {history_count:,} initial snapshots")
    
    # Check views
    cursor.execute("""
        SELECT table_name FROM information_schema.views
        WHERE table_name IN ('package_state_transitions', 'package_significant_changes', 'packages_current_from_history')
        ORDER BY table_name
    """)
    
    print("\n✓ Views created:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}")
    
    # Check functions
    cursor.execute("""
        SELECT routine_name FROM information_schema.routines
        WHERE routine_name IN ('get_package_at_time', 'get_package_timeline')
        ORDER BY routine_name
    """)
    
    print("\n✓ Functions created:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}()")
    
    # Sample timeline
    print("\n" + "="*70)
    print("TESTING - Get timeline for a sample package")
    print("="*70)
    
    cursor.execute("""
        SELECT label FROM metrc_packages 
        WHERE license_number = 'MC281599'
        LIMIT 1
    """)
    sample_label = cursor.fetchone()[0]
    
    print(f"\nSample package: {sample_label}")
    
    cursor.execute("""
        SELECT * FROM get_package_timeline(%s)
    """, (sample_label,))
    
    timeline = cursor.fetchall()
    if timeline:
        print(f"\nTimeline entries: {len(timeline)}")
        for row in timeline[:3]:  # Show first 3
            change_time, change_type, changed_fields, quantity, is_finished, is_archived, endpoint = row
            print(f"  {change_time}: {change_type} - Qty: {quantity}, Finished: {is_finished}")
    else:
        print("  (No timeline entries yet - run a sync to capture changes)")
    
    print("\n" + "="*70)
    print("SUCCESS - Package history system is ready!")
    print("="*70)
    print("""
Next steps:
1. Run daily sync to start capturing changes
2. Try example queries from PACKAGE_HISTORY_GUIDE.md
3. Build dashboards to visualize package journeys

Key queries:
  • SELECT * FROM get_package_timeline('LABEL');
  • SELECT * FROM get_package_at_time('LABEL', '2025-12-01');
  • SELECT * FROM package_state_transitions WHERE label = 'LABEL';
    """)
    
except Exception as e:
    conn.rollback()
    print(f"\n✗ Migration failed: {e}")
    raise
finally:
    cursor.close()
    conn.close()

print("="*70)
