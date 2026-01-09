from transfer_sync_direction_aware import DirectionAwareTransferSync
from datetime import datetime, timedelta

sync = DirectionAwareTransferSync()

# Fetch some transfers (24 hour window)
end_date = datetime.now()
start_date = end_date - timedelta(hours=23)

print("=" * 60)
print("OUTGOING TRANSFERS:")
print("=" * 60)

outgoing = sync.processing.get_outgoing_transfers(
    license_number='MP281433',
    last_modified_start=start_date.strftime('%Y-%m-%dT%H:%M:%S'),
    last_modified_end=end_date.strftime('%Y-%m-%dT%H:%M:%S')
)

if isinstance(outgoing, dict):
    outgoing = outgoing.get('Data', [])

print(f"Fetched {len(outgoing)} outgoing transfers")
for i, transfer in enumerate(outgoing[:2]):
    transfer_id = transfer.get('Id')
    delivery_id = transfer.get('DeliveryId')
    manifest = transfer.get('ManifestNumber')
    deliveries = transfer.get('Deliveries')
    print(f"\nTransfer {i+1}:")
    print(f"  ID: {transfer_id}")
    print(f"  Manifest: {manifest}")
    print(f"  DeliveryId: {delivery_id}")
    print(f"  Deliveries: {deliveries}")

print("\n" + "=" * 60)
print("INCOMING TRANSFERS:")
print("=" * 60)

incoming = sync.processing.get_incoming_transfers(
    license_number='MP281433',
    last_modified_start=start_date.strftime('%Y-%m-%dT%H:%M:%S'),
    last_modified_end=end_date.strftime('%Y-%m-%dT%H:%M:%S')
)

if isinstance(incoming, dict):
    incoming = incoming.get('Data', [])

print(f"Fetched {len(incoming)} incoming transfers")
for i, transfer in enumerate(incoming[:2]):
    transfer_id = transfer.get('Id')
    delivery_id = transfer.get('DeliveryId')
    manifest = transfer.get('ManifestNumber')
    deliveries = transfer.get('Deliveries')
    print(f"\nTransfer {i+1}:")
    print(f"  ID: {transfer_id}")
    print(f"  Manifest: {manifest}")
    print(f"  DeliveryId: {delivery_id}")
    print(f"  Deliveries: {deliveries}")
