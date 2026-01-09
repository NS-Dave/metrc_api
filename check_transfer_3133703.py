import json
from transfer_sync_direction_aware import DirectionAwareTransferSync

sync = DirectionAwareTransferSync()

# The transfer you're looking at
transfer_id = 3133703

print("=" * 80)
print(f"TRANSFER {transfer_id} from /transfers/v2/outgoing")
print("=" * 80)

# First, let's see what we get from the outgoing endpoint
sync.connect_supabase()
cursor = sync.conn.cursor()
cursor.execute("""
    SELECT 
        manifest_number,
        destination_facility_name,
        destination_facility_license_number,
        transporter_facility_name,
        actual_arrival_datetime,
        actual_departure_datetime,
        shipment_type
    FROM metrc_transfers 
    WHERE id = %s AND direction = 'outgoing'
""", (transfer_id,))

result = cursor.fetchone()
if result:
    print("\nCurrently stored in database:")
    print(f"  Manifest: {result[0]}")
    print(f"  Destination Name: {result[1]}")
    print(f"  Destination License: {result[2]}")
    print(f"  Transporter: {result[3]}")
    print(f"  Actual Arrival: {result[4]}")
    print(f"  Actual Departure: {result[5]}")
    print(f"  Shipment Type: {result[6]}")

# Now fetch the deliveries for this transfer
print("\n" + "=" * 80)
print(f"DELIVERIES for transfer {transfer_id} from /transfers/v2/{transfer_id}/deliveries")
print("=" * 80)

url = f"/transfers/v2/{transfer_id}/deliveries"
deliveries_response = sync.processing.client.get(url, license_number='MC281599')

deliveries = None
if isinstance(deliveries_response, dict):
    deliveries = deliveries_response.get('Data', [])
elif isinstance(deliveries_response, list):
    deliveries = deliveries_response

if deliveries:
    print(f"\nFound {len(deliveries)} delivery/deliveries\n")
    for i, delivery in enumerate(deliveries):
        print(f"Delivery {i+1}:")
        print(json.dumps({
            'Id': delivery.get('Id'),
            'RecipientFacilityName': delivery.get('RecipientFacilityName'),
            'RecipientFacilityLicenseNumber': delivery.get('RecipientFacilityLicenseNumber'),
            'ShipmentTypeName': delivery.get('ShipmentTypeName'),
            'ShipmentTransactionType': delivery.get('ShipmentTransactionType'),
            'EstimatedDepartureDateTime': delivery.get('EstimatedDepartureDateTime'),
            'ActualDepartureDateTime': delivery.get('ActualDepartureDateTime'),
            'EstimatedArrivalDateTime': delivery.get('EstimatedArrivalDateTime'),
            'ActualArrivalDateTime': delivery.get('ActualArrivalDateTime'),
            'ReceivedDateTime': delivery.get('ReceivedDateTime'),
            'DeliveryPackageCount': delivery.get('DeliveryPackageCount'),
        }, indent=2))
