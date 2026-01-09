#!/usr/bin/env python3
"""Quick test of plants sync in metrc_daily_sync"""

from metrc_daily_sync import MetrcSupabaseSync

syncer = MetrcSupabaseSync()

try:
    syncer.connect_supabase()
    print("Testing plants sync...\n")
    
    # Test cultivation license
    syncer.sync_plants('MC281599')
    
    # Test processing license (should gracefully skip)
    syncer.sync_plants('MP281433')
    
    print("\n✓ Plants sync test completed")
    
finally:
    syncer.close()
