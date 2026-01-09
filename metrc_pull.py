"""
Production Metrc Data Pull
Pulls Metrc data from production environment for reporting.

Supports multiple licenses:
- MC281599 (Cultivation)
- MP281433 (Processing)
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
from datetime import datetime

# License configuration
LICENSES = {
    'cultivation': os.getenv('METRC_LICENSE_CULTIVATION', 'MC281599'),
    'processing': os.getenv('METRC_LICENSE_PROCESSING', 'MP281433')
}

def pull_current_data():
    """Pull current state of Metrc data for reporting."""
    
    # Initialize clients with production credentials
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    
    if not client.test_connection():
        raise Exception("Failed to connect to Metrc API")
    
    cultivation = CultivationClient(client)
    processing = ProcessingClient(client)
    
    print(f"Pulling data for multiple licenses")
    print(f"Cultivation: {LICENSES['cultivation']}")
    print(f"Processing: {LICENSES['processing']}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("-" * 60)
    
    # Pull data
    data = {
        'cultivation': {},
        'processing': {},
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'licenses': LICENSES
        }
    }
    
    # Facilities (all licenses)
    print("Fetching facilities...")
    data['facilities'] = client.get_facilities()
    print(f"  ✓ {len(data['facilities'])} facilities")
    
    # === CULTIVATION LICENSE DATA ===
    cultivation_license = LICENSES['cultivation']
    print(f"\nCultivation License ({cultivation_license}):")
    
    # Strains
    print("  Fetching strains...")
    data['cultivation']['strains'] = cultivation.get_strains(license_number=cultivation_license)
    print(f"    ✓ {len(data['cultivation']['strains'])} strains")
    
    # Locations
    print("  Fetching locations...")
    data['cultivation']['locations'] = processing.get_locations(license_number=cultivation_license)
    print(f"    ✓ {len(data['cultivation']['locations'])} locations")
    
    # Plant Batches
    print("  Fetching plant batches...")
    data['cultivation']['plant_batches_active'] = cultivation.get_plant_batches('active', license_number=cultivation_license)
    print(f"    ✓ {len(data['cultivation']['plant_batches_active'])} active plant batches")
    
    # Plants
    print("  Fetching plants...")
    data['cultivation']['plants_vegetative'] = cultivation.get_plants('vegetative', license_number=cultivation_license)
    data['cultivation']['plants_flowering'] = cultivation.get_plants('flowering', license_number=cultivation_license)
    print(f"    ✓ {len(data['cultivation']['plants_vegetative'])} vegetative plants")
    print(f"    ✓ {len(data['cultivation']['plants_flowering'])} flowering plants")
    
    # Harvests
    print("  Fetching harvests...")
    data['cultivation']['harvests_active'] = cultivation.get_harvests('active', license_number=cultivation_license)
    print(f"    ✓ {len(data['cultivation']['harvests_active'])} active harvests")
    
    # === PROCESSING LICENSE DATA ===
    processing_license = LICENSES['processing']
    print(f"\nProcessing License ({processing_license}):")
    
    # Items
    print("  Fetching items...")
    data['processing']['items'] = processing.get_items(license_number=processing_license)
    print(f"    ✓ {len(data['processing']['items'])} items")
    
    # Locations
    print("  Fetching locations...")
    data['processing']['locations'] = processing.get_locations(license_number=processing_license)
    print(f"    ✓ {len(data['processing']['locations'])} locations")
    
    # Packages
    print("  Fetching packages...")
    data['processing']['packages_active'] = processing.get_packages('active', license_number=processing_license)
    print(f"    ✓ {len(data['processing']['packages_active'])} active packages")
    
    print("-" * 60)
    print("Pull complete!")
    
    # Save to JSON file with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"metrc_data_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"Data saved to: {filename}")
    
    return data

def pull_recent_changes(hours=1, buffer_minutes=5):
    """Pull only data modified in the last N hours."""
    
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    processing = ProcessingClient(client)
    
    # Get time window
    start_time, end_time = DateUtils.get_sync_window(hours=hours, buffer_minutes=buffer_minutes)
    
    print(f"Pulling recent changes for multiple licenses")
    print(f"Cultivation: {LICENSES['cultivation']}")
    print(f"Processing: {LICENSES['processing']}")
    print(f"Time range: {start_time} to {end_time}")
    print("-" * 60)
    
    data = {
        'cultivation': {},
        'processing': {},
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'licenses': LICENSES,
            'time_range': {
                'start': start_time,
                'end': end_time
            }
        }
    }
    
    cultivation_license = LICENSES['cultivation']
    processing_license = LICENSES['processing']
    
    # Get modified plants from cultivation license
    print(f"Fetching modified plants ({cultivation_license})...")
    data['cultivation']['plants_modified'] = []
    data['cultivation']['plants_modified'].extend(cultivation.get_plants(
        phase='vegetative',
        license_number=cultivation_license,
        last_modified_start=start_time,
        last_modified_end=end_time
    ))
    data['cultivation']['plants_modified'].extend(cultivation.get_plants(
        phase='flowering',
        license_number=cultivation_license,
        last_modified_start=start_time,
        last_modified_end=end_time
    ))
    print(f"  ✓ {len(data['cultivation']['plants_modified'])} modified plants")
    
    # Get modified packages from processing license
    print(f"Fetching modified packages ({processing_license})...")
    data['processing']['packages_modified'] = processing.get_packages(
        status='active',
        license_number=processing_license,
        last_modified_start=start_time,
        last_modified_end=end_time
    )
    print(f"  ✓ {len(data['processing']['packages_modified'])} modified packages")
    
    print("-" * 60)
    print("Pull complete!")
    
    # Save to JSON
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"metrc_changes_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"Data saved to: {filename}")
    
    return data

if __name__ == "__main__":
    import sys
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == '--recent':
            # Recent changes only
            hours = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            pull_recent_changes(hours=hours)
        else:
            # Full pull
            pull_current_data()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
