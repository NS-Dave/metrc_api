"""
Harvest Reconciliation - Supabase Version

Query Supabase data warehouse for instant harvest weight reconciliation.
Much faster than querying Metrc API directly (< 1 second vs 2-5 minutes).

Prerequisites:
1. Run supabase_schema.sql in Supabase
2. Run metrc_daily_sync.py to populate data
3. Set SUPABASE_PASSWORD environment variable
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
from supabase_config import get_connection_string


def format_weight(grams, unit='Grams'):
    """Format weight with proper unit."""
    if unit == 'Pounds':
        return f"{grams / 453.592:.2f} lb"
    elif unit == 'Ounces':
        return f"{grams / 28.3495:.2f} oz"
    elif unit == 'Kilograms':
        return f"{grams / 1000:.2f} kg"
    else:
        return f"{grams:.2f}g"


def run_reconciliation_report(min_discrepancy_grams=5.0, license_number='MC281599'):
    """
    Run harvest reconciliation report from Supabase.
    
    Args:
        min_discrepancy_grams: Minimum discrepancy to report (default 5g)
        license_number: License to analyze (default MC281599 cultivation)
    """
    print("=" * 80)
    print("HARVEST WEIGHT RECONCILIATION - SUPABASE")
    print(f"License: {license_number}")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Minimum Discrepancy: {min_discrepancy_grams}g")
    print("=" * 80)
    print()
    
    # Connect to Supabase
    print("Connecting to Supabase...")
    conn = psycopg2.connect(get_connection_string(), cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    
    # Check when data was last synced
    cursor.execute("""
        SELECT MAX(synced_at) as last_sync
        FROM metrc_harvests
        WHERE license_number = %s
    """, (license_number,))
    
    last_sync = cursor.fetchone()['last_sync']
    print(f"✓ Connected")
    print(f"  Data last synced: {last_sync}")
    print()
    
    # Get reconciliation data
    cursor.execute("""
        SELECT 
            harvest_name,
            harvest_date,
            harvest_packaged_weight,
            unit_of_weight,
            package_count,
            total_package_weight_grams,
            active_package_weight_grams,
            weight_discrepancy_grams,
            is_finished,
            harvest_synced_at,
            packages_synced_at
        FROM harvest_reconciliation
        WHERE license_number = %s
            AND weight_discrepancy_grams >= %s
        ORDER BY weight_discrepancy_grams DESC
    """, (license_number, min_discrepancy_grams))
    
    discrepancies = cursor.fetchall()
    
    if not discrepancies:
        print(f"✓ No discrepancies found >= {min_discrepancy_grams}g")
        print()
        
        # Show summary stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_harvests,
                SUM(package_count) as total_packages,
                AVG(weight_discrepancy_grams) as avg_discrepancy,
                MAX(weight_discrepancy_grams) as max_discrepancy
            FROM harvest_reconciliation
            WHERE license_number = %s
        """, (license_number,))
        
        stats = cursor.fetchone()
        print("Summary:")
        print(f"  Total harvests: {stats['total_harvests']}")
        print(f"  Total packages: {stats['total_packages']}")
        print(f"  Average discrepancy: {stats['avg_discrepancy']:.2f}g")
        print(f"  Maximum discrepancy: {stats['max_discrepancy']:.2f}g")
        
    else:
        print(f"Found {len(discrepancies)} harvests with discrepancies >= {min_discrepancy_grams}g:")
        print()
        print("-" * 80)
        
        for i, disc in enumerate(discrepancies, 1):
            harvest_weight = format_weight(disc['harvest_packaged_weight'], disc['unit_of_weight'])
            package_weight = format_weight(disc['total_package_weight_grams'])
            active_weight = format_weight(disc['active_package_weight_grams'])
            discrepancy = format_weight(disc['weight_discrepancy_grams'])
            
            status = "FINISHED" if disc['is_finished'] else "ACTIVE"
            
            print(f"[{i}] {disc['harvest_name']}")
            print(f"    Harvest Date: {disc['harvest_date']}")
            print(f"    Status: {status}")
            print(f"    Harvest Weight: {harvest_weight}")
            print(f"    Package Count: {disc['package_count']}")
            print(f"    Total Package Weight: {package_weight}")
            print(f"    Active Package Weight: {active_weight}")
            print(f"    ⚠️  DISCREPANCY: {discrepancy}")
            print()
        
        print("-" * 80)
    
    # Get packages for most problematic harvest
    if discrepancies:
        worst_harvest = discrepancies[0]['harvest_name']
        
        print()
        print(f"Packages for most problematic harvest: {worst_harvest}")
        print("-" * 80)
        
        cursor.execute("""
            SELECT 
                label,
                product_name,
                quantity,
                unit_of_measure,
                packaged_date,
                finished_date,
                archived_date,
                location_name
            FROM metrc_packages
            WHERE source_harvest_names LIKE %s
                AND license_number = %s
            ORDER BY packaged_date DESC
        """, (f'%{worst_harvest}%', license_number))
        
        packages = cursor.fetchall()
        
        if packages:
            for pkg in packages:
                status = "FINISHED" if pkg['finished_date'] else ("ARCHIVED" if pkg['archived_date'] else "ACTIVE")
                print(f"  {pkg['label']}")
                print(f"    Product: {pkg['product_name']}")
                print(f"    Quantity: {pkg['quantity']} {pkg['unit_of_measure']}")
                print(f"    Status: {status}")
                print(f"    Location: {pkg['location_name']}")
                print()
        else:
            print(f"  ⚠️  No packages found linked to this harvest!")
            print(f"  This may indicate:")
            print(f"    - Harvest name mismatch in package source field")
            print(f"    - Packages not yet created from harvest")
            print(f"    - Packages on different license")
            print()
    
    print("=" * 80)
    print("✓ RECONCILIATION COMPLETE")
    print("=" * 80)
    
    conn.close()


def get_harvest_summary(license_number='MC281599'):
    """Get summary statistics for all harvests."""
    conn = psycopg2.connect(get_connection_string(), cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_harvests,
            SUM(CASE WHEN is_finished THEN 1 ELSE 0 END) as finished_count,
            SUM(CASE WHEN is_finished THEN 0 ELSE 1 END) as active_count,
            SUM(total_packaged_weight) as total_weight,
            AVG(total_packaged_weight) as avg_weight,
            MAX(harvest_date) as most_recent_harvest,
            MIN(harvest_date) as oldest_harvest
        FROM metrc_harvests
        WHERE license_number = %s
            AND total_packaged_weight > 0
    """, (license_number,))
    
    stats = cursor.fetchone()
    
    print("=" * 80)
    print(f"HARVEST SUMMARY - {license_number}")
    print("=" * 80)
    print(f"Total harvests with packages: {stats['total_harvests']}")
    print(f"Finished: {stats['finished_count']}")
    print(f"Active: {stats['active_count']}")
    print(f"Total packaged weight: {stats['total_weight']:.2f}g")
    print(f"Average harvest weight: {stats['avg_weight']:.2f}g")
    print(f"Most recent harvest: {stats['most_recent_harvest']}")
    print(f"Oldest harvest: {stats['oldest_harvest']}")
    print("=" * 80)
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    # Check for command line arguments
    min_discrepancy = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    license_number = sys.argv[2] if len(sys.argv) > 2 else 'MC281599'
    
    # Run summary first
    get_harvest_summary(license_number)
    print()
    
    # Run reconciliation
    run_reconciliation_report(min_discrepancy, license_number)
