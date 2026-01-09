#!/usr/bin/env python3
"""
Historical backfill for plants and plant batches.

Unlike transfers, plants and plant batches APIs support last_modified filtering,
so we can fetch historical inactive records in chunks.

Usage:
    python backfill_plants.py --days 90          # Last 90 days
    python backfill_plants.py --start 2023-05-01 --end 2026-01-06
    python backfill_plants.py --days 981 --yes   # Full backfill from inception
"""

import argparse
from datetime import datetime, timedelta
from metrc_daily_sync import MetrcSupabaseSync
import time
import sys

def backfill_plants(start_date: datetime, end_date: datetime, licenses: list = None, delay_seconds: int = 1):
    """
    Backfill plants and plant batches for a date range.
    
    Processes in 7-day chunks to balance API load and completeness.
    
    Args:
        start_date: Start of date range
        end_date: End of date range  
        licenses: List of license numbers
        delay_seconds: Seconds to wait between chunks (default 1)
    """
    if licenses is None:
        licenses = ['MC281599']  # Only cultivation license has plants
    
    sync = MetrcSupabaseSync()
    
    # Calculate total days
    total_days = (end_date - start_date).days
    chunk_hours = 24  # Metrc API limit: max 24 hours per query
    total_chunks = total_days  # One chunk per day
    
    print(f"\n{'=' * 80}")
    print(f"PLANTS & PLANT BATCHES BACKFILL")
    print(f"{'=' * 80}")
    print(f"Date range: {start_date.date()} to {end_date.date()} ({total_days} days)")
    print(f"Licenses: {', '.join(licenses)}")
    print(f"Processing in {chunk_hours}-hour chunks ({total_chunks} chunks total)...")
    print(f"{'=' * 80}\n")
    
    total_plants = 0
    total_batches = 0
    chunks_processed = 0
    chunks_failed = 0
    
    # Process in 24-hour chunks (API requirement)
    current = start_date
    chunk_num = 0
    
    while current < end_date:
        chunk_num += 1
        chunk_end = min(current + timedelta(hours=chunk_hours), end_date)
        start_str = current.strftime('%Y-%m-%dT%H:%M:%S')
        end_str = chunk_end.strftime('%Y-%m-%dT%H:%M:%S')
        
        print(f"\nChunk {chunk_num}/{total_chunks}: {current.date()} to {chunk_end.date()}")
        print("-" * 80)
        
        chunk_plants = 0
        chunk_batches = 0
        
        for license_number in licenses:
            print(f"License: {license_number}")
            
            try:
                # Fetch inactive plants in this chunk
                phases = ['vegetative', 'flowering', 'onhold', 'inactive']
                all_plants = []
                
                for phase in phases:
                    try:
                        result = sync.cultivation.get_plants(
                            license_number=license_number,
                            phase=phase,
                            last_modified_start=start_str,
                            last_modified_end=end_str
                        )
                        # Handle response format
                        if isinstance(result, dict):
                            plants = result.get('Data', [])
                        elif isinstance(result, list):
                            plants = result
                        else:
                            plants = []
                        
                        if len(plants) > 0:
                            all_plants.extend(plants)
                            print(f"  Found {len(plants)} {phase} plants")
                    except Exception as e:
                        if 'Authentication failed' not in str(e):
                            print(f"  Warning: Error fetching {phase} plants: {e}")
                
                # Upsert plants
                if all_plants:
                    try:
                        inserted, updated = sync.upsert_plants(all_plants, license_number)
                        chunk_plants += len(all_plants)
                        print(f"  Plants: {inserted} inserted, {updated} updated")
                    except Exception as e:
                        print(f"  ERROR upserting plants: {e}")
                        # Rollback and reconnect
                        if sync.conn and not sync.conn.closed:
                            sync.conn.rollback()
                        sync.connect_supabase()
                
                # Fetch inactive plant batches in this chunk
                all_batches = []
                for status in ['active', 'inactive']:
                    try:
                        result = sync.cultivation.get_plant_batches(
                            license_number=license_number,
                            status=status,
                            last_modified_start=start_str,
                            last_modified_end=end_str
                        )
                        # Handle response format
                        if isinstance(result, dict):
                            batches = result.get('Data', [])
                        elif isinstance(result, list):
                            batches = result
                        else:
                            batches = []
                        
                        if len(batches) > 0:
                            all_batches.extend(batches)
                            print(f"  Found {len(batches)} {status} plant batches")
                    except Exception as e:
                        if 'Authentication failed' not in str(e):
                            print(f"  Warning: Error fetching {status} batches: {e}")
                
                # Upsert plant batches
                if all_batches:
                    try:
                        inserted, updated = sync.upsert_plant_batches(all_batches, license_number)
                        chunk_batches += len(all_batches)
                        print(f"  Plant Batches: {inserted} inserted, {updated} updated")
                    except Exception as e:
                        print(f"  ERROR upserting plant batches: {e}")
                        # Rollback and reconnect
                        if sync.conn and not sync.conn.closed:
                            sync.conn.rollback()
                        sync.connect_supabase()
                
                if not all_plants and not all_batches:
                    print(f"  No plants or batches in this period")
                
            except Exception as e:
                print(f"  ERROR processing chunk: {e}")
                chunks_failed += 1
                continue
        
        total_plants += chunk_plants
        total_batches += chunk_batches
        chunks_processed += 1
        
        print(f"  Chunk total: {chunk_plants} plants, {chunk_batches} batches")
        
        # Move to next chunk
        current = chunk_end
        
        # Delay between chunks to avoid rate limiting
        if current < end_date:
            time.sleep(delay_seconds)
    
    # Final summary
    print(f"\n{'=' * 80}")
    print(f"BACKFILL COMPLETE")
    print(f"{'=' * 80}")
    print(f"Chunks processed: {chunks_processed}/{total_chunks}")
    print(f"Chunks failed: {chunks_failed}")
    print(f"Total plants: {total_plants}")
    print(f"Total plant batches: {total_batches}")
    print(f"{'=' * 80}\n")
    
    sync.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill plants and plant batches from Metrc')
    parser.add_argument('--days', type=int, help='Number of days to backfill from today')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--delay', type=int, default=1, help='Delay in seconds between chunks (default: 1)')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    # Determine date range
    end_date = datetime.now()
    
    if args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    elif args.days:
        start_date = end_date - timedelta(days=args.days)
    else:
        parser.error("Must specify either --days OR both --start and --end")
    
    # Confirmation
    total_days = (end_date - start_date).days
    chunk_hours = 24
    total_chunks = total_days
    
    if not args.yes:
        print(f"\nBackfill Configuration:")
        print(f"  Start: {start_date.date()}")
        print(f"  End: {end_date.date()}")
        print(f"  Days: {total_days}")
        print(f"  Chunks: {total_chunks} ({chunk_hours}-hour chunks)")
        print(f"  Delay: {args.delay}s between chunks")
        print(f"\nThis will make approximately {total_chunks * 8} API calls.")
        
        response = input("\nProceed? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)
    
    # Run backfill
    backfill_plants(start_date, end_date, delay_seconds=args.delay)


if __name__ == '__main__':
    main()
