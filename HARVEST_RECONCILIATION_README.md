# Harvest Reconciliation System

## Overview

This system provides SQL-based harvest reconciliation with Excel export for review. It replaces the ad-hoc CLI tool with a systematic approach that scales to all harvests.

## Philosophy

- **Calculate in SQL**: All reconciliation logic lives in database views
- **Review in Excel**: Export to spreadsheets for analysis
- **Transparent**: Show all data, flag issues, no black-box automation
- **Simple vs Complex**: Separate packages by source harvest count
- **API Enrichment**: Pull additional context from Metrc when needed

## Components

### 1. SQL Views (`harvest_reconciliation_views.sql`)

**Main Views:**
- `v_harvest_reconciliation` - Master reconciliation view (one row per harvest)
- `v_harvests_needing_review` - Harvests with discrepancies or complex packages
- `v_complex_packages_detail` - All complex packages needing manual allocation
- `v_package_categorization` - Simple vs complex, active vs finished
- `v_transfer_classification` - Sale vs internal transfers

**Install Views:**
```sql
-- Copy content from harvest_reconciliation_views.sql
-- Paste and run in Supabase SQL Editor
```

### 2. Export Script (`export_harvest_reconciliation.py`)

**Basic Export (SQL only):**
```powershell
python export_harvest_reconciliation.py --output reconciliation.xlsx
```

**With API Enrichment (slower, more detail):**
```powershell
python export_harvest_reconciliation.py --with-api-context
```

**Single Harvest Detail:**
```powershell
python export_harvest_reconciliation.py --harvest "DXFO R4C68 11/10/25" --output detail.xlsx
```

### 3. CLI Tool (Legacy, for quick checks)

```powershell
# Quick single harvest check
python harvest_recon_tool.py --harvest "DXFO R4C68 11/10/25" --packages

# Summary of last 30 days
python harvest_recon_tool.py --days 30
```

## Workflow

### Step 1: Install SQL Views

1. Open [harvest_reconciliation_views.sql](harvest_reconciliation_views.sql)
2. Copy entire file
3. Paste into Supabase SQL Editor
4. Run to create all views and indexes

### Step 2: Export to Excel

```powershell
cd c:\python\metrc_api
python export_harvest_reconciliation.py
```

This creates `harvest_reconciliation.xlsx` with sheets:
- **Reconciliation Summary** - All harvests with metrics
- **Needs Review** - Harvests with discrepancies or complex packages
- **Complex Packages** - Packages requiring manual weight allocation
- **Active Inventory** - Current inventory grouped by harvest
- **Sales by Harvest** - Sales grouped by harvest

### Step 3: Review in Excel

**Check "Needs Review" sheet:**
- `simple_discrepancy > 1g` - Weight discrepancy
- `complex_package_count > 0` - Manual allocation needed

**For Complex Packages:**
- Check "Complex Packages" sheet
- Each row shows package with multiple source harvests
- `source_harvest_names` column lists all source harvests
- Requires manual decision on weight attribution

### Step 4: Enrich with API Context (Optional)

For complex packages, get detailed source harvest breakdown from Metrc:

```powershell
python export_harvest_reconciliation.py --with-api-context
```

This creates additional files:
- `harvest_reconciliation_complex_enriched.xlsx` - Complex packages with API source harvest details
- `harvest_reconciliation_adjustment_reasons.xlsx` - List of package adjustment reasons

## Business Rules

### Active Package
```sql
finished_date IS NULL AND archived_date IS NULL
```

### Sale Transfer
```sql
shipment_type IN ('Unaffiliated Transfer', 'Affiliated Transfer')
AND destination_facility_name != '140 Industrial Road, LLC'
```

### Simple Package
- Single source harvest
- Weight fully attributable to that harvest
- Auto-reconciled

### Complex Package
- Multiple source harvests
- Weight split across multiple harvests
- Requires manual allocation decision

## Reconciliation Status

- **OK**: Simple discrepancy < 1g
- **REVIEW_NEEDED**: Simple discrepancy ≥ 1g OR has complex packages

## Direct SQL Queries

### All Harvests with Issues
```sql
SELECT * FROM v_harvests_needing_review;
```

### Complex Packages
```sql
SELECT * FROM v_complex_packages_detail;
```

### Single Harvest Detail
```sql
SELECT * FROM v_package_detail 
WHERE 'DXFO R4C68 11/10/25' = ANY(source_harvest_array);
```

### Active Inventory Summary
```sql
SELECT 
    UNNEST(source_harvest_array) as harvest_name,
    COUNT(*) as package_count,
    SUM(quantity) as total_weight
FROM v_package_categorization
WHERE package_status = 'active'
GROUP BY harvest_name
ORDER BY total_weight DESC;
```

## Metrc API Context

### Package Source Harvest Details
```python
from export_harvest_reconciliation import MetrcAPIContext

api = MetrcAPIContext()
source_harvests = api.get_package_source_harvests(package_id=123456, license_number='MC281599')
# Returns list of source harvests with weights per harvest
```

### Adjustment Reasons
```python
reasons = api.get_adjustment_reasons(license_number='MC281599')
# Returns list of valid adjustment reasons for package weight changes
```

## Automation

The SQL views are automatically updated as new data syncs from Metrc (daily at 6 AM via `metrc_daily_sync.py`). Export whenever you need current reconciliation status:

```powershell
# Weekly reconciliation export
python export_harvest_reconciliation.py --output "reconciliation_$(Get-Date -Format 'yyyy-MM-dd').xlsx"
```

## Performance

SQL views use GIN indexes on `source_harvest_names` for fast lookup. Export of ~1000 harvests takes ~10-15 seconds without API enrichment, ~5-10 minutes with API enrichment (depends on complex package count).

## Troubleshooting

**Empty results:**
```sql
-- Check if views exist
SELECT * FROM pg_views WHERE schemaname = 'public' AND viewname LIKE 'v_harvest%';

-- Verify data
SELECT COUNT(*) FROM metrc_harvests;
SELECT COUNT(*) FROM metrc_packages WHERE source_harvest_names IS NOT NULL;
```

**Slow export:**
- Run without `--with-api-context` first
- API enrichment makes one API call per complex package
- Use API enrichment only when you need source harvest weight breakdown

**Missing columns:**
- Ensure SQL views are installed from latest `harvest_reconciliation_views.sql`
- Re-run the SQL file in Supabase to update views
