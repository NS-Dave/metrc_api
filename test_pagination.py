#!/usr/bin/env python3
"""Test pagination on active packages endpoint."""

from dotenv import load_dotenv
load_dotenv()

from client import MetrcClient
from config import MetrcConfig
from processing import ProcessingClient

# Initialize
config = MetrcConfig.from_env()
client = MetrcClient(config)
processing = ProcessingClient(client)

print("Testing active packages endpoint WITH pagination...")
print("=" * 80)

# Get active packages with pagination
packages = processing.get_packages('active', license_number='MC281599')

print(f"\nTotal active packages retrieved: {len(packages)}")

# Show first few packages
if packages:
    print(f"\nFirst package: {packages[0].get('Label', 'N/A')}")
    print(f"Last package: {packages[-1].get('Label', 'N/A')}")

# Count by location
locations = {}
for pkg in packages:
    loc = pkg.get('LocationName', 'Unknown')
    locations[loc] = locations.get(loc, 0) + 1

print(f"\nActive packages by location:")
for loc, count in sorted(locations.items(), key=lambda x: x[1], reverse=True):
    print(f"  {loc}: {count}")

print("=" * 80)
