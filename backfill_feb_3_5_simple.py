"""
Backfill Metrc Data for February 3-5, 2026 - SIMPLE VERSION

Calls the existing daily sync functionality for specific dates.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
from datetime import datetime

# Import the existing sync class
from metrc_daily_sync import MetrcSupabaseSync

# License configuration
CULTIVATION_LICENSE = os.getenv('METRC_LICENSE_CULTIVATION', 'MC281599')
PROCESSING_LICENSE = os.getenv('METRC_LICENSE_PROCESSING', 'MP281433')


def main():
    """Main backfill execution using existing sync methods."""
    print()
    print("=" * 70)
    print("METRC BACKFILL: February 3-5, 2026")
    print("=" * 70)
    print()
    print("This will backfill data that was missed when automation was broken.")
    print("Using the same sync logic as the daily automation.")
    print()
    
    # Define date ranges for each day (48 hour windows centered on each day)
    dates = [
        ("Feb 3", 48, datetime(2026, 2, 3)),
        ("Feb 4", 48, datetime(2026, 2, 4)),
        ("Feb 5", 48, datetime(2026, 2, 5)),
    ]
    
    try:
        syncer = MetrcSupabaseSync()
        
        for date_label, hours, _ in dates:
            print()
            print("=" * 70)
            print(f"Syncing data for {date_label}, 2026 (last {hours} hours)")
            print("=" * 70)
            print()
            
            # Cultivation License
            print(f"CULTIVATION LICENSE: {CULTIVATION_LICENSE}")
            print("-" * 70)
            
            # Harvests
            print(f"Syncing harvests...")
            syncer.sync_harvests_incremental(CULTIVATION_LICENSE, hours=hours)
            
            # Packages
            print(f"Syncing packages...")
            syncer.sync_packages_incremental(CULTIVATION_LICENSE, hours=hours)
            
            print()
            
            # Processing License  
            print(f"PROCESSING LICENSE: {PROCESSING_LICENSE}")
            print("-" * 70)
            
            # Packages
            print(f"Syncing packages...")
            syncer.sync_packages_incremental(PROCESSING_LICENSE, hours=hours)
            
            print()
        
        syncer.close()
        
        print()
        print("=" * 70)
        print("[SUCCESS] ALL BACKFILLS COMPLETED")
        print("=" * 70)
        print()
        print("Data for February 3-5, 2026 has been synced to Supabase.")
        print()
        
    except Exception as e:
        print()
        print("=" * 70)
        print("[ERROR] BACKFILL FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
