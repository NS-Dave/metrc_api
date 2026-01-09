"""
Harvest Weight Reconciliation
Tracks the whereabouts of all packaged weight from harvests.

For each harvest with TotalPackagedWeight > 0, accounts for:
- Active packages (current inventory)
- Transferred packages (transferred out, including to processing license)

All weights tracked in grams for reconciliation.
"""
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from processing import ProcessingClient
from utils import DateUtils
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

# License configuration
CULTIVATION_LICENSE = os.getenv('METRC_LICENSE_CULTIVATION', 'MC281599')
PROCESSING_LICENSE = os.getenv('METRC_LICENSE_PROCESSING', 'MP281433')

def get_all_harvests(cultivation_client, license_number):
    """Get all harvests (active and inactive) with packaged weight."""
    print("Fetching all harvests...")
    
    # Get active harvests
    active_response = cultivation_client.get_harvests('active', license_number=license_number)
    # API returns paginated response with Data field
    active = active_response['Data'] if isinstance(active_response, dict) and 'Data' in active_response else (active_response if isinstance(active_response, list) else [])
    print(f"  ✓ {len(active)} active harvests")
    
    # Get inactive harvests in 24-hour chunks (API limit)
    # Get last 12 months of inactive harvests
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    inactive = []
    current_start = start_date
    
    print("  Fetching inactive harvests in 24-hour chunks...")
    chunk_count = 0
    while current_start < end_date:
        # Calculate 24-hour chunk end (exactly 24 hours)
        current_end = min(current_start + timedelta(hours=24), end_date)
        
        start_str = current_start.strftime('%Y-%m-%dT%H:%M:%S')
        end_str = current_end.strftime('%Y-%m-%dT%H:%M:%S')
        
        chunk_count += 1
        if chunk_count % 10 == 0:
            print(f"    Processing chunk {chunk_count}...")
        
        try:
            chunk_response = cultivation_client.get_harvests(
                'inactive',
                license_number=license_number,
                last_modified_start=start_str,
                last_modified_end=end_str
            )
            # Extract Data field from paginated response
            chunk = chunk_response['Data'] if isinstance(chunk_response, dict) and 'Data' in chunk_response else (chunk_response if isinstance(chunk_response, list) else [])
            inactive.extend(chunk)
        except Exception as e:
            print(f"    Error fetching chunk {start_str} to {end_str}: {e}")
            # Continue to next chunk
        
        # Move to next chunk (start where this one ended)
        current_start = current_end
    
    print(f"  ✓ {len(inactive)} inactive harvests (last 12 months)")
    
    # Combine and filter to harvests with packaged weight
    all_harvests = active + inactive
    harvests_with_packages = [
        h for h in all_harvests 
        if h.get('TotalPackagedWeight', 0) > 0
    ]
    
    print(f"  ✓ {len(harvests_with_packages)} harvests with packaged weight")
    
    return harvests_with_packages

def convert_to_grams(quantity, unit):
    """Convert quantity to grams based on unit."""
    # Common conversions
    conversions = {
        'Grams': 1.0,
        'Ounces': 28.3495,
        'Pounds': 453.592,
        'Kilograms': 1000.0,
        'Milligrams': 0.001
    }
    
    return quantity * conversions.get(unit, 1.0)

def get_packages_for_harvest(processing_client, harvest_name, license_number):
    """Get all packages (active and inactive) linked to a harvest."""
    
    # Get active packages
    active_response = processing_client.get_packages('active', license_number=license_number)
    active_packages = active_response['Data'] if isinstance(active_response, dict) and 'Data' in active_response else (active_response if isinstance(active_response, list) else [])
    
    # Get inactive packages (transferred, finished, etc.)
    inactive_response = processing_client.get_packages('inactive', license_number=license_number)
    inactive_packages = inactive_response['Data'] if isinstance(inactive_response, dict) and 'Data' in inactive_response else (inactive_response if isinstance(inactive_response, list) else [])
    
    all_packages = active_packages + inactive_packages
    
    # Filter to packages from this harvest
    harvest_packages = []
    for pkg in all_packages:
        # Check if package came from this harvest
        # This could be in SourceHarvestNames or similar field
        source_harvests = pkg.get('SourceHarvestNames', '')
        if harvest_name in source_harvests:
            harvest_packages.append(pkg)
    
    return harvest_packages

def categorize_package(package):
    """Categorize package status."""
    
    # Package is finished/transferred out
    if package.get('FinishedDate'):
        return 'transferred'
    
    # Package is active in inventory
    if package.get('Quantity', 0) > 0:
        return 'active'
    
    # Package exists but has zero quantity (likely transferred)
    return 'transferred'

def reconcile_harvest(harvest, packages):
    """Reconcile harvest packaged weight with actual packages."""
    
    harvest_name = harvest['Name']
    total_packaged_grams = harvest['TotalPackagedWeight']  # Already in grams
    
    # Categorize packages
    active_weight = 0.0
    transferred_weight = 0.0
    
    for pkg in packages:
        quantity = pkg.get('Quantity', 0)
        unit = pkg.get('UnitOfMeasureAbbreviation', 'Grams')
        weight_grams = convert_to_grams(quantity, unit)
        
        status = categorize_package(pkg)
        
        if status == 'active':
            active_weight += weight_grams
        else:
            transferred_weight += weight_grams
    
    total_accounted = active_weight + transferred_weight
    discrepancy = total_packaged_grams - total_accounted
    
    return {
        'harvest_name': harvest_name,
        'harvest_id': harvest['Id'],
        'total_packaged_grams': total_packaged_grams,
        'active_grams': active_weight,
        'transferred_grams': transferred_weight,
        'total_accounted_grams': total_accounted,
        'discrepancy_grams': discrepancy,
        'discrepancy_pct': (discrepancy / total_packaged_grams * 100) if total_packaged_grams > 0 else 0,
        'package_count': len(packages),
        'status': harvest.get('FinishedDate') and 'Finished' or 'Active'
    }

def run_reconciliation():
    """Run full harvest weight reconciliation."""
    
    print("=" * 70)
    print("HARVEST WEIGHT RECONCILIATION")
    print(f"License: {CULTIVATION_LICENSE}")
    print(f"Date: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    
    print("Connecting to Metrc API...")
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    
    try:
        facilities = client.get_facilities()
        print(f"✓ Connected - {len(facilities)} facilities accessible")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        raise Exception("Failed to connect to Metrc API")
    
    cultivation = CultivationClient(client)
    processing = ProcessingClient(client)
    
    print()
    
    # Get all harvests with packaged weight
    harvests = get_all_harvests(cultivation, CULTIVATION_LICENSE)
    
    if not harvests:
        print("No harvests with packaged weight found.")
        return
    
    print()
    print(f"Analyzing {len(harvests)} harvests...")
    print()
    
    # Reconcile each harvest
    results = []
    
    for i, harvest in enumerate(harvests, 1):
        harvest_name = harvest['Name']
        print(f"[{i}/{len(harvests)}] {harvest_name}...", end=" ")
        
        # Get packages for this harvest
        packages = get_packages_for_harvest(processing, harvest_name, CULTIVATION_LICENSE)
        
        # Reconcile
        result = reconcile_harvest(harvest, packages)
        results.append(result)
        
        # Print summary
        if abs(result['discrepancy_grams']) > 0.1:
            status = "⚠️  DISCREPANCY"
        else:
            status = "✓ OK"
        
        print(f"{result['package_count']} packages - {status}")
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    # Calculate totals
    total_harvested = sum(r['total_packaged_grams'] for r in results)
    total_active = sum(r['active_grams'] for r in results)
    total_transferred = sum(r['transferred_grams'] for r in results)
    total_discrepancy = sum(r['discrepancy_grams'] for r in results)
    
    print(f"Total Harvested Weight:    {total_harvested:,.2f} g")
    print(f"  - Active Inventory:      {total_active:,.2f} g ({total_active/total_harvested*100:.1f}%)")
    print(f"  - Transferred Out:       {total_transferred:,.2f} g ({total_transferred/total_harvested*100:.1f}%)")
    print(f"  - Discrepancy:           {total_discrepancy:,.2f} g ({total_discrepancy/total_harvested*100:.2f}%)")
    print()
    
    # Show harvests with discrepancies
    discrepancies = [r for r in results if abs(r['discrepancy_grams']) > 0.1]
    
    if discrepancies:
        print(f"⚠️  {len(discrepancies)} harvests with discrepancies:")
        print()
        for r in sorted(discrepancies, key=lambda x: abs(x['discrepancy_grams']), reverse=True):
            print(f"  {r['harvest_name']}")
            print(f"    Packaged: {r['total_packaged_grams']:,.2f} g")
            print(f"    Accounted: {r['total_accounted_grams']:,.2f} g")
            print(f"    Discrepancy: {r['discrepancy_grams']:,.2f} g ({r['discrepancy_pct']:.2f}%)")
            print()
    else:
        print("✓ All harvests reconciled perfectly!")
    
    # Save detailed results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"harvest_reconciliation_{timestamp}.json"
    
    output = {
        'timestamp': datetime.now().isoformat(),
        'license': CULTIVATION_LICENSE,
        'summary': {
            'total_harvests': len(results),
            'total_harvested_grams': total_harvested,
            'total_active_grams': total_active,
            'total_transferred_grams': total_transferred,
            'total_discrepancy_grams': total_discrepancy,
            'harvests_with_discrepancies': len(discrepancies)
        },
        'harvests': results
    }
    
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Detailed results saved to: {filename}")
    
    return results

if __name__ == "__main__":
    import sys
    
    try:
        run_reconciliation()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
