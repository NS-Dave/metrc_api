#!/usr/bin/env python3
"""
Historical backfill for transfer data with direction-aware storage.

This script fetches transfers going back historically and populates Supabase
with complete transfer, delivery, and package details.

Usage:
    python backfill_transfers.py --days 90          # Last 90 days
    python backfill_transfers.py --start 2025-01-01 --end 2026-01-06
"""

import argparse
from datetime import datetime, timedelta
from transfer_sync_direction_aware import DirectionAwareTransferSync
import time
import sys

def backfill_transfers(start_date: datetime, end_date: datetime, licenses: list = None, delay_seconds: int = 1):
    """
    Backfill transfers for a date range.
    
    Processes in 24-hour chunks due to Metrc API limitations.
    
    Args:
        start_date: Start of date range
        end_date: End of date range  
        licenses: List of license numbers
        delay_seconds: Seconds to wait between chunks (default 1, increase if rate limited)
    """
    if licenses is None:
        licenses = ['MP281433', 'MC281599']
    
    sync = DirectionAwareTransferSync()
    
    # Calculate total days
    total_days = (end_date - start_date).days
    print(f"\n{'=' * 80}")
    print(f"TRANSFER BACKFILL")
    print(f"{'=' * 80}")
    print(f"Date range: {start_date.date()} to {end_date.date()} ({total_days} days)")
    print(f"Licenses: {', '.join(licenses)}")
    print(f"Processing in 24-hour chunks...")
    print(f"{'=' * 80}\n")
    
    total_incoming = 0
    total_outgoing = 0
    total_packages = 0
    chunks_processed = 0
    chunks_failed = 0
    
    # Process in 24-hour chunks (working backwards from end_date)
    current_end = end_date
    
    while current_end > start_date:
        current_start = max(current_end - timedelta(hours=23), start_date)
        chunk_num = chunks_processed + chunks_failed + 1
        
        print(f"\n[Chunk {chunk_num}] {current_start.strftime('%Y-%m-%d %H:%M')} to {current_end.strftime('%Y-%m-%d %H:%M')}")
        print("-" * 80)
        
        try:
            for license_number in licenses:
                print(f"\nProcessing {license_number}...")
                
                # Fetch incoming transfers
                print("  Fetching incoming transfers...")
                incoming_transfers = []
                try:
                    response = sync.processing.get_incoming_transfers(
                        license_number=license_number,
                        last_modified_start=current_start.strftime('%Y-%m-%dT%H:%M:%S'),
                        last_modified_end=current_end.strftime('%Y-%m-%dT%H:%M:%S')
                    )
                    if isinstance(response, dict):
                        incoming_transfers = response.get('Data', [])
                    elif isinstance(response, list):
                        incoming_transfers = response
                except Exception as e:
                    print(f"    ! Error fetching incoming: {e}")
                
                # Fetch outgoing transfers
                print("  Fetching outgoing transfers...")
                outgoing_transfers = []
                try:
                    response = sync.processing.get_outgoing_transfers(
                        license_number=license_number,
                        last_modified_start=current_start.strftime('%Y-%m-%dT%H:%M:%S'),
                        last_modified_end=current_end.strftime('%Y-%m-%dT%H:%M:%S')
                    )
                    if isinstance(response, dict):
                        outgoing_transfers = response.get('Data', [])
                    elif isinstance(response, list):
                        outgoing_transfers = response
                except Exception as e:
                    print(f"    ! Error fetching outgoing: {e}")
                
                # Deduplicate
                incoming_unique = sync._deduplicate_by_id(incoming_transfers)
                outgoing_unique = sync._deduplicate_by_id(outgoing_transfers)
                
                print(f"    Found {len(incoming_unique)} incoming, {len(outgoing_unique)} outgoing")
                
                # Store incoming
                if incoming_unique:
                    try:
                        inc_inserted, inc_updated = sync.upsert_transfers_with_direction(
                            incoming_unique, license_number, 'incoming'
                        )
                        print(f"    OK Incoming: {inc_inserted} inserted, {inc_updated} updated")
                        total_incoming += len(incoming_unique)
                    except Exception as e:
                        print(f"    ERROR storing incoming: {e}")
                
                # Store outgoing
                if outgoing_unique:
                    try:
                        out_inserted, out_updated = sync.upsert_transfers_with_direction(
                            outgoing_unique, license_number, 'outgoing'
                        )
                        print(f"    OK Outgoing: {out_inserted} inserted, {out_updated} updated")
                        total_outgoing += len(outgoing_unique)
                    except Exception as e:
                        print(f"    ERROR storing outgoing: {e}")
                
                # Small delay to avoid rate limiting
                time.sleep(delay_seconds)
            
            chunks_processed += 1
            
        except Exception as e:
            print(f"\nERROR Chunk failed: {e}")
            chunks_failed += 1
            # Continue with next chunk instead of stopping
        
        # Move to previous chunk
        current_end = current_start
        
        # Progress update every 10 chunks
        if chunk_num % 10 == 0:
            print(f"\n{'=' * 80}")
            print(f"Progress: {chunks_processed} chunks completed, {chunks_failed} failed")
            print(f"Transfers: {total_incoming} incoming, {total_outgoing} outgoing")
            print(f"{'=' * 80}\n")
    
    # Final summary
    print(f"\n{'=' * 80}")
    print(f"BACKFILL COMPLETE")
    print(f"{'=' * 80}")
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Chunks processed: {chunks_processed}")
    print(f"Chunks failed: {chunks_failed}")
    print(f"Total transfers: {total_incoming + total_outgoing}")
    print(f"  - Incoming: {total_incoming}")
    print(f"  - Outgoing: {total_outgoing}")
    print(f"{'=' * 80}\n")
    
    # Count packages in database
    try:
        sync.connect_supabase()
        cursor = sync.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM metrc_transfer_packages")
        package_count = cursor.fetchone()[0]
        print(f"Total packages in database: {package_count:,}")
    except Exception as e:
        print(f"Could not count packages: {e}")
    
    return chunks_processed, chunks_failed


def main():
    parser = argparse.ArgumentParser(
        description='Backfill historical transfer data from Metrc API'
    )
    
    # Option 1: Specify number of days back
    parser.add_argument(
        '--days',
        type=int,
        help='Number of days to backfill (e.g., 90 for last 90 days)'
    )
    
    # Option 2: Specify exact date range
    parser.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD), defaults to today'
    )
    
    # Optional: specific licenses
    parser.add_argument(
        '--licenses',
        nargs='+',
        help='License numbers to process (default: MP281433 MC281599)'
    )
    
    # Optional: delay between chunks
    parser.add_argument(
        '--delay',
        type=int,
        default=1,
        help='Seconds to wait between chunks (default: 1, increase if rate limited)'
    )
    
    # Skip confirmation prompt
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt (for unattended runs)'
    )
    
    args = parser.parse_args()
    
    # Determine date range
    end_date = datetime.now()
    
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    
    if args.days:
        start_date = end_date - timedelta(days=args.days)
    elif args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
    else:
        # Default to 30 days
        print("No date range specified, defaulting to last 30 days")
        print("Use --days or --start/--end to specify range")
        print()
        start_date = end_date - timedelta(days=30)
    
    # Get licenses
    licenses = args.licenses if args.licenses else ['MP281433', 'MC281599']
    
    # Confirm before starting
    total_days = (end_date - start_date).days
    estimated_chunks = total_days + 1  # Roughly one chunk per day
    estimated_time_minutes = estimated_chunks * 0.5  # Rough estimate: 30 seconds per chunk
    
    print(f"\nBackfill configuration:")
    print(f"  Start: {start_date.date()}")
    print(f"  End: {end_date.date()}")
    print(f"  Days: {total_days}")
    print(f"  Licenses: {', '.join(licenses)}")
    print(f"  Estimated chunks: ~{estimated_chunks}")
    print(f"  Estimated time: ~{estimated_time_minutes:.0f} minutes")
    
    if not args.yes:
        response = input(f"\nProceed with backfill? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled")
            sys.exit(0)
    else:
        print("\n[Auto-confirmed with --yes flag]")
    
    # Run backfill
    start_time = time.time()
    chunks_processed, chunks_failed = backfill_transfers(start_date, end_date, licenses, args.delay)
    elapsed_time = time.time() - start_time
    
    print(f"\nTotal time: {elapsed_time/60:.1f} minutes")
    print(f"Success rate: {chunks_processed}/{chunks_processed + chunks_failed} chunks")
    
    if chunks_failed > 0:
        print(f"\nWARNING: {chunks_failed} chunks failed. Consider re-running for failed date ranges.")
        sys.exit(1)
    else:
        print("\nSUCCESS: Backfill completed successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()
