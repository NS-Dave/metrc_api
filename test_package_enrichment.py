from transfer_sync_direction_aware import DirectionAwareTransferSync
import json

sync = DirectionAwareTransferSync()

# Try to get full package details for one of the outgoing packages
package_id = 15552164  # From transfer 3133703
package_label = "1A40A030000C289000031366"

print(f"Attempting to fetch full details for package {package_id} ({package_label})")
print("This is an OUTGOING package from MC281599")
print("=" * 80)

try:
    url = f"/packages/v2/{package_id}"
    package_detail = sync.processing.client.get(url, license_number='MC281599')
    
    if package_detail:
        print("\nSUCCESS! Got package details:")
        print(json.dumps(package_detail, indent=2, default=str))
except Exception as e:
    print(f"\nFAILED: {e}")
