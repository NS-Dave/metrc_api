from transfer_sync_direction_aware import DirectionAwareTransferSync
import json

sync = DirectionAwareTransferSync()

# Fetch packages for delivery 3136503 (from transfer 3133703)
delivery_id = 3136503

detail = sync.processing.get_transfer_delivery(delivery_id, license_number='MC281599')
packages = None
if isinstance(detail, dict):
    packages = detail.get('Data', [])
elif isinstance(detail, list):
    packages = detail

if packages:
    print(f"Got {len(packages)} packages from delivery {delivery_id}")
    print("\nFirst package structure:")
    print(json.dumps(packages[0], indent=2))
