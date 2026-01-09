import json
from transfer_sync_direction_aware import DirectionAwareTransferSync

sync = DirectionAwareTransferSync()

# Try to get deliveries for an outgoing transfer
transfer_id = 3134527

print(f"Getting deliveries for outgoing transfer {transfer_id}...")

try:
    # Using the client directly
    url = f"/transfers/v2/{transfer_id}/deliveries"
    deliveries = sync.processing.client.get(url, license_number='MP281433')
    
    if isinstance(deliveries, dict):
        deliveries = deliveries.get('Data', [])
    
    print(f"Found {len(deliveries)} deliveries")
    
    if deliveries:
        print("\nFirst delivery:")
        print(json.dumps(deliveries[0], indent=2, default=str))
        
        delivery_id = deliveries[0].get('Id')
        if delivery_id:
            print(f"\nNow getting packages for delivery {delivery_id}...")
            packages = sync.processing.get_transfer_delivery(delivery_id, license_number='MP281433')
            if isinstance(packages, dict):
                packages = packages.get('Data', [])
            print(f"Found {len(packages)} packages")
            
except Exception as e:
    print(f"Error: {e}")
