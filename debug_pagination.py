#!/usr/bin/env python3
"""Debug pagination response format."""

from dotenv import load_dotenv
load_dotenv()

from client import MetrcClient
from config import MetrcConfig

# Initialize
config = MetrcConfig.from_env()
client = MetrcClient(config)

print("Testing raw API response format...")
print("=" * 80)

# Make raw request without pagination
result = client._make_request('GET', 'packages/v2/active', 
                              params={'pageNumber': 1, 'pageSize': 5},
                              license_number='MC281599')

print(f"Type: {type(result)}")
print(f"Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
print(f"\nFirst 500 chars of response:")
import json
print(json.dumps(result, indent=2, default=str)[:500])
