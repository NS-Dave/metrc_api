from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

from config import MetrcConfig
from client import MetrcClient

config = MetrcConfig.from_env()
client = MetrcClient(config)

print("\nTesting get_facilities()...")
try:
    facilities = client.get_facilities()
    print(f"SUCCESS! Got {len(facilities)} facilities")
except Exception as e:
    print(f"FAILED: {e}")
