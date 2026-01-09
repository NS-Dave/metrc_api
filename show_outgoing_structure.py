import json
from transfer_sync_direction_aware import DirectionAwareTransferSync
from datetime import datetime, timedelta

sync = DirectionAwareTransferSync()

end_date = datetime.now()
start_date = end_date - timedelta(hours=23)

outgoing = sync.processing.get_outgoing_transfers(
    license_number='MP281433',
    last_modified_start=start_date.strftime('%Y-%m-%dT%H:%M:%S'),
    last_modified_end=end_date.strftime('%Y-%m-%dT%H:%M:%S')
)

if isinstance(outgoing, dict):
    outgoing = outgoing.get('Data', [])

if outgoing:
    print("Full first outgoing transfer object:")
    print(json.dumps(outgoing[0], indent=2, default=str))
