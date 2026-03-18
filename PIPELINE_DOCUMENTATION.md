# Cultivation & Manufacturing Pipeline Documentation

**Pipeline Name:** METRC API Integration
**Location:** `C:\python\metrc_api`
**Data Source:** METRC API (Massachusetts Cannabis Compliance System)
**Data Destination:** Supabase PostgreSQL (Cloud Data Warehouse)
**Schedule:** Daily at 6:00 AM via Windows Task Scheduler

---

## 1. Overview

This pipeline synchronizes cultivation and manufacturing data from the METRC (Marijuana Enforcement Tracking Reporting & Compliance) system into a Supabase PostgreSQL data warehouse. METRC is the state-mandated cannabis tracking system for Massachusetts.

### Key Capabilities
- Multi-license support (Cultivation MC281599, Processing MP281433)
- Incremental sync with 48-hour lookback window
- Full plant lifecycle tracking (seed to sale)
- Package history tracking (SCD Type 2 pattern)
- Harvest reconciliation with discrepancy detection
- Transfer tracking (incoming/outgoing)
- 200x query performance improvement over live API

### Business Context
- **Cultivation License (MC281599)**: Tracks plants, harvests, batches
- **Processing License (MP281433)**: Tracks packages, items, transfers
- **State Requirement**: All cannabis businesses in Massachusetts must use METRC

---

## 2. Architecture

### Directory Structure

```
C:\python\metrc_api\
│
├── Core API Modules
│   ├── config.py              # Configuration & API endpoints
│   ├── client.py              # HTTP client with auth & rate limiting
│   ├── cultivation.py         # Cultivation operations
│   ├── processing.py          # Processing/manufacturing operations
│   ├── utils.py               # Utilities (date, validation, transform)
│   └── __init__.py            # Package exports
│
├── Database Integration
│   ├── supabase_config.py     # Database connection config
│   ├── package_history.py     # Change tracking (SCD2)
│   └── *.sql                  # Schema and views
│
├── Sync Scripts
│   ├── metrc_daily_sync.py    # Primary daily sync (1,402 lines)
│   ├── metrc_historical_backfill.py  # Historical data population
│   ├── metrc_reference_data_sync.py  # Facilities, strains, items
│   ├── sync_plants.py         # Plant-specific sync
│   └── sync_missing_packages.py      # Gap filling
│
├── Analysis & Reporting
│   ├── harvest_reconciliation_supabase.py  # Fast reconciliation
│   ├── export_harvest_reconciliation.py    # Excel export
│   └── harvest_recon_tool.py  # CLI reconciliation tool
│
├── Configuration
│   ├── .env.example           # Environment template
│   └── requirements.txt       # Python dependencies
│
├── Logs
│   └── metrc_api.log          # API call logs (40+ MB)
│
└── Documentation
    ├── README.md              # Main documentation
    ├── QUICK_REFERENCE.md     # Command reference
    └── *.md                   # Additional docs
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Windows Task Scheduler                        │
│                    (Daily @ 6:00 AM)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  metrc_daily_sync.py │
                  │  (Orchestrator)      │
                  └──────────┬───────────┘
                             │
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ config.py    │  │ client.py    │  │ supabase_    │
    │ (Settings)   │  │ (HTTP/Auth)  │  │ config.py    │
    └──────────────┘  └──────┬───────┘  └──────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
       ┌──────────────┐             ┌──────────────┐
       │ cultivation  │             │ processing   │
       │    .py       │             │    .py       │
       │              │             │              │
       │ - Plants     │             │ - Packages   │
       │ - Batches    │             │ - Items      │
       │ - Harvests   │             │ - Transfers  │
       │ - Strains    │             │ - Lab Tests  │
       └──────┬───────┘             └──────┬───────┘
              │                             │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │        METRC API            │
              │  (https://api-ma.metrc.com) │
              │                             │
              │  Rate: 10 req/sec           │
              │  Auth: HTTP Basic           │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │   Supabase PostgreSQL       │
              │   (Data Warehouse)          │
              │                             │
              │  Tables:                    │
              │  - metrc_harvests           │
              │  - metrc_packages           │
              │  - metrc_plants             │
              │  - metrc_transfers          │
              │  - metrc_packages_history   │
              │  - metrc_sync_log           │
              └─────────────────────────────┘
```

---

## 3. Data Flow

### Daily Sync Process

```
1. INITIALIZATION
   └── Load config from environment
   └── Initialize Metrc API clients (cultivation + processing)
   └── Initialize Supabase connection
   └── Log sync start to metrc_sync_log

2. CULTIVATION LICENSE (MC281599)
   └── Sync Harvests (last 48 hours)
   └── Sync Packages (last 48 hours)
   └── Sync Transfers (last 7 days)
   └── Sync Plants (full snapshot)
   └── Sync Plant Batches (full snapshot)
       ├── Capture package history before updates
       ├── Upsert to database
       └── Log records pulled/inserted/updated

3. PROCESSING LICENSE (MP281433)
   └── Sync Packages (last 48 hours)
   └── Sync Transfers (last 7 days)
   └── (Plants skipped - no cultivation access)

4. COMPLETION
   └── Log sync completion
   └── Close connections
```

### Data Transformation Pipeline

```
METRC API Response
       │
       ▼
┌──────────────────────────────────────┐
│ Data Extraction (JSON → Python)      │
│ - Parse API response                 │
│ - Extract Data array                 │
│ - Handle pagination                  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Field Mapping & Normalization        │
│ - Map Metrc fields to DB columns     │
│ - Convert dates to ISO 8601          │
│ - Normalize weights/quantities       │
│ - Link relationships (harvest→pkg)   │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ History Capture (SCD2)               │
│ - Detect field changes               │
│ - Record previous state              │
│ - Create history entry               │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Database Upsert                      │
│ - Insert new records                 │
│ - Update existing records            │
│ - Preserve raw JSONB data            │
└──────────────────────────────────────┘
```

---

## 4. METRC API Integration

### API Details

| Setting | Value |
|---------|-------|
| **Base URL** | `https://api-ma.metrc.com` |
| **API Version** | v2 |
| **Authentication** | HTTP Basic Auth |
| **Rate Limit** | 10 requests/second (client-enforced) |
| **Timeout** | 30 seconds |

### Key Endpoints

| Category | Endpoint | Description |
|----------|----------|-------------|
| **Strains** | `/strains/v2/active` | Strain definitions |
| **Plant Batches** | `/plantbatches/v2/active` | Batch tracking |
| **Plants** | `/plants/v2/vegetative` | Vegetative plants |
| **Plants** | `/plants/v2/flowering` | Flowering plants |
| **Harvests** | `/harvests/v2/active` | Active harvests |
| **Packages** | `/packages/v2/active` | Active inventory |
| **Packages** | `/packages/v2/transferred` | Sold/transferred |
| **Transfers** | `/transfers/v2/incoming` | Inbound transfers |
| **Transfers** | `/transfers/v2/outgoing` | Outbound transfers |
| **Items** | `/items/v2/active` | Product definitions |
| **Facilities** | `/facilities/v2` | Licensed facilities |

### Authentication

```python
# Credentials from environment
METRC_SOFTWARE_API_KEY = "..."  # From Metrc Connect
METRC_USER_API_KEY = "..."      # User-specific key

# Header construction
credentials = base64.encode(f"{SOFTWARE_KEY}:{USER_KEY}")
headers = {"Authorization": f"Basic {credentials}"}
```

---

## 5. Database Schema

### Supabase Connection

| Setting | Value |
|---------|-------|
| **Host** | `aws-1-us-east-2.pooler.supabase.com` |
| **Port** | 6543 (pooler) |
| **Database** | postgres |
| **User** | `postgres.kacquxbizuqgsslnubdy` |

### Core Tables

| Table | Records | Description |
|-------|---------|-------------|
| `metrc_harvests` | 317+ | Harvest tracking |
| `metrc_packages` | 15,421+ | Package inventory |
| `metrc_plants` | 768+ | Individual plants |
| `metrc_plant_batches` | varies | Plant batch tracking |
| `metrc_transfers` | 3,803+ | Transfer manifests |
| `metrc_transfer_packages` | varies | Transfer line items |
| `metrc_packages_history` | 296K/yr | Change tracking (SCD2) |
| `metrc_sync_log` | varies | Execution audit log |

### Key Views

| View | Purpose |
|------|---------|
| `v_harvest_reconciliation` | Master reconciliation metrics |
| `v_harvests_needing_review` | Flagged discrepancies |
| `v_complex_packages_detail` | Multi-source packages |
| `v_package_categorization` | Simple vs complex classification |

### Data Storage Strategy

**JSONB Column:**
- Raw API response stored in `data` column
- Preserves all fields for flexibility
- Enables audit trail and recovery

**Relational Columns:**
- Key fields extracted for fast querying
- Proper indexes on common filters
- Foreign key relationships

---

## 6. Configuration

### Environment Variables

```bash
# Metrc API Credentials (Required)
METRC_SOFTWARE_API_KEY=your_software_key
METRC_USER_API_KEY=your_user_key

# Database (Required)
SUPABASE_PASSWORD=your_password

# License Numbers (Optional - defaults in config.py)
METRC_LICENSE_CULTIVATION=MC281599
METRC_LICENSE_PROCESSING=MP281433

# API Settings (Optional)
METRC_STATE=MA
METRC_TIMEOUT=30
METRC_LOG_LEVEL=INFO
```

### config.py Settings

```python
# State-specific configuration
BASE_URL = "https://api-ma.metrc.com"
STATE = "MA"

# License numbers
LICENSE_CULTIVATION = "MC281599"
LICENSE_PROCESSING = "MP281433"

# Rate limiting
MAX_REQUESTS_PER_SECOND = 10
REQUEST_TIMEOUT = 30
```

---

## 7. Scheduling

### Windows Task Scheduler

| Setting | Value |
|---------|-------|
| **Task Name** | `metrc_sync` |
| **Location** | `\Automation\metrc_sync` |
| **Script** | `metrc_daily_sync.py` |
| **Schedule** | Daily at 6:00 AM |
| **Status** | Active |

### Sync Windows

| Data Type | Window | Frequency |
|-----------|--------|-----------|
| Harvests | Last 48 hours | Daily |
| Packages | Last 48 hours | Daily |
| Transfers | Last 7 days | Daily |
| Plants | Full snapshot | Daily |
| Plant Batches | Full snapshot | Daily |
| Reference Data | Full snapshot | Weekly (manual) |

### Manual Execution

```bash
# Full daily sync
python metrc_daily_sync.py

# Historical backfill
python metrc_historical_backfill.py

# Reference data only
python metrc_reference_data_sync.py

# Plant sync only
python sync_plants.py

# Connection test
python simple_test.py
```

---

## 8. Key Scripts

### metrc_daily_sync.py (Primary)
**Lines:** 1,402
**Purpose:** Main daily sync orchestrator

**Key Methods:**
- `sync_harvests_incremental()` - Last 48 hours
- `sync_packages_incremental()` - Last 48 hours
- `sync_transfers_incremental()` - Last 7 days
- `sync_plants()` - Full snapshot
- `sync_plant_batches()` - Full snapshot

### client.py (Core HTTP Client)
**Lines:** 426
**Purpose:** HTTP client with auth, rate limiting, retry

**Key Features:**
- HTTP Basic Auth
- Rate limiting (10 req/sec)
- Automatic retry with exponential backoff
- 5 custom exception types

### cultivation.py (Cultivation Operations)
**Lines:** 512
**Purpose:** Cultivation-specific API operations

**Entities:**
- Strains, Plant Batches, Plants, Harvests

### processing.py (Processing Operations)
**Lines:** 525
**Purpose:** Processing/manufacturing API operations

**Entities:**
- Packages, Items, Locations, Transfers, Lab Tests

### package_history.py (Change Tracking)
**Purpose:** SCD Type 2 history tracking

**Key Functions:**
- `detect_changes()` - Field comparison
- `capture_history_before_update()` - Pre-update snapshot
- `create_initial_history_entry()` - First entry

---

## 9. Harvest Reconciliation

### Purpose
Track weight accountability from harvest through packaging to sale.

### Package Classification

| Type | Definition | Reconciliation |
|------|------------|----------------|
| **Simple** | Single source harvest | Automatic |
| **Complex** | Multiple source harvests | Manual review |

### Discrepancy Detection

```sql
-- Harvest reconciliation view calculates:
- Total harvested weight
- Total packaged weight
- Total sold weight
- Active package weight
- Discrepancy (harvested - packaged - waste)
```

### Reconciliation Tools

| Script | Purpose |
|--------|---------|
| `harvest_reconciliation_supabase.py` | Fast DB-based reconciliation |
| `export_harvest_reconciliation.py` | Excel export with detail |
| `harvest_recon_tool.py` | CLI for quick checks |

---

## 10. Package History Tracking

### SCD Type 2 Pattern

The system tracks all package state changes:

```
┌──────────────────────────────────────────────────────────┐
│ Package: 1A400030000A...                                 │
├──────────────────────────────────────────────────────────┤
│ 2025-01-01 09:00 │ CREATED     │ qty: 100 │ Active      │
│ 2025-01-05 14:30 │ QTY_CHANGE  │ qty: 85  │ Active      │
│ 2025-01-10 11:00 │ QTY_CHANGE  │ qty: 70  │ Active      │
│ 2025-01-15 16:45 │ STATUS      │ qty: 70  │ Transferred │
└──────────────────────────────────────────────────────────┘
```

### History Table Schema

| Column | Description |
|--------|-------------|
| `id` | History entry ID |
| `package_id` | Package reference |
| `change_type` | created, state_change, quantity_change, updated |
| `quantity` | Quantity at this point |
| `status` | Package status |
| `valid_from` | When this state began |
| `valid_to` | When this state ended (null if current) |

### Query Functions

```sql
-- Get package timeline
SELECT * FROM get_package_timeline('package_id');

-- Get package state at specific time
SELECT * FROM get_package_state_at('package_id', '2025-01-10');
```

---

## 11. Logging & Monitoring

### Log Files

| File | Purpose | Size |
|------|---------|------|
| `metrc_api.log` | API call logs | 40+ MB |

### Log Format
```
2025-01-30 06:00:15 - metrc_api - INFO - Starting daily sync
2025-01-30 06:00:16 - metrc_api - DEBUG - GET /harvests/v2/active
2025-01-30 06:00:17 - metrc_api - INFO - Fetched 25 harvests
```

### Database Audit Log (metrc_sync_log)

| Column | Description |
|--------|-------------|
| `entity_type` | harvests, packages, transfers, plants |
| `license_number` | MC281599, MP281433 |
| `sync_type` | incremental, backfill |
| `sync_start/end` | Timestamps |
| `records_pulled` | API count |
| `records_inserted` | New records |
| `records_updated` | Updated records |
| `status` | running, completed, failed |
| `error_message` | Error details |

### Monitoring Queries

```sql
-- Recent sync history
SELECT entity_type, license_number, sync_start,
       records_pulled, records_inserted, status
FROM metrc_sync_log
ORDER BY sync_start DESC
LIMIT 20;

-- Failed syncs
SELECT * FROM metrc_sync_log
WHERE status = 'failed'
ORDER BY sync_start DESC;
```

---

## 12. Error Handling

### Exception Types

| Exception | Cause | Recovery |
|-----------|-------|----------|
| `MetrcAuthenticationError` | Invalid credentials | Check API keys |
| `MetrcRateLimitError` | Rate limit exceeded | Auto-retry with backoff |
| `MetrcValidationError` | Invalid request data | Fix payload |
| `MetrcAPIError` | API error response | Check error message |
| `MetrcConnectionError` | Network failure | Auto-retry |

### Retry Logic

```python
# Automatic retry with exponential backoff
# Attempt 1: Immediate
# Attempt 2: 1 second delay
# Attempt 3: 2 second delay
# Attempt 4: 4 second delay
# Attempt 5: Fail
```

---

## 13. Dependencies

### requirements.txt

```
requests>=2.31.0          # HTTP client
urllib3>=2.0.0            # URL handling
python-dotenv>=1.0.0      # Environment management
psycopg2-binary           # PostgreSQL adapter
```

### External Services

| Service | Purpose |
|---------|---------|
| METRC API | Source data (Massachusetts) |
| Supabase | PostgreSQL data warehouse |
| Windows Task Scheduler | Daily automation |

---

## 14. Performance

### Query Performance Comparison

| Operation | API Time | Database Time | Improvement |
|-----------|----------|---------------|-------------|
| Harvest reconciliation | 2-5 min | <1 sec | 200x |
| Package lookup | 30-60 sec | <100ms | 300x |
| Historical analysis | ~365 API calls | Single query | Unbounded |

### Typical Sync Metrics

| Metric | Value |
|--------|-------|
| Sync duration | 2-5 minutes |
| API calls per sync | 50-100 |
| Records per sync | 200-500 |
| History growth | 296K rows/year |

---

## 15. Security

### Sensitive Data (Git-Ignored)

- `.env` - API keys and passwords
- `metrc_api.log` - Contains API responses

### Access Control

- API keys scoped to specific licenses
- Supabase connection via pooler (no direct DB)
- Environment variables for all secrets

### Best Practices

- Rotate API keys regularly via Metrc Connect
- Never commit `.env` to version control
- Monitor `metrc_api.log` for unusual activity

---

## 16. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        METRC API                                 │
│  (State Cannabis Compliance System)                             │
│                                                                  │
│  ┌─────────────────────┐     ┌─────────────────────┐            │
│  │ Cultivation License │     │ Processing License  │            │
│  │     MC281599        │     │     MP281433        │            │
│  │                     │     │                     │            │
│  │ • Plants           │     │ • Packages          │            │
│  │ • Plant Batches    │     │ • Items             │            │
│  │ • Harvests         │     │ • Transfers         │            │
│  │ • Strains          │     │ • Lab Tests         │            │
│  └──────────┬──────────┘     └──────────┬──────────┘            │
└─────────────┼────────────────────────────┼──────────────────────┘
              │                            │
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │    MetrcClient (HTTP)       │
              │                             │
              │  • Basic Auth               │
              │  • Rate Limiting (10/sec)   │
              │  • Retry Logic              │
              │  • Error Handling           │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │   Daily Sync Engine         │
              │   (metrc_daily_sync.py)     │
              │                             │
              │  • 48-hour harvest/package  │
              │  • 7-day transfers          │
              │  • Full plant snapshot      │
              │  • History capture          │
              └──────────────┬──────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Supabase PostgreSQL                            │
│                   (Data Warehouse)                               │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ metrc_harvests  │  │ metrc_packages  │  │ metrc_plants    │  │
│  │     (317+)      │  │    (15,421+)    │  │     (768+)      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ metrc_transfers │  │ packages_history│  │  metrc_sync_log │  │
│  │    (3,803+)     │  │   (296K/yr)     │  │    (audit)      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                  │
│  Views: v_harvest_reconciliation, v_complex_packages_detail     │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Downstream Uses                              │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Fast Queries    │  │ Reconciliation  │  │ Excel Reports   │  │
│  │ (<1 second)     │  │ Views           │  │ & Analysis      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 17. Troubleshooting

### Common Issues

| Symptom | Cause | Resolution |
|---------|-------|------------|
| Auth failed | Invalid API keys | Verify keys in Metrc Connect |
| Rate limit errors | Too many requests | Reduce concurrency |
| No data returned | Invalid license | Check license number |
| Sync timeout | Large data volume | Increase timeout |
| Database error | Connection issue | Check Supabase status |

### Debug Commands

```bash
# Test API connection
python simple_test.py

# Check sync log
psql -c "SELECT * FROM metrc_sync_log ORDER BY sync_start DESC LIMIT 10;"

# View recent API logs
tail -100 metrc_api.log
```

---

## 18. Cross-System Integration

### Pipeline Nature: Read-Only

This pipeline is **read-only** — it pulls data from METRC but does not write back. All data in METRC is entered manually by cultivation and manufacturing staff as part of their daily workflow:
- Harvest logging
- Package creation and adjustments
- Transfer manifests
- Waste recording
- Lab result acknowledgment

The pipeline captures this operational data for analytics and reconciliation.

### Cross-System Join Keys

METRC data integrates with other business systems (Apex, Dutchie, QBO) using multiple join keys:

| Join Key | Description | Systems Linked |
|----------|-------------|----------------|
| **Package Tag** | METRC 24-char tag (1A400...) | METRC ↔ Apex ↔ Dutchie |
| **Package Tag History** | Historical tag tracking | METRC ↔ Reconciliation |
| **Manifest Number** | Transfer manifest ID | METRC ↔ Apex |
| **License Number** | Facility license (MC/MP...) | METRC ↔ QBO (vendor) |
| **Harvest Batch Code** | Cultivation batch identifier | METRC ↔ Internal tracking |
| **Production Batch Code** | Manufacturing batch ID | METRC ↔ QA/Compliance |
| **Item Number** | Product SKU/item ID | METRC ↔ Dutchie ↔ Apex |
| **Date-Based Matching** | Transaction date ranges | All systems |

### Join Location: Supabase Views

Cross-system joins occur in **Supabase SQL views**, where tables from different source systems are combined:

```sql
-- Example: METRC packages joined with Apex orders
SELECT
    m.package_tag,
    m.quantity,
    a.order_id,
    a.buyer_name
FROM metrc_packages m
JOIN apex_shipping_orders a
    ON m.package_tag = a.metrc_tag
```

This enables unified reporting across compliance (METRC), sales (Apex/Dutchie), and finance (QBO) data.

### Inventory Costing Workflow

METRC tracks **weights and quantities** but not costs. Inventory valuation follows a separate workflow:

```
METRC (Weights/Quantities)
        │
        ▼
Spreadsheet Analysis (Excel/Sheets)
        │ Calculate costs per batch/package
        │ Apply cost allocation methods
        │ Generate valuation summary
        ▼
Journal Entries (CSV)
        │
        ▼
QBO (COGS/Inventory Accounts)
```

**Key Points:**
- METRC provides the physical inventory data (what exists)
- Spreadsheets calculate the financial value (what it's worth)
- Journal entries post the valuation to QBO
- No automated cost tracking from METRC to QBO

### Entity Relationship Status

| Relationship | Status | Priority |
|--------------|--------|----------|
| METRC Facilities ↔ QBO Vendors | No formal crosswalk | Medium |
| METRC Transfers ↔ Apex Orders | No formal crosswalk | Medium |
| METRC Packages ↔ Dutchie Inventory | No formal crosswalk | Medium |
| METRC Package Tags ↔ Sales | Ad-hoc joins | Medium |

**Future State:** Formal entity crosswalk table to enable:
- Automated sales reconciliation (METRC transfers vs Apex orders)
- Inventory accuracy validation (METRC vs Dutchie counts)
- Vendor spend analysis (METRC facilities vs QBO payables)

---

## 19. Future Improvements

- [ ] Weekly automated reference data sync
- [ ] Real-time alerting for reconciliation discrepancies
- [ ] Dashboard layer (Streamlit/PowerBI)
- [ ] Export to BigQuery for enterprise analytics
- [ ] Parallel API requests for faster sync
- [ ] Log file rotation
- [ ] Role-based access control
- [ ] **Formalize METRC ↔ Apex/Dutchie entity crosswalk** (medium priority)
- [ ] Automate inventory costing workflow
- [ ] METRC package tag → sales transaction linkage

---

*Document generated: January 2026*
*Pipeline version: Production (active since July 2025)*
