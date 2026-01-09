"""Test the intransit endpoint"""
import os
from processing import ProcessingClient
from client import MetrcClient
from config import MetrcConfig

# Load config from environment
config = MetrcConfig(
    software_api_key=os.getenv('METRC_SOFTWARE_API_KEY'),
    user_api_key=os.getenv('METRC_USER_API_KEY')
)
client = MetrcClient(config)
proc = ProcessingClient(client)

print("Testing packages/v2/intransit endpoint for MC281599...")
result = proc.client.get(
    'packages/v2/intransit',
    params={},
    license_number='MC281599',
    paginate=True
)

print(f"\nFound {len(result)} in-transit packages")

if result:
    print("\nFirst 3 packages:")
    for pkg in result[:3]:
        print(f"  {pkg.get('Label')} - {pkg.get('ProductName')}")
        print(f"    From: {pkg.get('ItemFromFacilityLicenseNumber')}")
        print(f"    Received: {pkg.get('ReceivedDateTime')}")
else:
    print("\nNo packages returned from intransit endpoint")
    print("\nNote: The /intransit endpoint may only show packages during active")
    print("      transport (on a manifest), not packages sitting unreceived.")
