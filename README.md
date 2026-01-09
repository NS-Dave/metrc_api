# Metrc API Integration - Massachusetts (Production)

Python client for integrating with the Metrc (Marijuana Enforcement Tracking Reporting & Compliance) API for Massachusetts Cultivation and Processing licenses.

## Overview

This integration provides a complete Python client for the Metrc API v2, specifically configured for Massachusetts cannabis operations. It supports:

- **Cultivation Operations**: Plants, plant batches, harvests, strains
- **Processing Operations**: Packages, items, lab tests, transfers
- **Core Features**: Authentication, rate limiting, error handling, incremental syncing
- **Production Ready**: Configured with production credentials for live data access

## Prerequisites

- Python 3.8 or higher
- ✅ Metrc Software API Key (Integrator Key) - **Production**
- ✅ Metrc User API Key - **Production**
- ✅ Massachusetts Licenses:
  - **MC281599** (Cultivation) - Primary Focus
  - **MP281433** (Processing) - Primary Focus
  - MR283288, MR284733, MR281800 (Retail) - Out of Scope

## Installation

1. **Install required packages:**

```powershell
pip install requests urllib3
```

2. **Clone or download this directory** to your local machine

3. **Set up environment variables** (see Configuration section below)

## Configuration

### Environment Variables

Create environment variables for your API credentials. You can set these in PowerShell:

```powershell
# Required - API Credentials
$env:METRC_SOFTWARE_API_KEY = "your-software-api-key-here"
$env:METRC_USER_API_KEY = "user-api-key-here"

# Optional - Default License
$env:METRC_LICENSE_NUMBER = "MC123456"  # Your MA license number
$env:METRC_LICENSE_TYPE = "Cultivation"  # or "Processing"

# Optional - Configuration
$env:METRC_STATE = "MA"  # Default: MA
$env:METRC_TIMEOUT = "30"  # Request timeout in seconds
$env:METRC_LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
```

**For persistent environment variables**, add them to your system environment variables or create a `.env` file.

### Creating a .env File (Alternative)

Create a file named `.env` in the project directory:

```ini
METRC_SOFTWARE_API_KEY=your-software-api-key-here
METRC_USER_API_KEY=user-api-key-here
METRC_LICENSE_NUMBER=MC123456
METRC_LICENSE_TYPE=Cultivation
METRC_LOG_LEVEL=INFO
```

Then load it using python-dotenv:

```python
from dotenv import load_dotenv
load_dotenv()
```

## Quick Start

### 1. Test Your Connection

```python
from config import MetrcConfig
from client import MetrcClient

# Load configuration from environment
config = MetrcConfig.from_env()

# Create client
client = MetrcClient(config)

# Test connection
if client.test_connection():
    print("✓ Connected successfully!")
    
    # Get facilities
    facilities = client.get_facilities()
    for fac in facilities:
        print(f"Facility: {fac['Name']}")
        print(f"License: {fac['License']['Number']}")
```

### 2. Cultivation Operations

```python
from cultivation import CultivationClient

cultivation = CultivationClient(client)

# Get all active strains
strains = cultivation.get_strains()

# Get vegetative plants
veg_plants = cultivation.get_plants(phase='vegetative')

# Get flowering plants
flower_plants = cultivation.get_plants(phase='flowering')

# Get active harvests
harvests = cultivation.get_harvests(status='active')

# Get plant batches
batches = cultivation.get_plant_batches(status='active')
```

### 3. Processing Operations

```python
from processing import ProcessingClient

processing = ProcessingClient(client)

# Get active packages
packages = processing.get_packages(status='active')

# Get all items (products)
items = processing.get_items()

# Get locations
locations = processing.get_locations()

# Get incoming transfers
transfers = processing.get_incoming_transfers()
```

### 4. Incremental Data Sync

```python
from utils import DateUtils

# Get sync window (last 1 hour + 5 min buffer)
start_time, end_time = DateUtils.get_sync_window(hours=1, buffer_minutes=5)

# Get modified plants
modified_plants = cultivation.get_plants(
    phase='vegetative',
    last_modified_start=start_time,
    last_modified_end=end_time
)

# Get modified packages
modified_packages = processing.get_packages(
    status='active',
    last_modified_start=start_time,
    last_modified_end=end_time
)
```

## Project Structure

```
metrc_api/
├── config.py           # Configuration management and endpoint definitions
├── client.py           # Core API client with authentication and HTTP handling
├── cultivation.py      # Cultivation-specific operations
├── processing.py       # Processing-specific operations
├── utils.py            # Utility functions (dates, validation, transforms)
├── examples.py         # Usage examples and sample workflows
├── README.md           # This file
└── requirements.txt    # Python dependencies
```

## Core Modules

### config.py
- `MetrcConfig`: Configuration class
- `Endpoints`: API endpoint path constants
- `LicenseType`: License type constants

### client.py
- `MetrcClient`: Main API client
- `MetrcAPIError`: Base exception class
- HTTP methods: `get()`, `post()`, `put()`, `delete()`
- Helper: `get_with_last_modified()` for incremental syncs

### cultivation.py
- `CultivationClient`: Cultivation operations
- Strains, plant batches, plants, harvests
- Growth phase changes, harvesting, destruction

### processing.py
- `ProcessingClient`: Processing operations
- Packages, items, locations, transfers
- Package creation, adjustments, lab tests

### utils.py
- `DateUtils`: Date/time formatting and manipulation
- `ValidationUtils`: Data validation helpers
- `DataTransformUtils`: Data grouping and filtering
- `ErrorFormatter`: Error message formatting
- `RateLimiter`: Rate limiting helper

## Common Operations

### Creating Strains

```python
new_strains = [
    {
        "Name": "Blue Dream",
        "TestingStatus": "None",
        "ThcLevel": 0.18,
        "CbdLevel": 0.02,
        "IndicaPercentage": 20.0,
        "SativaPercentage": 80.0
    }
]

cultivation.create_strains(new_strains)
```

### Creating Plant Batches

```python
from utils import DateUtils

new_batch = [
    {
        "Name": "BD-Batch-001",
        "Type": "Clone",
        "Count": 25,
        "Strain": "Blue Dream",
        "Location": "Propagation Room",
        "Item": "Clone Item",
        "PatientLicenseNumber": None,
        "ActualDate": DateUtils.date_only(datetime.now())
    }
]

cultivation.create_plant_batches_from_packages(new_batch)
```

### Changing Growth Phase

```python
# Move plant batch to vegetative phase
changes = [
    {
        "Name": "BD-Batch-001",
        "Count": 25,
        "StartingTag": "1A4FF01000000220000000010",
        "GrowthPhase": "Vegetative",
        "NewLocation": "Veg Room A",
        "GrowthDate": DateUtils.date_only(datetime.now()),
        "PatientLicenseNumber": None
    }
]

cultivation.change_plant_batch_growth_phase(changes)
```

### Harvesting Plants

```python
harvests = [
    {
        "Plant": "1A4FF01000000220000000010",
        "Weight": 125.5,
        "UnitOfWeight": "Grams",
        "DryingLocation": "Drying Room A",
        "HarvestName": "Harvest-20251218",
        "PatientLicenseNumber": None,
        "ActualDate": DateUtils.date_only(datetime.now())
    }
]

cultivation.harvest_plants(harvests)
```

### Creating Packages from Harvest

```python
packages = [
    {
        "Tag": "1A4FF01000000220000000100",
        "Location": "Storage",
        "Item": "Flower - Blue Dream",
        "UnitOfWeight": "Ounces",
        "PatientLicenseNumber": None,
        "Note": "Batch BD-001",
        "IsProductionBatch": False,
        "ProductionBatchNumber": None,
        "IsTradeSample": False,
        "IsTestingSample": False,
        "ProductRequiresRemediation": False,
        "ActualDate": DateUtils.date_only(datetime.now()),
        "Ingredients": [
            {
                "HarvestId": 123,
                "HarvestName": "Harvest-20251218",
                "Weight": 16.0,
                "UnitOfWeight": "Ounces"
            }
        ]
    }
]

cultivation.create_harvest_packages(packages)
```

### Adjusting Package Quantities

```python
adjustments = [
    {
        "Label": "1A4FF01000000220000000100",
        "Quantity": -0.5,  # Negative for reduction
        "UnitOfMeasure": "Ounces",
        "AdjustmentReason": "Drying Loss",
        "AdjustmentDate": DateUtils.date_only(datetime.now()),
        "ReasonNote": "Normal moisture loss during curing"
    }
]

processing.adjust_packages(adjustments)
```

### Creating Items (Products)

```python
new_items = [
    {
        "ItemCategory": "Buds",
        "Name": "Blue Dream Flower - Premium",
        "UnitOfMeasure": "Ounces",
        "Strain": "Blue Dream",
        "UnitThcPercent": 18.5,
        "UnitCbdPercent": 2.0,
        "Description": "Premium indoor Blue Dream flower"
    }
]

processing.create_items(new_items)
```

## Data Analysis Examples

### Group Plants by Strain

```python
from utils import DataTransformUtils

plants = cultivation.get_plants(phase='vegetative')
by_strain = DataTransformUtils.group_by_strain(plants)

for strain, plant_list in by_strain.items():
    print(f"{strain}: {len(plant_list)} plants")
```

### Calculate Total Inventory

```python
packages = processing.get_packages(status='active')

inventory = {}
for pkg in packages:
    item_name = pkg['Item']['Name']
    quantity = pkg['Quantity']
    uom = pkg['UnitOfMeasureAbbreviation']
    
    key = f"{item_name} ({uom})"
    inventory[key] = inventory.get(key, 0) + quantity

for item, qty in inventory.items():
    print(f"{item}: {qty:.2f}")
```

## Error Handling

```python
from client import (
    MetrcAPIError,
    MetrcAuthenticationError,
    MetrcRateLimitError,
    MetrcValidationError
)

try:
    strains = cultivation.get_strains()
except MetrcAuthenticationError as e:
    print("Authentication failed - check API keys")
except MetrcRateLimitError as e:
    print("Rate limit exceeded - wait before retrying")
except MetrcValidationError as e:
    print(f"Validation error: {e}")
except MetrcAPIError as e:
    print(f"API error: {e}")
```

## Rate Limiting

The client includes built-in rate limiting. The default is 10 requests per second, but you can adjust:

```python
config = MetrcConfig.from_env()
config.requests_per_second = 5.0  # Slower rate

client = MetrcClient(config)
```

## Logging

All API calls are logged. Configure log level via environment variable or config:

```python
config = MetrcConfig.from_env()
config.log_level = "DEBUG"  # DEBUG, INFO, WARNING, ERROR
config.log_file = "metrc_api.log"

client = MetrcClient(config)
```

## Best Practices

### 1. Use Incremental Syncs
For scheduled jobs, use `lastModifiedStart` and `lastModifiedEnd` parameters to only fetch changed data:

```python
# Run hourly with 5-minute buffer
start, end = DateUtils.get_sync_window(hours=1, buffer_minutes=5)
modified = cultivation.get_plants(
    phase='vegetative',
    last_modified_start=start,
    last_modified_end=end
)
```

### 2. Batch Operations
When creating or updating multiple records, send them in batches:

```python
from utils import DataTransformUtils

items = [...] # Large list
batches = DataTransformUtils.paginate_list(items, page_size=100)

for batch in batches:
    cultivation.create_strains(batch)
```

### 3. Validate Before Submitting

```python
from utils import ValidationUtils

# Validate tag format
if not ValidationUtils.is_valid_tag(tag):
    print("Invalid tag format")

# Validate required fields
is_valid, missing = ValidationUtils.validate_required_fields(
    data,
    ['Name', 'Type', 'Count', 'Strain']
)
if not is_valid:
    print(f"Missing fields: {missing}")
```

### 4. Handle Multiple Licenses

```python
# Override license number per request
cultivation_license = "MC123456"
processing_license = "MF789012"

# Get data from cultivation license
plants = cultivation.get_plants(license_number=cultivation_license)

# Get data from processing license
packages = processing.get_packages(license_number=processing_license)
```

## Scheduled Automation

### Example: Hourly Sync Script

```python
# sync_metrc_data.py
import sys
from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from processing import ProcessingClient
from utils import DateUtils

def sync_data():
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    processing = ProcessingClient(client)
    
    # Get changes from last 65 minutes (1 hour + 5 min buffer)
    start, end = DateUtils.get_sync_window(hours=1, buffer_minutes=5)
    
    # Sync plants
    plants = cultivation.get_plants(
        phase='vegetative',
        last_modified_start=start,
        last_modified_end=end
    )
    print(f"Synced {len(plants)} modified plants")
    
    # Sync packages
    packages = processing.get_packages(
        status='active',
        last_modified_start=start,
        last_modified_end=end
    )
    print(f"Synced {len(packages)} modified packages")
    
    # TODO: Save to database

if __name__ == "__main__":
    try:
        sync_data()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
```

### Windows Task Scheduler

Create a batch file `run_sync.bat`:

```batch
@echo off
cd C:\python\metrc_api
python sync_metrc_data.py >> sync_log.txt 2>&1
```

Schedule it to run hourly using Task Scheduler.

## Troubleshooting

### Connection Issues

1. **401 Unauthorized**: Check API keys are correct
2. **403 Forbidden**: User doesn't have permission for resource
3. **404 Not Found**: Check endpoint URL and license number
4. **429 Rate Limited**: Reduce request frequency

### Common Errors

**"METRC_SOFTWARE_API_KEY must be set"**
- Set environment variables before running

**"Validation error: Row 0: Invalid strain name"**
- Ensure referenced resources (strains, locations, items) exist in Metrc

**"Request failed: Connection timeout"**
- Increase timeout in config: `config.timeout = 60`

## API Documentation

Official Metrc API documentation:
- **MA Production API**: https://api-ma.metrc.com
- **Documentation**: https://api-or.metrc.com/Documentation
- **Postman Collection**: Configured with production credentials in `Metrc API` collection

## Sandbox Evaluation Archive

All sandbox evaluation materials have been moved to `sandbox_evaluation/` directory for reference.

## License Types Reference

Massachusetts license prefixes:
- **MC**: Cultivation
- **MF**: Processing/Manufacturing
- **MR**: Retail
- **MT**: Testing Lab
- **MP**: Transportation

## Support and Resources

- **Metrc Support**: support@metrc.com
- **MA Cannabis Control Commission**: https://masscannabiscontrol.com
- **API Status**: Check Metrc Connect for system status

## Security Notes

- **Never commit API keys** to version control
- **Rotate keys regularly** through Metrc Connect
- **Use environment variables** or secure credential storage
- **Limit user API key permissions** to minimum required
- **Monitor API logs** for unusual activity

## Next Steps

1. ✅ Receive API credentials from Metrc
2. ✅ Set up environment variables
3. ✅ Run connection test (`examples.py`)
4. ✅ Verify facility access
5. ✅ Test read operations (get strains, plants, packages)
6. ✅ Plan data integration (database, BigQuery, etc.)
7. ✅ Set up scheduled syncs
8. ✅ Implement error notifications

## Questions?

This integration is ready to use once you receive your Metrc API credentials. The code is structured to be production-ready with proper error handling, rate limiting, and logging.

For questions about Metrc API functionality, refer to the official documentation or contact Metrc support.
