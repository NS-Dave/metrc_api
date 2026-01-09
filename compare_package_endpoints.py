from transfer_sync_direction_aware import DirectionAwareTransferSync
import json

sync = DirectionAwareTransferSync()

delivery_id = 3136503

print("Testing different package endpoints for delivery", delivery_id)
print("=" * 80)

# Try the non-wholesale endpoint
print("\n1. /transfers/v2/deliveries/{id}/packages (NO /wholesale):")
try:
    url = f"/transfers/v2/deliveries/{delivery_id}/packages"
    packages = sync.processing.client.get(url, license_number='MC281599')
    
    if isinstance(packages, dict):
        packages = packages.get('Data', [])
    
    if packages:
        print(f"   SUCCESS! Got {len(packages)} packages")
        print("\n   First package structure:")
        print(json.dumps(packages[0], indent=2, default=str))
    else:
        print("   No packages returned")
except Exception as e:
    print(f"   FAILED: {e}")

print("\n" + "=" * 80)
print("\n2. /transfers/v2/deliveries/{id}/packages/wholesale (current approach):")
try:
    packages = sync.processing.get_transfer_delivery(delivery_id, license_number='MC281599')
    
    if isinstance(packages, dict):
        packages = packages.get('Data', [])
    
    if packages:
        print(f"   SUCCESS! Got {len(packages)} packages")
        print("\n   First package structure:")
        print(json.dumps(packages[0], indent=2, default=str))
except Exception as e:
    print(f"   FAILED: {e}")
