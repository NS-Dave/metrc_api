"""Check what data the API actually returns for a delivery."""
from dotenv import load_dotenv
load_dotenv()

from config import MetrcConfig
from client import MetrcClient
from processing import ProcessingClient
import json
import os

# Initialize API client
config = MetrcConfig.from_env()
metrc_client = MetrcClient(config)
processing = ProcessingClient(metrc_client)

PROCESSING_LICENSE = os.getenv('METRC_LICENSE_PROCESSING', 'MP281433')

# The delivery that was successfully enriched according to terminal output
delivery_id = 3141413
manifest = '0003138613'

print(f"\n{'='*80}")
print(f"Fetching API data for manifest {manifest}, delivery {delivery_id}")
print(f"{'='*80}\n")

try:
    detail = processing.get_transfer_delivery(delivery_id, license_number=PROCESSING_LICENSE)
    
    if isinstance(detail, dict):
        packages = detail.get('Data', [])
        
        if packages:
            print(f"API returned {len(packages)} packages")
            print(f"\nFirst package structure:")
            print(json.dumps(packages[0], indent=2, default=str))
            
            print(f"\n{'='*80}")
            print(f"Key fields that should populate:")
            print(f"{'='*80}")
            pkg = packages[0]
            print(f"PackageLabel: {pkg.get('PackageLabel')}")
            print(f"ProductName: {pkg.get('ProductName')}")
            print(f"ItemName: {pkg.get('ItemName')}")
            print(f"ShippedQuantity: {pkg.get('ShippedQuantity')}")
            print(f"ReceivedQuantity: {pkg.get('ReceivedQuantity')}")
            print(f"ItemUnitThcPercent: {pkg.get('ItemUnitThcPercent')}")
            print(f"ItemUnitCbdPercent: {pkg.get('ItemUnitCbdPercent')}")
        else:
            print("API returned empty package list")
    else:
        print(f"API returned unexpected format: {type(detail)}")
        print(detail)

except Exception as e:
    print(f"API error: {e}")
    import traceback
    traceback.print_exc()
