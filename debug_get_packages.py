#!/usr/bin/env python3
"""Debug what get_packages returns with pagination."""

from dotenv import load_dotenv
load_dotenv()

from processing import ProcessingClient
from client import MetrcClient
from config import MetrcConfig

config = MetrcConfig.from_env()
client = MetrcClient(config)
processing = ProcessingClient(client)

result = processing.get_packages('active', license_number='MC281599')

print(f"Type: {type(result)}")
print(f"Length: {len(result) if isinstance(result, (list, dict)) else 'N/A'}")

if isinstance(result, dict):
    print(f"Keys: {result.keys()}")
    if 'Data' in result:
        print(f"Data length: {len(result['Data'])}")
elif isinstance(result, list):
    print(f"List length: {len(result)}")
    if result:
        print(f"First item keys: {result[0].keys() if isinstance(result[0], dict) else 'N/A'}")
