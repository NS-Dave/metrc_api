# Metrc API Quick Reference

## Setup Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Set environment variables (METRC_SOFTWARE_API_KEY, METRC_USER_API_KEY)
- [ ] Run connection test: `python test_connection.py`
- [ ] Review examples: `python examples.py`

## Common Commands

### Test Connection
```python
python test_connection.py
```

### Run Examples
```python
python examples.py
```

## Quick Code Snippets

### Initialize Client
```python
from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from processing import ProcessingClient

config = MetrcConfig.from_env()
client = MetrcClient(config)
cultivation = CultivationClient(client)
processing = ProcessingClient(client)
```

### Get Data
```python
# Strains
strains = cultivation.get_strains()

# Plants
veg_plants = cultivation.get_plants(phase='vegetative')
flower_plants = cultivation.get_plants(phase='flowering')

# Packages
packages = processing.get_packages(status='active')

# Harvests
harvests = cultivation.get_harvests(status='active')

# Items
items = processing.get_items()

# Locations
locations = processing.get_locations()
```

### Incremental Sync
```python
from utils import DateUtils

# Last hour with 5-min buffer
start, end = DateUtils.get_sync_window(hours=1, buffer_minutes=5)

# Get modified data
plants = cultivation.get_plants(
    phase='vegetative',
    last_modified_start=start,
    last_modified_end=end
)
```

### Create Operations
```python
from utils import DateUtils
from datetime import datetime

# Create strain
cultivation.create_strains([{
    "Name": "Strain Name",
    "TestingStatus": "None",
    "ThcLevel": 0.20,
    "CbdLevel": 0.05,
    "IndicaPercentage": 60.0,
    "SativaPercentage": 40.0
}])

# Create plant batch
cultivation.create_plant_batches_from_packages([{
    "Name": "Batch Name",
    "Type": "Clone",
    "Count": 25,
    "Strain": "Strain Name",
    "Location": "Location Name",
    "Item": "Item Name",
    "PatientLicenseNumber": None,
    "ActualDate": DateUtils.date_only(datetime.now())
}])

# Change growth phase
cultivation.change_plant_batch_growth_phase([{
    "Name": "Batch Name",
    "Count": 25,
    "StartingTag": "1A4FF01000000220000000010",
    "GrowthPhase": "Vegetative",
    "NewLocation": "Veg Room A",
    "GrowthDate": DateUtils.date_only(datetime.now()),
    "PatientLicenseNumber": None
}])

# Harvest plants
cultivation.harvest_plants([{
    "Plant": "1A4FF01000000220000000010",
    "Weight": 125.5,
    "UnitOfWeight": "Grams",
    "DryingLocation": "Drying Room",
    "HarvestName": "Harvest-001",
    "PatientLicenseNumber": None,
    "ActualDate": DateUtils.date_only(datetime.now())
}])

# Create package from harvest
cultivation.create_harvest_packages([{
    "Tag": "1A4FF01000000220000000100",
    "Location": None,
    "Item": "Item Name",
    "UnitOfWeight": "Ounces",
    "PatientLicenseNumber": None,
    "Note": "",
    "IsProductionBatch": False,
    "ProductionBatchNumber": None,
    "IsTradeSample": False,
    "IsTestingSample": False,
    "ProductRequiresRemediation": False,
    "ActualDate": DateUtils.date_only(datetime.now()),
    "Ingredients": [{
        "HarvestId": 123,
        "HarvestName": "Harvest-001",
        "Weight": 16.0,
        "UnitOfWeight": "Ounces"
    }]
}])

# Adjust package quantity
processing.adjust_packages([{
    "Label": "1A4FF01000000220000000100",
    "Quantity": -0.5,
    "UnitOfMeasure": "Ounces",
    "AdjustmentReason": "Drying Loss",
    "AdjustmentDate": DateUtils.date_only(datetime.now()),
    "ReasonNote": "Normal curing loss"
}])

# Create item
processing.create_items([{
    "ItemCategory": "Buds",
    "Name": "Product Name",
    "UnitOfMeasure": "Ounces",
    "Strain": "Strain Name",
    "UnitThcPercent": 18.5,
    "UnitCbdPercent": 2.0,
    "Description": "Product description"
}])
```

### Data Analysis
```python
from utils import DataTransformUtils

# Group by strain
plants = cultivation.get_plants(phase='vegetative')
by_strain = DataTransformUtils.group_by_strain(plants)

for strain, plant_list in by_strain.items():
    print(f"{strain}: {len(plant_list)} plants")

# Calculate totals
packages = processing.get_packages(status='active')
total_qty = DataTransformUtils.sum_quantities(packages, 'Quantity')
```

### Error Handling
```python
from client import (
    MetrcAPIError,
    MetrcAuthenticationError,
    MetrcRateLimitError,
    MetrcValidationError
)

try:
    result = cultivation.get_strains()
except MetrcAuthenticationError:
    print("Check API keys")
except MetrcRateLimitError:
    print("Rate limited - wait and retry")
except MetrcValidationError as e:
    print(f"Validation error: {e}")
except MetrcAPIError as e:
    print(f"API error: {e}")
```

## Key Endpoints

### Cultivation
- Strains: `get_strains()`, `create_strains()`, `update_strains()`
- Plant Batches: `get_plant_batches()`, `create_plant_batches_from_packages()`
- Plants: `get_plants()`, `move_plants()`, `change_plant_growth_phase()`
- Harvests: `get_harvests()`, `harvest_plants()`, `create_harvest_packages()`

### Processing
- Packages: `get_packages()`, `create_packages()`, `adjust_packages()`
- Items: `get_items()`, `create_items()`, `update_items()`
- Locations: `get_locations()`, `create_locations()`
- Transfers: `get_incoming_transfers()`, `get_outgoing_transfers()`
- Lab Tests: `get_lab_test_results()`, `record_lab_test_results()`

## Utilities

### Date Utils
```python
DateUtils.now_iso()  # Current time in ISO 8601
DateUtils.date_only(datetime.now())  # YYYY-MM-DD
DateUtils.days_ago(7)  # 7 days ago
DateUtils.get_sync_window(hours=1, buffer_minutes=5)  # For incremental syncs
```

### Validation Utils
```python
ValidationUtils.is_valid_tag("1A4FF01000000220000000010")
ValidationUtils.is_valid_license("MC123456")
ValidationUtils.validate_weight(100.5)
ValidationUtils.validate_required_fields(data, ['Name', 'Type'])
```

### Data Transform Utils
```python
DataTransformUtils.paginate_list(items, page_size=100)
DataTransformUtils.filter_by_strain(items, "Blue Dream")
DataTransformUtils.group_by_strain(items)
DataTransformUtils.sum_quantities(items)
DataTransformUtils.convert_weight(16, 'Ounces', 'Grams')
```

## License Number Formats (Massachusetts)

- **MC######** - Cultivation
- **MF######** - Processing/Manufacturing  
- **MR######** - Retail
- **MT######** - Testing Lab
- **MP######** - Transportation

## Important Notes

1. **Authentication**: Uses Basic Auth with Base64 encoding
2. **Date Format**: ISO 8601 (YYYY-MM-DDTHH:MM:SS±HH:MM)
3. **Rate Limiting**: Built into client (default 10 req/sec)
4. **Incremental Sync**: Use `lastModifiedStart` and `lastModifiedEnd`
5. **Batch Operations**: Can send multiple items in single request
6. **Tags**: 24-character alphanumeric identifiers

## Troubleshooting

| Error | Solution |
|-------|----------|
| 401 Unauthorized | Check API keys |
| 403 Forbidden | Check user permissions |
| 404 Not Found | Verify license number and endpoint |
| 429 Rate Limited | Reduce request frequency |
| 400 Validation | Check required fields and data format |

## Next Steps After Credentials

1. Set environment variables
2. Run `python test_connection.py`
3. Explore with `python examples.py`
4. Test read operations (get methods)
5. Plan data storage (database/BigQuery)
6. Implement scheduled syncs
7. Set up error monitoring

## Support

- Metrc Documentation: https://api-or.metrc.com/Documentation
- Metrc Support: support@metrc.com
- MA CCC: https://masscannabiscontrol.com
