# Metrc API Integration - AI Agent Instructions

## Project Overview
This is a **production Python data pipeline** syncing Massachusetts cannabis tracking data from Metrc API to Supabase PostgreSQL warehouse. It supports two live licenses: **MC281599 (Cultivation)** and **MP281433 (Processing)**.

## Architecture

```
Metrc API (rate-limited) → Daily sync scripts → Supabase (PostgreSQL)
                                                    ↓
                                            Fast queries (<1s vs 2-5 min API calls)
```

**Key pattern**: Never query Metrc API repeatedly for analysis—sync to Supabase first, then query the warehouse.

### Core Modules
- **`client.py`**: Base HTTP client with auth, rate limiting, retry logic. All API calls go through `MetrcClient`.
- **`cultivation.py`**: Wraps cultivation endpoints (plants, harvests, strains, plant_batches). Uses `CultivationClient(MetrcClient)`.
- **`processing.py`**: Wraps processing endpoints (packages, items, transfers, lab tests). Uses `ProcessingClient(MetrcClient)`.
- **`config.py`**: Environment-based config (`MetrcConfig.from_env()`). Contains `Endpoints` class with all API paths.
- **`supabase_config.py`**: DB connection strings. Requires `SUPABASE_PASSWORD` env var.
- **`metrc_daily_sync.py`**: Main production sync script. Runs daily via Windows Task Scheduler at 6 AM.

### Data Flow Patterns
1. **Incremental sync**: Use `last_modified_start/end` params to pull 48-hour windows (harvests, packages)
2. **Directional transfers**: Same transfer ID can be both incoming AND outgoing—always track `direction` column
3. **Package enrichment**: Transfer packages are minimal; enrich via `/packages/v2/{id}` for full details
4. **Full API response storage**: All records store raw JSON in `data` JSONB column for flexibility

## Critical Conventions

### Environment Variables (Required)
```powershell
$env:METRC_SOFTWARE_API_KEY = "..."  # Integrator key
$env:METRC_USER_API_KEY = "..."      # User key
$env:SUPABASE_PASSWORD = "..."       # DB password
$env:METRC_LICENSE_CULTIVATION = "MC281599"
$env:METRC_LICENSE_PROCESSING = "MP281433"
```

### License Handling
**Always specify license_number explicitly**—don't rely on config defaults. Each API call requires the correct license (cultivation or processing).

### Date Formats
- Metrc expects **ISO 8601** with timezone: `2024-01-15T00:00:00-05:00`
- Use `DateUtils.to_iso()` for conversions
- Use `DateUtils.get_sync_window(hours=48)` for incremental syncs

### Error Handling
All custom exceptions inherit from `MetrcAPIError`:
- `MetrcAuthenticationError`: Check API keys
- `MetrcRateLimitError`: Retry with exponential backoff
- `MetrcValidationError`: Check request payload format

## Common Workflows

### Running Daily Sync
```powershell
python metrc_daily_sync.py
```
This syncs: harvests (48hr), packages (48hr), transfers (7d), plants (full), plant_batches (full).

### Windows Task Scheduler Setup
Production sync runs daily at 6 AM via Task Scheduler:
```powershell
# Create scheduled task
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\python\metrc_api\metrc_daily_sync.py" -WorkingDirectory "C:\python\metrc_api"
$trigger = New-ScheduledTaskTrigger -Daily -At 6am
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "Metrc Daily Sync" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

View task status:
```powershell
Get-ScheduledTask -TaskName "Metrc Daily Sync"
Get-ScheduledTaskInfo -TaskName "Metrc Daily Sync"
```

### Query Supabase (Fast)
```python
from supabase_config import get_connection_string
import psycopg2

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()
cursor.execute("SELECT * FROM harvest_reconciliation LIMIT 10")
```

### Fetch Fresh Data from Metrc (Slow)
```python
from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient

config = MetrcConfig.from_env()
client = MetrcClient(config)
cultivation = CultivationClient(client)

harvests = cultivation.get_harvests(status='active', license_number='MC281599')
```

### Backfill Historical Data
Use `last_modified_start/end` to pull date ranges:
```python
from datetime import datetime, timedelta

start = datetime(2024, 1, 1)
end = datetime(2024, 12, 31)
packages = processing.get_packages('inactive', start, end, 'MP281433')
```

## Database Schema Patterns

### Tables
- **`metrc_harvests`**: Harvest tracking (harvest_name is unique identifier, NOT id)
- **`metrc_packages`**: Package inventory (label is unique, id can change)
- **`metrc_plant_batches`**: Clone/seed batches
- **`metrc_plants`**: Individual plants (vegetative, flowering, on-hold)
- **`metrc_transfers`**: Manifests with direction (incoming/outgoing)
- **`metrc_sync_log`**: Tracks all sync operations

### Important Views
- **`harvest_reconciliation`**: Pre-joined harvest→packages weight discrepancies (see note below)

### Key Columns
- `source_harvest_names`: JSONB array linking packages to harvests (use `@>` operator for queries)
- `data`: Full Metrc API response (JSONB)
- `direction`: 'incoming' or 'outgoing' for transfers (critical—same ID can exist as both)

## Harvest Reconciliation (Major Use Case - IN PROGRESS)

**Goal**: Track where harvested cannabis weight goes—consumed in packages, sold in transfers, or discrepancies.

**Current State**: The reconciliation views and scripts exist but are **not producing adequate results**. The system attempts to:
- Match harvest weights to downstream package weights
- Identify "simple" packages (single source harvest) vs "complex" packages (multiple source harvests)
- Calculate discrepancies between harvest weight and total package weight
- Export to Excel for manual review ([export_harvest_reconciliation.py](export_harvest_reconciliation.py))

**Known Issues**:
- Weight allocation logic for complex packages is incomplete
- Discrepancy calculations need validation
- Manual review workflow is cumbersome

**Related Files**:
- [harvest_reconciliation_views.sql](harvest_reconciliation_views.sql) - SQL views (may need revision)
- [HARVEST_RECONCILIATION_README.md](HARVEST_RECONCILIATION_README.md) - Documentation of intended workflow
- [harvest_reconciliation_supabase.py](harvest_reconciliation_supabase.py), [export_harvest_reconciliation.py](export_harvest_reconciliation.py)

When working on harvest reconciliation improvements, focus on validating the weight tracking logic before implementing UI/export features.

## Gotchas

1. **Harvest name vs ID**: Use `HarvestName` (e.g., "H0001") as primary key, not API `Id` (changes over time)
2. **Package label uniqueness**: Package `Label` is the true identifier, not `Id`
3. **Transfer deduplication**: Dedupe by `(id, license_number, direction)`, NOT just `id`
4. **Pagination**: Metrc API doesn't paginate—returns all results in single response
5. **Rate limits**: ~10 req/sec. Client handles this with `requests_per_second` throttling
6. **Schema evolution**: Many `.sql` migration files exist—check `MIGRATION_PLAN.md` before altering schema

## Testing
- **`simple_test.py`**: Basic connection test
- **`test_*.py`**: Specific endpoint/feature tests
- **`check_*.py`**: Schema and data integrity validators

## Documentation Files
- **`README.md`**: General setup and usage
- **`SUPABASE_INTEGRATION_SUMMARY.md`**: Warehouse architecture
- **`MIGRATION_PLAN.md`**: Schema evolution strategy
- **`SCHEDULED_TASKS_BREAKDOWN.md`**: Production sync schedule details

## When Making Changes

1. **New endpoints**: Add to `Endpoints` class in [config.py](config.py), implement in [cultivation.py](cultivation.py) or [processing.py](processing.py)
2. **Schema changes**: Create numbered `.sql` migration file, update `MIGRATION_PLAN.md`
3. **New sync types**: Extend `MetrcSupabaseSync` class in [metrc_daily_sync.py](metrc_daily_sync.py)
4. **Testing**: Create `test_*.py` or `check_*.py` script, don't modify production sync directly
