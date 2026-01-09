"""
Reset historical backfill sync log to force complete re-processing.
This will delete all 'completed' backfill entries from the sync log,
allowing the backfill to run from the beginning (March 9, 2023).

Use this when you need to reprocess historical data with updated logic
(like the product_name extraction fix).
"""

from metrc_daily_sync import MetrcSupabaseSync

def reset_backfill_log():
    syncer = MetrcSupabaseSync()
    syncer.connect_supabase()
    cursor = syncer.conn.cursor()
    
    # Count current entries
    cursor.execute("""
        SELECT COUNT(*), MIN(date_range_start), MAX(date_range_end)
        FROM metrc_sync_log
        WHERE sync_type = 'backfill' AND status = 'completed'
    """)
    count, min_date, max_date = cursor.fetchone()
    
    print(f"Current backfill log:")
    print(f"  Completed windows: {count:,}")
    print(f"  Date range: {min_date} to {max_date}")
    print()
    
    # Confirm
    response = input("Delete all backfill sync log entries? This will force complete re-processing. (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        syncer.close()
        return
    
    # Delete
    cursor.execute("""
        DELETE FROM metrc_sync_log
        WHERE sync_type = 'backfill' AND status = 'completed'
    """)
    
    deleted = cursor.rowcount
    syncer.conn.commit()
    
    print(f"\n✓ Deleted {deleted:,} sync log entries")
    print("The backfill will now process all windows from 2023-03-09")
    
    syncer.close()

if __name__ == '__main__':
    reset_backfill_log()
