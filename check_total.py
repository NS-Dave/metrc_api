#!/usr/bin/env python3
"""Check total active package count."""

from dotenv import load_dotenv
load_dotenv()

from client import MetrcClient
from config import MetrcConfig

config = MetrcConfig.from_env()
client = MetrcClient(config)

result = client._make_request('GET', 'packages/v2/active', 
                              params={'pageNumber': 1, 'pageSize': 1},
                              license_number='MC281599')

print(f"Total: {result['Total']}")
print(f"TotalRecords: {result['TotalRecords']}")
print(f"TotalPages: {result['TotalPages']}")
print(f"PageSize: {result['PageSize']}")
print(f"RecordsOnPage: {result['RecordsOnPage']}")
