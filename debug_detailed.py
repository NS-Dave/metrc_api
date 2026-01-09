from dotenv import load_dotenv
load_dotenv()

from config import MetrcConfig
from client import MetrcClient
import json

config = MetrcConfig.from_env()

# Create client
client = MetrcClient(config)

# Monkey patch to see what's happening
original_request = client._make_request

def debug_request(method, endpoint, **kwargs):
    url = f"{client.config.base_url}{endpoint}"
    print(f"Making request to: {url}")
    
    # Build headers
    headers = {
        'Authorization': client._create_auth_header(),
        'Content-Type': 'application/json'
    }
    
    # Make raw request without using session
    import requests
    response = requests.get(url, headers=headers, timeout=30)
    
    print(f"Status: {response.status_code}")
    print(f"Content length: {len(response.content)}")
    print(f"Has content: {bool(response.content)}")
    print(f"Text length: {len(response.text)}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Encoding: {response.encoding}")
    
    if response.content:
        try:
            data = response.json()
            print(f"JSON parsed successfully - {len(data)} items")
            return data
        except Exception as e:
            print(f"JSON parse error: {e}")
            print(f"First 200 chars: {response.text[:200]}")
    
    return None

try:
    facilities = debug_request('GET', '/facilities/v2')
    print(f"\nSuccess! Got {len(facilities)} facilities")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
