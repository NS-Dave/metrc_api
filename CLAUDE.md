# CLAUDE.md — metrc_api

METRC (Massachusetts cannabis compliance) → Supabase. Licenses: MC281599 (cultivation),
MP281433 (processing). Heartbeat name: `metrc`. Root invariants: `C:\python\CLAUDE.md`.

## Entry points & schedule

- **Daily 6 AM** (`run_daily_sync.bat`, heartbeat-wrapped) → `metrc_daily_sync.py`
  (incremental by last-modified). Rolling log: `logs/daily_sync.log` (success marker:
  `DAILY SYNC COMPLETED SUCCESSFULLY`).
- Reference data: `metrc_reference_data_sync.py`. Historical:
  `metrc_historical_backfill.py`. Plants: `sync_plants.py`.
- DB-side audit trail: `metrc_sync_log` table (note: `metrc_sync_logs` also exists but
  is empty/legacy — write to `metrc_sync_log`).

## Data notes & traps

- This is **compliance data** — reconciliation against METRC is the ground truth for
  audits. Harvest reconciliation tooling: `harvest_recon_tool.py`,
  `export_harvest_reconciliation.py`, views in `harvest_reconciliation_views.sql`.
- Package history uses SCD-style tracking (`package_history.py`,
  `schema_package_history.sql`) — updates append history, they don't overwrite.
- Transfers have direction/type enrichment applied via the `schema_transfer_*.sql`
  series; read `TRANSFER_STORAGE_LOGIC.md` before touching transfer code.
- Join keys outward: package tags (24-char `1A4000...`) → Apex line items & Dutchie
  inventory; manifest numbers → Apex shipping orders.
- ⚠️ `metrc_api.log` at the project root is a 45MB+ unrotated log — don't read it whole;
  tail it. (Candidate for cleanup/rotation.)
- Auth: HTTP Basic (vendor+user keys) in `.env`.

## Commands

```powershell
cd c:\python\metrc_api ; .\.venv\Scripts\Activate.ps1
python metrc_daily_sync.py             # daily incremental
python metrc_reference_data_sync.py    # reference tables
python harvest_recon_tool.py           # reconciliation
```

## Definition of done

1. venv active; manual `metrc_daily_sync.py` completes with the success marker in the log.
2. `metrc_sync_log` has a fresh row; heartbeat lands in `pipeline_last_runs`.
3. Schema changes go through a `schema_*.sql` file (pattern here), applied deliberately.
4. Commit from Windows (sandbox git leaves stale locks).
