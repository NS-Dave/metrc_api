from dotenv import load_dotenv
load_dotenv()

from config import MetrcConfig
from client import MetrcClient
import requests

config = MetrcConfig.from_env()
client = MetrcClient(config)

# Make a raw request to see what happens
url = f"{config.base_url}/facilities/v2"
auth_header = client._create_auth_header()

print(f"Testing: {url}")
print(f"Auth header (first 50 chars): {auth_header[:50]}...")

response = requests.get(url, headers={'Authorization': auth_header}, timeout=30)

print(f"\nStatus Code: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"Response text (first 500 chars):\n{response.text[:500]}")
